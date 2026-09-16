from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Channel = Literal["instagram", "whatsapp", "email"]


class Message(BaseModel):
    conversation_id: str
    lead_id: str
    channel: Channel
    sender_id: str
    sender_name: str | None = None
    direction: Literal["inbound", "outbound"]
    content: str
    provider_message_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    conversation_id: str
    lead_id: str
    channel: Channel
    sender_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Qualification(BaseModel):
    status: Literal["qualified", "not_qualified", "needs_information"]
    evidence: list[str] = Field(default_factory=list)


class Assignment(BaseModel):
    representative: str | None = None
    reason: str | None = None


class Lead(BaseModel):
    lead_id: str
    channel: Channel
    sender_id: str
    sender_name: str | None = None
    status: Literal[
        "new",
        "needs_information",
        "qualified",
        "not_qualified",
        "booked",
    ] = "new"
    qualification: Qualification | None = None
    assignment: Assignment | None = None
    automation_enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)