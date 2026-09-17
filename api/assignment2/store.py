from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient

from .schemas import AgentRun


MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is not configured."
    )


client = MongoClient(MONGODB_URI)

db_name = os.getenv(
    "MONGODB_DATABASE",
    "abstract_ai",
)

db = client[db_name]

runs_collection = db["agent_runs"]


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def create_run(run: AgentRun) -> None:
    runs_collection.insert_one(
        run.model_dump()
    )


def get_run(
    run_id: str,
    session_id: Optional[str] = None,
) -> Optional[AgentRun]:

    query = {
        "run_id": run_id,
    }

    if session_id is not None:
        query["session_id"] = session_id

    document = runs_collection.find_one(
        query
    )

    if not document:
        return None

    document.pop("_id", None)

    return AgentRun.model_validate(
        document
    )


def save_run(run: AgentRun) -> None:

    run.updated_at = now_iso()

    runs_collection.update_one(
        {
            "run_id": run.run_id,
            "session_id": run.session_id,
        },
        {
            "$set": run.model_dump()
        },
        upsert=True,
    )


def delete_session_runs(
    session_id: str,
) -> None:

    runs_collection.delete_many(
        {
            "session_id": session_id
        }
    )