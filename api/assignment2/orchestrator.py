from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
    create_run,
    get_run,
    save_run,
)


MAX_REVIEW_ATTEMPTS = 2


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def add_step(
    run: AgentRun,
    agent: str,
    attempt: int,
    input_version: int,
    input_data: dict,
) -> AgentStep:

    step = AgentStep(
        step_id=new_id("step"),
        run_id=run.run_id,
        agent=agent,
        attempt=attempt,
        input_version=input_version,
        status="RUNNING",
        input_data=input_data,
    )

    run.steps.append(step)

    save_run(run)

    return step


def complete_step(
    run: AgentRun,
    step: AgentStep,
    output_data: dict,
    output_version: int,
) -> None:

    step.status = "COMPLETED"
    step.output_data = output_data
    step.output_version = output_version

    save_run(run)


def fail_step(
    run: AgentRun,
    step: AgentStep,
    error: str,
) -> None:

    step.status = "FAILED"
    step.error = error

    run.status = "FAILED"

    save_run(run)


def validate_handoff(
    payload: dict,
    required_fields: list[str],
) -> bool:

    return all(
        field in payload
        for field in required_fields
    )


def add_handoff(
    run: AgentRun,
    from_agent: str,
    to_agent: str,
    input_version: int,
    output_version: int,
    payload: dict,
    required_fields: list[str],
) -> None:

    valid = validate_handoff(
        payload,
        required_fields,
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
        raise ValueError(
            f"Invalid {from_agent} → {to_agent} handoff."
        )

    save_run(run)


def extract_source_facts(
    intake: IntakeOutput,
) -> list[SourceFact]:

    facts = []

    for fact in intake.decisions:
        facts.append(fact)

    for fact in intake.requirements:
        facts.append(fact)

    for fact in intake.constraints:
        facts.append(fact)

    return facts


def create_new_run(
    transcript: str,
    company_rules: str,
    session_id: str,
    simulate_failure_at: str | None = None,
) -> AgentRun:

    timestamp = now_iso()

    run = AgentRun(
        run_id=new_id("run"),
        session_id=session_id,
        source_version=1,
        transcript=transcript,
        company_rules=company_rules,
        status="RUNNING",
        simulate_failure_at=simulate_failure_at,
        created_at=timestamp,
        updated_at=timestamp,
    )

    create_run(run)

    return run


def execute_run(
    run: AgentRun,
    resume: bool = False,
) -> AgentRun:

    # --------------------------------------------------
    # 1. INTAKE
    # --------------------------------------------------

    intake_step = next(
        (
            step
            for step in run.steps
            if step.agent == "intake"
            and step.status == "COMPLETED"
        ),
        None,
    )

    if intake_step is None:

        intake_step = add_step(
            run=run,
            agent="intake",
            attempt=1,
            input_version=run.source_version,
            input_data={
                "transcript": run.transcript,
                "company_rules": run.company_rules,
            },
        )

        if (
            run.simulate_failure_at == "intake"
            and not resume
        ):
            fail_step(
                run,
                intake_step,
                "SIMULATED MODEL FAILURE",
            )

            run.simulate_failure_at = None
            save_run(run)

            return run

        try:

            intake = run_intake(
                run.transcript,
                run.company_rules,
            )

            complete_step(
                run,
                intake_step,
                intake.model_dump(),
                run.source_version,
            )

        except Exception as exc:

            fail_step(
                run,
                intake_step,
                str(exc),
            )

            return run

    else:

        intake = IntakeOutput.model_validate(
            intake_step.output_data
        )

    # --------------------------------------------------
    # Source facts
    # --------------------------------------------------

    run.source_facts = extract_source_facts(
        intake
    )

    save_run(run)

    # --------------------------------------------------
    # INTAKE → PLANNING
    # --------------------------------------------------

    add_handoff(
        run=run,
        from_agent="intake",
        to_agent="planning",
        input_version=run.source_version,
        output_version=run.source_version,
        payload=intake.model_dump(),
        required_fields=[
            "decisions",
            "requirements",
            "constraints",
            "missing_information",
            "conflicts",
        ],
    )

    # --------------------------------------------------
    # PLANNING + REVIEW LOOP
    # --------------------------------------------------

    previous_corrections = []

    while (
        run.review_attempts
        < MAX_REVIEW_ATTEMPTS
    ):

        planning_attempt = (
            len(
                [
                    s
                    for s in run.steps
                    if s.agent == "planning"
                ]
            )
            + 1
        )

        planning_step = add_step(
            run=run,
            agent="planning",
            attempt=planning_attempt,
            input_version=run.source_version,
            input_data={
                "intake": intake.model_dump(),
                "company_rules": run.company_rules,
                "corrections": previous_corrections,
            },
        )

        if (
            run.simulate_failure_at == "planning"
            and not resume
            and planning_attempt == 1
        ):
            fail_step(
                run,
                planning_step,
                "SIMULATED MODEL FAILURE",
            )

            run.simulate_failure_at = None
            save_run(run)

            return run

        try:

            planning = run_planning(
                intake=intake,
                company_rules=run.company_rules,
                corrections=previous_corrections,
            )

            complete_step(
                run,
                planning_step,
                planning.model_dump(),
                run.source_version,
            )

        except Exception as exc:

            fail_step(
                run,
                planning_step,
                str(exc),
            )

            return run

        add_handoff(
            run=run,
            from_agent="planning",
            to_agent="review",
            input_version=run.source_version,
            output_version=run.source_version,
            payload=planning.model_dump(),
            required_fields=[
                "tasks",
                "supported_facts",
                "recommendations",
                "unresolved_questions",
            ],
        )

        # --------------------------------------------------
        # REVIEW
        # --------------------------------------------------

        run.review_attempts += 1

        review_step = add_step(
            run=run,
            agent="review",
            attempt=run.review_attempts,
            input_version=run.source_version,
            input_data={
                "transcript": run.transcript,
                "company_rules": run.company_rules,
                "intake": intake.model_dump(),
                "planning": planning.model_dump(),
            },
        )

        if (
            run.simulate_failure_at == "review"
            and not resume
        ):
            fail_step(
                run,
                review_step,
                "SIMULATED MODEL FAILURE",
            )

            run.simulate_failure_at = None
            save_run(run)

            return run

        try:

            review = run_review(
                transcript=run.transcript,
                company_rules=run.company_rules,
                intake=intake,
                planning=planning,
            )

            complete_step(
                run,
                review_step,
                review.model_dump(),
                run.source_version,
            )

        except Exception as exc:

            fail_step(
                run,
                review_step,
                str(exc),
            )

            return run

        if review.status == "PASS":

            run.final_plan = planning
            run.status = "COMPLETED"

            save_run(run)

            return run

        previous_corrections = [
            correction.model_dump()
            for correction in review.corrections
        ]

        add_handoff(
            run=run,
            from_agent="review",
            to_agent="planning",
            input_version=run.source_version,
            output_version=run.source_version,
            payload=review.model_dump(),
            required_fields=[
                "status",
                "corrections",
                "unresolved_issues",
            ],
        )

        if (
            run.review_attempts
            >= MAX_REVIEW_ATTEMPTS
        ):

            run.status = "UNRESOLVED"

            save_run(run)

            return run

    run.status = "UNRESOLVED"

    save_run(run)

    return run


def start_run(
    transcript: str,
    company_rules: str,
    session_id: str,
    simulate_failure_at: str | None = None,
) -> AgentRun:

    run = create_new_run(
        transcript=transcript,
        company_rules=company_rules,
        session_id=session_id,
        simulate_failure_at=simulate_failure_at,
    )

    return execute_run(run)


def resume_run(
    run_id: str,
    session_id: str,
) -> AgentRun:

    run = get_run(
        run_id,
        session_id,
    )

    if run is None:
        raise ValueError(
            "Run not found."
        )

    if run.status not in [
        "FAILED",
    ]:
        return run

    run.status = "RUNNING"

    save_run(run)

    return execute_run(
        run,
        resume=True,
    )