from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .agents import (
    run_intake,
    run_planning,
    run_review,
)
from .schemas import (
    AgentHandoff,
    AgentRun,
    AgentStep,
    IntakeOutput,
    PlanningOutput,
    ReviewOutput,
    SourceFact,
    SourceReference,
)
from .store import get_run, save_run


MAX_REVIEW_ATTEMPTS = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def add_step(
    run: AgentRun,
    agent: str,
    attempt: int,
    input_version: int,
) -> AgentStep:
    step = AgentStep(
        step_id=new_id("step"),
        run_id=run.run_id,
        agent=agent,
        attempt=attempt,
        input_version=input_version,
        output_version=None,
        status="RUNNING",
        input_data={},
        output_data=None,
        error=None,
        created_at=now_iso(),
        completed_at=None,
    )

    run.steps.append(step)
    return step


def complete_step(
    step: AgentStep,
    output_data: dict,
    output_version: int,
) -> None:
    step.status = "COMPLETED"
    step.output_data = output_data
    step.output_version = output_version
    step.completed_at = now_iso()


def fail_step(
    step: AgentStep,
    error: str,
) -> None:
    step.status = "FAILED"
    step.error = error
    step.completed_at = now_iso()


def validate_handoff(
    payload: dict,
    required_fields: list[str],
) -> tuple[bool, str | None]:
    for field in required_fields:
        if field not in payload:
            return False, f"Missing required handoff field: {field}"

    return True, None


def add_handoff(
    run: AgentRun,
    from_agent: str,
    to_agent: str,
    payload: dict,
    input_version: int,
    output_version: int,
    required_fields: list[str],
) -> AgentHandoff:

    valid, error = validate_handoff(
        payload=payload,
        required_fields=required_fields,
    )

    handoff = AgentHandoff(
        handoff_id=new_id("handoff"),
        run_id=run.run_id,
        from_agent=from_agent,
        to_agent=to_agent,
        input_version=input_version,
        output_version=output_version,
        payload=payload,
        validation_status="VALID" if valid else "INVALID",
    )

    run.handoffs.append(handoff)

    if not valid:
        raise RuntimeError(
            f"Invalid {from_agent} -> {to_agent} handoff: {error}"
        )

    return handoff


def extract_source_facts(
    intake: IntakeOutput,
) -> list[SourceFact]:
    """
    Convert Intake output into persisted source facts.

    This is only used when a new Intake result is generated.
    Existing user-corrected source facts are preserved separately.
    """

    facts: list[SourceFact] = []

    for item in intake.decisions:
        facts.append(
            SourceFact(
                fact_id=item.id,
                fact_type="decision",
                content=item.content,
                source_reference=item.source_reference,
            )
        )

    for item in intake.requirements:
        facts.append(
            SourceFact(
                fact_id=item.id,
                fact_type="requirement",
                content=item.content,
                source_reference=item.source_reference,
            )
        )

    for item in intake.constraints:
        facts.append(
            SourceFact(
                fact_id=item.id,
                fact_type="constraint",
                content=item.content,
                source_reference=item.source_reference,
            )
        )

    return facts


def create_new_run(
    session_id: str,
    transcript: str,
    company_rules: str,
    simulate_failure_at: str | None = None,
) -> AgentRun:

    return AgentRun(
        run_id=new_id("run"),
        session_id=session_id,
        source_version=1,
        transcript=transcript,
        company_rules=company_rules,
        source_facts=[],
        steps=[],
        handoffs=[],
        status="RUNNING",
        final_plan=None,
        review_attempts=0,
        simulate_failure_at=simulate_failure_at,
        created_at=now_iso(),
        updated_at=now_iso(),
    )


def _latest_completed_step(
    run: AgentRun,
    agent: str,
) -> AgentStep | None:

    candidates = [
        step
        for step in run.steps
        if step.agent == agent
        and step.status == "COMPLETED"
        and step.output_version == run.source_version
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda step: step.attempt,
    )


def _current_source_facts(
    run: AgentRun,
) -> list[dict]:

    return [
        fact.model_dump()
        for fact in run.source_facts
    ]


def _latest_intake_output(
    run: AgentRun,
) -> IntakeOutput | None:

    step = _latest_completed_step(
        run,
        "intake",
    )

    if not step or not step.output_data:
        return None

    return IntakeOutput.model_validate(
        step.output_data
    )


def _latest_planning_output(
    run: AgentRun,
) -> PlanningOutput | None:

    step = _latest_completed_step(
        run,
        "planning",
    )

    if not step or not step.output_data:
        return None

    return PlanningOutput.model_validate(
        step.output_data
    )


def _latest_review_output(
    run: AgentRun,
) -> ReviewOutput | None:

    step = _latest_completed_step(
        run,
        "review",
    )

    if not step or not step.output_data:
        return None

    return ReviewOutput.model_validate(
        step.output_data
    )


def execute_run(
    run: AgentRun,
    resume: bool = False,
) -> AgentRun:

    run.status = "RUNNING"
    run.updated_at = now_iso()

    current_version = run.source_version

    # ---------------------------------------------------------
    # 1. INTAKE
    # ---------------------------------------------------------
    #
    # IMPORTANT FIX:
    #
    # A completed Intake step is reusable ONLY when its output_version
    # matches the current source_version.
    #
    # Therefore:
    #
    # source_version 1 + Intake version 1 -> reuse
    # source_version 2 + Intake version 1 -> DO NOT reuse
    #
    # This is the core stale-context bug fix.
    # ---------------------------------------------------------

    intake_output = _latest_intake_output(run)

    if intake_output is None:

        intake_step = add_step(
            run=run,
            agent="intake",
            attempt=1,
            input_version=current_version,
        )

        intake_step.input_data = {
            "transcript": run.transcript,
            "source_version": current_version,
            "source_facts": _current_source_facts(run),
        }

        try:

            if run.simulate_failure_at == "intake":
                raise RuntimeError("SIMULATED MODEL FAILURE")

            intake_output = run_intake(
                transcript=run.transcript,
                source_facts=_current_source_facts(run),
            )

            complete_step(
                step=intake_step,
                output_data=intake_output.model_dump(),
                output_version=current_version,
            )

            # -------------------------------------------------
            # Only initialise source facts when this is the
            # first source version.
            #
            # For a corrected source version, NEVER overwrite
            # the user's corrected source facts with a fresh
            # extraction from the old transcript.
            # -------------------------------------------------

            if current_version == 1 and not run.source_facts:
                run.source_facts = extract_source_facts(
                    intake_output
                )

        except Exception as exc:
            fail_step(
                intake_step,
                str(exc),
            )

            run.status = "FAILED"
            run.updated_at = now_iso()
            save_run(run)
            return run

        save_run(run)

    # ---------------------------------------------------------
    # 2. INTAKE -> PLANNING HANDOFF
    # ---------------------------------------------------------

    add_handoff(
        run=run,
        from_agent="intake",
        to_agent="planning",
        input_version=current_version,
        output_version=current_version,
        payload={
            "source_version": current_version,
            "source_facts": _current_source_facts(run),
            "intake_output": intake_output.model_dump(),
        },
        required_fields=[
            "source_version",
            "source_facts",
            "intake_output",
        ],
    )

    save_run(run)

    # ---------------------------------------------------------
    # 3. PLANNING -> REVIEW LOOP
    # ---------------------------------------------------------

    corrections: list[dict] = []

    # If we already have a review correction for this source version,
    # preserve it for resumed/repeated execution.
    previous_review = _latest_review_output(run)

    if previous_review and previous_review.status == "FAIL":
        corrections = [
            correction.model_dump()
            for correction in previous_review.corrections
        ]

    for attempt in range(
        1,
        MAX_REVIEW_ATTEMPTS + 1,
    ):

        run.review_attempts = attempt

        # -----------------------------------------------------
        # PLANNING
        # -----------------------------------------------------

        planning_output = _latest_planning_output(run)

        if planning_output is None:

            planning_step = add_step(
                run=run,
                agent="planning",
                attempt=attempt,
                input_version=current_version,
            )

            planning_step.input_data = {
                "source_version": current_version,
                "source_facts": _current_source_facts(run),
                "intake_output": intake_output.model_dump(),
                "company_rules": run.company_rules,
                "corrections": corrections,
            }

            try:

                if (
                    run.simulate_failure_at == "planning"
                    and not resume
                ):
                    raise RuntimeError(
                        "SIMULATED MODEL FAILURE"
                    )

                planning_output = run_planning(
                    transcript=run.transcript,
                    intake=intake_output,
                    company_rules=run.company_rules,
                    source_facts=_current_source_facts(run),
                    corrections=corrections,
                )

                complete_step(
                    step=planning_step,
                    output_data=planning_output.model_dump(),
                    output_version=current_version,
                )

            except Exception as exc:

                fail_step(
                    planning_step,
                    str(exc),
                )

                run.status = "FAILED"
                run.updated_at = now_iso()
                save_run(run)
                return run

            save_run(run)

        # -----------------------------------------------------
        # PLANNING -> REVIEW HANDOFF
        # -----------------------------------------------------

        add_handoff(
            run=run,
            from_agent="planning",
            to_agent="review",
            input_version=current_version,
            output_version=current_version,
            payload={
                "source_version": current_version,
                "source_facts": _current_source_facts(run),
                "intake_output": intake_output.model_dump(),
                "planning_output": planning_output.model_dump(),
            },
            required_fields=[
                "source_version",
                "source_facts",
                "intake_output",
                "planning_output",
            ],
        )

        save_run(run)

        # -----------------------------------------------------
        # REVIEW
        # -----------------------------------------------------

        review_output = _latest_review_output(run)

        if review_output is None:

            review_step = add_step(
                run=run,
                agent="review",
                attempt=attempt,
                input_version=current_version,
            )

            review_step.input_data = {
                "source_version": current_version,
                "source_facts": _current_source_facts(run),
                "intake_output": intake_output.model_dump(),
                "planning_output": planning_output.model_dump(),
                "company_rules": run.company_rules,
            }

            try:

                if (
                    run.simulate_failure_at == "review"
                    and not resume
                ):
                    raise RuntimeError(
                        "SIMULATED MODEL FAILURE"
                    )

                review_output = run_review(
                    transcript=run.transcript,
                    intake=intake_output,
                    plan=planning_output,
                    company_rules=run.company_rules,
                    source_facts=_current_source_facts(run),
                )

                complete_step(
                    step=review_step,
                    output_data=review_output.model_dump(),
                    output_version=current_version,
                )

            except Exception as exc:

                fail_step(
                    review_step,
                    str(exc),
                )

                run.status = "FAILED"
                run.updated_at = now_iso()
                save_run(run)
                return run

            save_run(run)

        # -----------------------------------------------------
        # REVIEW RESULT
        # -----------------------------------------------------

        if review_output.status == "PASS":

            run.final_plan = planning_output.model_dump()
            run.status = "COMPLETED"
            run.updated_at = now_iso()

            save_run(run)
            return run

        # -----------------------------------------------------
        # REVIEW FAILED -> PLANNING CORRECTION
        # -----------------------------------------------------

        corrections = [
            correction.model_dump()
            for correction in review_output.corrections
        ]

        add_handoff(
            run=run,
            from_agent="review",
            to_agent="planning",
            input_version=current_version,
            output_version=current_version,
            payload={
                "source_version": current_version,
                "corrections": corrections,
            },
            required_fields=[
                "source_version",
                "corrections",
            ],
        )

        save_run(run)

        # We deliberately continue to the next attempt.
        #
        # The next Planning call gets:
        # - current source facts
        # - current Intake
        # - review corrections
        #
        # Therefore the correction is a real agent-to-agent loop.

        if attempt >= MAX_REVIEW_ATTEMPTS:
            run.status = "UNRESOLVED"
            run.final_plan = planning_output.model_dump()
            run.updated_at = now_iso()
            save_run(run)
            return run

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # Remove nothing from the audit trail.
        #
        # We need the next Planning attempt to be a NEW step.
        # -----------------------------------------------------

        # Mark the current Planning output as stale for the next
        # correction attempt so _latest_planning_output() does not
        # reuse it.
        for step in run.steps:
            if (
                step.agent == "planning"
                and step.output_version == current_version
                and step.status == "COMPLETED"
            ):
                step.status = "STALE"

        # Same for Review, so the next attempt gets a new Review call.
        for step in run.steps:
            if (
                step.agent == "review"
                and step.output_version == current_version
                and step.status == "COMPLETED"
            ):
                step.status = "STALE"

        save_run(run)

    run.status = "UNRESOLVED"
    run.updated_at = now_iso()
    save_run(run)

    return run


def start_run(
    session_id: str,
    transcript: str,
    company_rules: str,
    simulate_failure_at: str | None = None,
) -> AgentRun:

    run = create_new_run(
        session_id=session_id,
        transcript=transcript,
        company_rules=company_rules,
        simulate_failure_at=simulate_failure_at,
    )

    save_run(run)

    return execute_run(run)


def resume_run(
    run_id: str,
    session_id: str,
) -> AgentRun:

    run = get_run(
        run_id=run_id,
        session_id=session_id,
    )

    if not run:
        raise ValueError("Run not found.")

    # The simulated failure flag is intentionally cleared so
    # resume performs the failed operation normally.
    run.simulate_failure_at = None

    return execute_run(
        run,
        resume=True,
    )