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
)

from .store import (
    get_run,
    save_run,
)


MAX_REVIEW_ATTEMPTS = 2


# =========================================================
# HELPERS
# =========================================================

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

            return (
                False,
                f"Missing required handoff field: {field}",
            )

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
        validation_status=(
            "VALID"
            if valid
            else "INVALID"
        ),
    )

    run.handoffs.append(handoff)

    if not valid:

        raise RuntimeError(
            f"Invalid handoff "
            f"{from_agent} -> {to_agent}: {error}"
        )

    return handoff


# =========================================================
# SOURCE FACT EXTRACTION
# =========================================================

def extract_source_facts(
    intake: IntakeOutput,
) -> list[SourceFact]:
    """
    Convert IntakeOutput into persisted SourceFact objects.

    Uses the actual schemas.py fields:
    - fact_id
    - category
    - content
    - source_reference
    """

    facts: list[SourceFact] = []

    for item in intake.decisions:

        facts.append(
            SourceFact(
                fact_id=item.fact_id,
                category="decision",
                content=item.content,
                source_reference=item.source_reference,
            )
        )

    for item in intake.requirements:

        facts.append(
            SourceFact(
                fact_id=item.fact_id,
                category="requirement",
                content=item.content,
                source_reference=item.source_reference,
            )
        )

    for item in intake.constraints:

        facts.append(
            SourceFact(
                fact_id=item.fact_id,
                category="constraint",
                content=item.content,
                source_reference=item.source_reference,
            )
        )

    return facts


# =========================================================
# CREATE RUN
# =========================================================

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


# =========================================================
# CURRENT SOURCE FACTS
# =========================================================

def current_source_facts(
    run: AgentRun,
) -> list[dict]:

    return [
        fact.model_dump()
        for fact in run.source_facts
    ]


# =========================================================
# FIND CURRENT-VERSION STEPS
# =========================================================

def latest_completed_step(
    run: AgentRun,
    agent: str,
) -> AgentStep | None:

    candidates = [
        step
        for step in run.steps
        if (
            step.agent == agent
            and step.status == "COMPLETED"
            and step.output_version == run.source_version
        )
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda step: step.attempt,
    )


def latest_intake_output(
    run: AgentRun,
) -> IntakeOutput | None:

    step = latest_completed_step(
        run,
        "intake",
    )

    if step is None:
        return None

    if step.output_data is None:
        return None

    return IntakeOutput.model_validate(
        step.output_data
    )


def latest_planning_output(
    run: AgentRun,
) -> PlanningOutput | None:

    step = latest_completed_step(
        run,
        "planning",
    )

    if step is None:
        return None

    if step.output_data is None:
        return None

    return PlanningOutput.model_validate(
        step.output_data
    )


def latest_review_output(
    run: AgentRun,
) -> ReviewOutput | None:

    step = latest_completed_step(
        run,
        "review",
    )

    if step is None:
        return None

    if step.output_data is None:
        return None

    return ReviewOutput.model_validate(
        step.output_data
    )


# =========================================================
# MARK AGENT OUTPUT STALE
# =========================================================

def mark_agent_stale(
    run: AgentRun,
    agent: str,
) -> None:

    for step in run.steps:

        if (
            step.agent == agent
            and step.status == "COMPLETED"
        ):
            step.status = "STALE"


# =========================================================
# EXECUTE RUN
# =========================================================

def execute_run(
    run: AgentRun,
    resume: bool = False,
) -> AgentRun:

    run.status = "RUNNING"
    run.updated_at = now_iso()

    source_version = run.source_version

    # =====================================================
    # 1. INTAKE
    # =====================================================

    intake_output = latest_intake_output(run)

    if intake_output is None:

        intake_step = add_step(
            run=run,
            agent="intake",
            attempt=1,
            input_version=source_version,
        )

        intake_step.input_data = {
            "transcript": run.transcript,
            "source_version": source_version,
            "source_facts": current_source_facts(run),
        }

        try:

            if run.simulate_failure_at == "intake":

                raise RuntimeError(
                    "SIMULATED MODEL FAILURE"
                )

            intake_output = run_intake(
                transcript=run.transcript,
                source_facts=current_source_facts(run),
            )

            complete_step(
                step=intake_step,
                output_data=intake_output.model_dump(),
                output_version=source_version,
            )

            # Only create initial source facts for version 1.
            #
            # After a user correction, we preserve the corrected
            # source fact instead of extracting the old transcript
            # value again.

            if (
                source_version == 1
                and not run.source_facts
            ):

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

    # =====================================================
    # 2. INTAKE -> PLANNING
    # =====================================================

    add_handoff(
        run=run,
        from_agent="intake",
        to_agent="planning",
        input_version=source_version,
        output_version=source_version,
        payload={
            "source_version": source_version,
            "source_facts": current_source_facts(run),
            "intake_output": intake_output.model_dump(),
        },
        required_fields=[
            "source_version",
            "source_facts",
            "intake_output",
        ],
    )

    save_run(run)

    # =====================================================
    # 3. PLANNING / REVIEW LOOP
    # =====================================================

    corrections: list[dict] = []

    for attempt in range(
        1,
        MAX_REVIEW_ATTEMPTS + 1,
    ):

        run.review_attempts = attempt

        # =================================================
        # PLANNING
        # =================================================

        planning_output = latest_planning_output(run)

        if planning_output is None:

            planning_step = add_step(
                run=run,
                agent="planning",
                attempt=attempt,
                input_version=source_version,
            )

            planning_step.input_data = {
                "source_version": source_version,
                "source_facts": current_source_facts(run),
                "intake_output": intake_output.model_dump(),
                "company_rules": run.company_rules,
                "corrections": corrections,
            }

            try:

                if run.simulate_failure_at == "planning":

                    raise RuntimeError(
                        "SIMULATED MODEL FAILURE"
                    )

                planning_output = run_planning(
                    transcript=run.transcript,
                    intake=intake_output,
                    company_rules=run.company_rules,
                    source_facts=current_source_facts(run),
                    corrections=corrections,
                )

                complete_step(
                    step=planning_step,
                    output_data=planning_output.model_dump(),
                    output_version=source_version,
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

        # =================================================
        # PLANNING -> REVIEW
        # =================================================

        add_handoff(
            run=run,
            from_agent="planning",
            to_agent="review",
            input_version=source_version,
            output_version=source_version,
            payload={
                "source_version": source_version,
                "source_facts": current_source_facts(run),
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

        # =================================================
        # REVIEW
        # =================================================

        review_output = latest_review_output(run)

        if review_output is None:

            review_step = add_step(
                run=run,
                agent="review",
                attempt=attempt,
                input_version=source_version,
            )

            review_step.input_data = {
                "source_version": source_version,
                "source_facts": current_source_facts(run),
                "intake_output": intake_output.model_dump(),
                "planning_output": planning_output.model_dump(),
                "company_rules": run.company_rules,
            }

            try:

                if run.simulate_failure_at == "review":

                    raise RuntimeError(
                        "SIMULATED MODEL FAILURE"
                    )

                review_output = run_review(
                    transcript=run.transcript,
                    intake=intake_output,
                    plan=planning_output,
                    company_rules=run.company_rules,
                    source_facts=current_source_facts(run),
                )

                complete_step(
                    step=review_step,
                    output_data=review_output.model_dump(),
                    output_version=source_version,
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

        # =================================================
        # REVIEW PASS
        # =================================================

        if review_output.status == "PASS":

            run.final_plan = planning_output
            run.status = "COMPLETED"
            run.updated_at = now_iso()

            save_run(run)

            return run

        # =================================================
        # REVIEW FAIL
        # =================================================

        corrections = [
            correction.model_dump()
            for correction in review_output.corrections
        ]

        add_handoff(
            run=run,
            from_agent="review",
            to_agent="planning",
            input_version=source_version,
            output_version=source_version,
            payload={
                "source_version": source_version,
                "corrections": corrections,
            },
            required_fields=[
                "source_version",
                "corrections",
            ],
        )

        save_run(run)

        # No more attempts available.

        if attempt >= MAX_REVIEW_ATTEMPTS:

            run.status = "UNRESOLVED"
            run.final_plan = planning_output
            run.updated_at = now_iso()

            save_run(run)

            return run

        # Force the next attempt to create fresh
        # Planning + Review steps.

        mark_agent_stale(
            run,
            "planning",
        )

        mark_agent_stale(
            run,
            "review",
        )

        save_run(run)

    # Safety fallback.

    run.status = "UNRESOLVED"
    run.updated_at = now_iso()

    save_run(run)

    return run


# =========================================================
# START RUN
# =========================================================

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


# =========================================================
# RESUME RUN
# =========================================================

def resume_run(
    run_id: str,
    session_id: str,
) -> AgentRun:

    run = get_run(
        run_id=run_id,
        session_id=session_id,
    )

    if run is None:

        raise ValueError(
            "Run not found."
        )

    # Clear simulated failure so the failed operation
    # can execute normally on resume.

    run.simulate_failure_at = None

    return execute_run(
        run,
        resume=True,
    )