from __future__ import annotations

import json
import os
from typing import Type

from google import genai
from pydantic import BaseModel

from .schemas import (
    IntakeOutput,
    PlanningOutput,
    ReviewOutput,
)


MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        _client = genai.Client(api_key=api_key)

    return _client


def call_llm(
    prompt: str,
    response_schema: Type[BaseModel],
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
        raise RuntimeError("LLM returned an empty response.")

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"LLM returned invalid JSON: {exc}"
        ) from exc

    return response_schema.model_validate(data)


def _format_source_facts(source_facts: list[dict]) -> str:
    """
    Format the persisted source facts so every downstream agent sees
    the CURRENT source version, including user-corrected facts.
    """
    if not source_facts:
        return "No persisted source facts are available."

    return json.dumps(
        source_facts,
        indent=2,
        ensure_ascii=False,
    )


def run_intake(
    transcript: str,
    source_facts: list[dict] | None = None,
) -> IntakeOutput:
    """
    Intake Agent.

    The original transcript remains the source document.

    source_facts represents the current authoritative structured
    source context. If a user corrected a fact, that corrected fact
    must override the previous extracted value.
    """

    current_facts = source_facts or []

    prompt = f"""
You are the Intake Agent in a three-agent operations coordination system.

Your job is to extract grounded information from the meeting transcript.

You must identify:
- decisions
- requirements
- constraints
- missing information
- conflicting information

Rules:
1. Do not invent owners.
2. Do not invent deadlines.
3. Do not invent requirements.
4. Every extracted fact must have a source reference where possible.
5. Clearly flag missing or conflicting information.
6. The original transcript is preserved as the source document.
7. The CURRENT SOURCE FACTS below are authoritative structured context.
8. If a current source fact differs from the original transcript because of
   a user correction, use the corrected value as authoritative.
9. Do not silently revert a corrected fact back to the old transcript value.
10. Preserve uncertainty rather than making assumptions.

ORIGINAL MEETING TRANSCRIPT:
{transcript}

CURRENT SOURCE FACTS:
{_format_source_facts(current_facts)}

Return only the structured IntakeOutput schema.
"""

    return call_llm(
        prompt=prompt,
        response_schema=IntakeOutput,
    )


def run_planning(
    transcript: str,
    intake: IntakeOutput,
    company_rules: str,
    source_facts: list[dict] | None = None,
    corrections: list[dict] | None = None,
) -> PlanningOutput:
    """
    Planning Agent.

    Consumes the CURRENT source facts plus the current Intake output.
    """

    current_facts = source_facts or []
    review_corrections = corrections or []

    prompt = f"""
You are the Planning Agent in a three-agent operations coordination system.

Your job is to convert the Intake Agent's structured information into
an actionable plan.

You must propose:
- tasks
- owners where supported
- deadlines where supported
- dependencies
- the basis for each important planning decision

IMPORTANT:
The CURRENT SOURCE FACTS are authoritative.

If a source fact was corrected by the user, the corrected value must be
used in the plan. Never use a stale value from an earlier agent output.

Rules:
1. Do not present unsupported assumptions as facts.
2. Do not invent owners.
3. Do not invent meeting-supported deadlines.
4. Company rules may create planning requirements, but distinguish those
   from facts stated in the meeting.
5. If company rules conflict with meeting facts, explicitly represent
   the conflict and recommend clarification where appropriate.
6. Incorporate Review Agent corrections.
7. Keep facts, recommendations, and unresolved questions distinguishable.
8. Dependencies should be included where they are logically required.

ORIGINAL MEETING TRANSCRIPT:
{transcript}

CURRENT SOURCE FACTS:
{_format_source_facts(current_facts)}

INTAKE AGENT OUTPUT:
{json.dumps(intake.model_dump(), indent=2, ensure_ascii=False)}

COMPANY RULES:
{company_rules}

REVIEW CORRECTIONS FROM PREVIOUS ATTEMPTS:
{json.dumps(review_corrections, indent=2, ensure_ascii=False)}

Return only the structured PlanningOutput schema.
"""

    return call_llm(
        prompt=prompt,
        response_schema=PlanningOutput,
    )


def run_review(
    transcript: str,
    intake: IntakeOutput,
    plan: PlanningOutput,
    company_rules: str,
    source_facts: list[dict] | None = None,
) -> ReviewOutput:
    """
    Review Agent.

    Checks the current plan against:
    - original transcript
    - current corrected source facts
    - Intake output
    - company rules
    """

    current_facts = source_facts or []

    prompt = f"""
You are the Review Agent in a three-agent operations coordination system.

Your job is to verify whether the Planning Agent's plan is grounded
and compliant.

Check:
- unsupported owners
- unsupported deadlines
- invented requirements
- missing requirements
- conflicts with the source facts
- company-rule violations
- missing dependencies
- incorrect treatment of facts versus recommendations
- unresolved source conflicts

IMPORTANT:
The CURRENT SOURCE FACTS are authoritative.

A user correction represents the current intended source fact.
The original transcript must remain unchanged, but the corrected fact
must be used when evaluating the plan.

If the plan is incorrect:
- return FAIL
- identify the exact problem
- provide a specific correction for the Planning Agent

If the plan is acceptable:
- return PASS
- corrections should be empty

Do not approve a plan merely because an earlier agent produced it.

ORIGINAL MEETING TRANSCRIPT:
{transcript}

CURRENT SOURCE FACTS:
{_format_source_facts(current_facts)}

INTAKE AGENT OUTPUT:
{json.dumps(intake.model_dump(), indent=2, ensure_ascii=False)}

PLANNING AGENT OUTPUT:
{json.dumps(plan.model_dump(), indent=2, ensure_ascii=False)}

COMPANY RULES:
{company_rules}

Return only the structured ReviewOutput schema.
"""

    return call_llm(
        prompt=prompt,
        response_schema=ReviewOutput,
    )