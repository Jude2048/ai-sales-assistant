from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .schemas import (
    AgentRun,
    FactCorrectionRequest,
    ResumeRequest,
    RunRequest,
)

from .orchestrator import (
    start_run,
    resume_run,
)

from .store import get_run


router = APIRouter(
    prefix="/assignment2",
    tags=["Assignment 2"],
)


# ---------------------------------------------------------
# START NEW RUN
# ---------------------------------------------------------

@router.post("/runs", response_model=AgentRun)
def start_assignment2_run(request: RunRequest):

    try:

        run = start_run(
            session_id=request.session_id,
            transcript=request.transcript,
            company_rules=request.company_rules,
            simulate_failure_at=request.simulate_failure_at,
        )

        return run

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ---------------------------------------------------------
# GET RUN
# ---------------------------------------------------------

@router.get("/runs/{run_id}", response_model=AgentRun)
def get_assignment2_run(
    run_id: str,
    session_id: str = "demo-session",
):

    run = get_run(
        run_id=run_id,
        session_id=session_id,
    )

    if run is None:

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    return run


# ---------------------------------------------------------
# RESUME RUN
# ---------------------------------------------------------

@router.post("/runs/resume", response_model=AgentRun)
def resume_assignment2_run(
    request: ResumeRequest,
):

    try:

        run = resume_run(
            run_id=request.run_id,
            session_id=request.session_id,
        )

        return run

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ---------------------------------------------------------
# CORRECT SOURCE FACT
# ---------------------------------------------------------

@router.post("/runs/correct-fact")
def correct_assignment2_fact(
    request: FactCorrectionRequest,
):

    run = get_run(
        run_id=request.run_id,
        session_id=request.session_id,
    )

    if run is None:

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    found = False

    for fact in run.source_facts:

        if fact.fact_id == request.fact_id:

            fact.content = request.new_content

            found = True
            break

    if not found:

        raise HTTPException(
            status_code=404,
            detail="Source fact not found.",
        )

    # -----------------------------------------------------
    # Move to the next source version ONCE.
    # -----------------------------------------------------

    run.source_version += 1

    # -----------------------------------------------------
    # Previous outputs are now stale.
    # -----------------------------------------------------

    run.review_attempts = 0
    run.final_plan = None
    run.status = "RUNNING"

    for step in run.steps:

        if step.status == "COMPLETED":
            step.status = "STALE"

    from .store import save_run

    save_run(run)

    return {
        "run_id": run.run_id,
        "source_version": run.source_version,
        "status": run.status,
        "message": (
            "Source fact corrected. "
            "Previous agent outputs are stale."
        ),
    }