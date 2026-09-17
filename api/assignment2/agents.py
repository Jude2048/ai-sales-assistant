from __future__ import annotations

import json
import os

from google import genai
from pydantic import BaseModel

from .schemas import (
    IntakeOutput,
    PlanningOutput,
    ReviewOutput,
)


MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.1-flash-lite",
)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured."
            )

        _client = genai.Client(
            api_key=api_key
        )

    return _client


def call_llm(
    prompt: str,
    response_schema: type[BaseModel],
) -> BaseModel:

    client = get_client()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": 0.1,
        },
    )

    if not response.text:
        raise RuntimeError(
            "LLM returned an empty response."
        )

    try:
        data = json.loads(response.text)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"LLM returned invalid JSON: {exc}"
        ) from exc

    return response_schema.model_validate(data)


def format_source_facts(
    source_facts: list[dict],
) -> str:

    if not source_facts:
        return "No corrected source facts are currently available."

    return json.dumps(
        source_facts,
        indent=2,
        ensure_ascii=False,
    )


# =========================================================
# INTAKE AGENT
# =========================================================

def run_intake(
    transcript: str,
    source_facts: list[dict] | None = None,
) -> IntakeOutput:

    current_source_facts = source_facts or []

    prompt = f"""
You are the Intake Agent.

Extract structured information from the meeting transcript.

Identify:

1. Decisions
2. Requirements
3. Constraints
4. Missing information
5. Conflicts

Ground everything in the provided evidence.

Rules:

- Do not invent owners.
- Do not invent deadlines.
- Do not invent requirements.
- Every decision, requirement, and constraint must contain a source reference.
- Clearly identify missing information.
- Clearly identify conflicts.
- Do not turn recommendations into facts.

IMPORTANT SOURCE-VERSION RULE:

The original transcript is preserved unchanged.

The CURRENT SOURCE FACTS represent the authoritative structured
source context.

If a current source fact differs from the original transcript,
treat the current source fact as the corrected authoritative value.

Do NOT revert a corrected fact back to the old transcript value.

ORIGINAL MEETING TRANSCRIPT:
{transcript}

CURRENT SOURCE FACTS:
{format_source_facts(current_source_facts)}

Return only the IntakeOutput schema.
"""

    return call_llm(
        prompt=prompt,
        response_schema=IntakeOutput,
    )


# =========================================================
# PLANNING AGENT
# =========================================================

def run_planning(
    transcript: str,
    intake: IntakeOutput,
    company_rules: str,
    source_facts: list[dict] | None = None,
    corrections: list[dict] | None = None,
) -> PlanningOutput:

    current_source_facts = source_facts or []
    review_corrections = corrections or []

    prompt = f"""
You are the Planning Agent.

Create an actionable operations plan using:

- the Intake Agent output
- the CURRENT SOURCE FACTS
- the company rules
- any Review Agent corrections

Each task may contain:

- task_id
- task
- owner
- deadline
- dependencies
- basis

The basis must distinguish between:

- supported_fact
- company_rule
- recommendation
- unresolved

Rules:

- Do not invent owners.
- Do not invent meeting deadlines.
- Do not invent requirements.
- A company rule can influence a recommendation, but must not be
  presented as a meeting fact.
- If the meeting and company rules conflict, explicitly represent
  the conflict.
- Incorporate Review Agent corrections.
- Use CURRENT SOURCE FACTS as authoritative.
- A user-corrected source fact overrides the stale value from an
  earlier agent output.
- Keep unresolved questions explicit.

ORIGINAL MEETING TRANSCRIPT:
{transcript}

CURRENT SOURCE FACTS:
{format_source_facts(current_source_facts)}

INTAKE AGENT OUTPUT:
{json.dumps(
    intake.model_dump(),
    indent=2,
    ensure_ascii=False,
)}

COMPANY RULES:
{company_rules}

REVIEW AGENT CORRECTIONS:
{json.dumps(
    review_corrections,
    indent=2,
    ensure_ascii=False,
)}

Return only the PlanningOutput schema.
"""

    return call_llm(
        prompt=prompt,
        response_schema=PlanningOutput,
    )


# =========================================================
# REVIEW AGENT
# =========================================================

def run_review(
    transcript: str,
    intake: IntakeOutput,
    plan: PlanningOutput,
    company_rules: str,
    source_facts: list[dict] | None = None,
) -> ReviewOutput:

    current_source_facts = source_facts or []

    prompt = f"""
You are the Review Agent.

Review the Planning Agent's proposed plan against:

1. The original meeting transcript
2. The CURRENT SOURCE FACTS
3. The Intake Agent output
4. The company rules

Check for:

- unsupported owners
- unsupported deadlines
- invented requirements
- missing requirements
- conflicts with current source facts
- company rule violations
- missing dependencies
- incorrect basis classification
- unresolved source conflicts

IMPORTANT:

CURRENT SOURCE FACTS are authoritative.

If a source fact has been corrected by the user,
the corrected value must be used when reviewing the plan.

The original transcript remains unchanged for audit purposes.

If the plan has a problem:

Return:

status = FAIL

and provide a specific correction for the Planning Agent.

If the plan is valid:

Return:

status = PASS

and an empty corrections list.

Do not approve a plan simply because an earlier agent produced it.

ORIGINAL MEETING TRANSCRIPT:
{transcript}

CURRENT SOURCE FACTS:
{format_source_facts(current_source_facts)}

INTAKE AGENT OUTPUT:
{json.dumps(
    intake.model_dump(),
    indent=2,
    ensure_ascii=False,
)}

PLANNING AGENT OUTPUT:
{json.dumps(
    plan.model_dump(),
    indent=2,
    ensure_ascii=False,
)}

COMPANY RULES:
{company_rules}

Return only the ReviewOutput schema.
"""

    return call_llm(
        prompt=prompt,
        response_schema=ReviewOutput,
    )