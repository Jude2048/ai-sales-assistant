from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


AgentName = Literal["intake", "planning", "review"]

StepStatus = Literal[
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "STALE",
]

RunStatus = Literal[
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "UNRESOLVED",
]


class SourceReference(BaseModel):
    quote: str
    location: str


class SourceFact(BaseModel):
    fact_id: str
    category: Literal[
        "decision",
        "requirement",
        "constraint",
    ]
    content: str
    source_reference: SourceReference


class IntakeOutput(BaseModel):
    decisions: list[SourceFact] = Field(default_factory=list)
    requirements: list[SourceFact] = Field(default_factory=list)
    constraints: list[SourceFact] = Field(default_factory=list)

    missing_information: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class Task(BaseModel):
    task_id: str
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    dependencies: list[str] = Field(default_factory=list)

    basis: Literal[
        "supported_fact",
        "company_rule",
        "recommendation",
        "unresolved",
    ]


class PlanningOutput(BaseModel):
    tasks: list[Task] = Field(default_factory=list)

    supported_facts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class ReviewCorrection(BaseModel):
    issue: str
    task_id: Optional[str] = None
    correction: str
    evidence: str


class ReviewOutput(BaseModel):
    status: Literal["PASS", "FAIL"]
    corrections: list[ReviewCorrection] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)


class TranscriptInput(BaseModel):
    transcript: str
    company_rules: str
    session_id: str = "demo-session"


class FactCorrectionRequest(BaseModel):
    run_id: str
    session_id: str
    fact_id: str
    new_content: str


class ResumeRequest(BaseModel):
    run_id: str
    session_id: str


class RunRequest(BaseModel):
    transcript: str
    company_rules: str
    session_id: str = "demo-session"
    simulate_failure_at: Optional[AgentName] = None


class AgentStep(BaseModel):
    step_id: str
    run_id: str
    agent: AgentName
    attempt: int

    input_version: int
    output_version: int | None = None

    status: StepStatus

    input_data: dict = Field(default_factory=dict)
    output_data: dict | None = None

    error: str | None = None

    created_at: str
    completed_at: str | None = None


class AgentHandoff(BaseModel):
    handoff_id: str
    run_id: str

    from_agent: AgentName
    to_agent: AgentName

    input_version: int
    output_version: int

    payload: dict = Field(default_factory=dict)

    validation_status: Literal[
        "VALID",
        "INVALID",
    ]


class AgentRun(BaseModel):
    run_id: str
    session_id: str

    source_version: int = 1

    transcript: str
    company_rules: str

    source_facts: list[SourceFact] = Field(default_factory=list)

    steps: list[AgentStep] = Field(default_factory=list)
    handoffs: list[AgentHandoff] = Field(default_factory=list)

    status: RunStatus = "RUNNING"

    final_plan: Optional[PlanningOutput] = None

    review_attempts: int = 0

    simulate_failure_at: Optional[AgentName] = None

    created_at: str
    updated_at: str