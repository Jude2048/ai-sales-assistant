from __future__ import annotations
from pdb import run

from fastapi import APIRouter, HTTPException

from .orchestrator import (
    resume_run,
    start_run,
)

from .schemas import (
    FactCorrectionRequest,
    ResumeRequest,
    RunRequest,
)

from .store import (
    get_run,
    save_run,
)


router = APIRouter(
    prefix="/assignment2",
    tags=["Assignment 2"],
)


@router.post("/runs/resume", response_model=AgentRun)
def resume_assignment2_run(request: ResumeRequest):
    try:
        run = resume_run(
            run_id=request.run_id,
            session_id=request.session_id,
        )

        return run

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

@router.get("/runs/{run_id}")
def get_assignment2_run(
    run_id: str,
    session_id: str = "demo-session",
):

    run = get_run(
        run_id,
        session_id,
    )

    if run is None:

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    return run.model_dump()


@router.post("/runs/resume")
def resume_assignment2_run(
    request: ResumeRequest,
):

    try:

        run = resume_run(
            run_id=request.run_id,
            session_id="demo-session",
        )

        return run.model_dump()

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


@router.post("/runs/correct-fact")
def correct_assignment2_fact(
    request: FactCorrectionRequest,
):

    run = get_run(
        request.run_id
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

    if not found:

        raise HTTPException(
            status_code=404,
            detail="Source fact not found.",
        )

    run.source_version += 1

    # Mark all old agent outputs as stale.
    for step in run.steps:

        if step.status == "COMPLETED":

            step.status = "STALE"

    run.final_plan = None
    run.status = "RUNNING"

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