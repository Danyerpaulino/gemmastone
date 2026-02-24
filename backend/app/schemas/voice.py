from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VoiceCallRequest(BaseModel):
    call_type: str | None = None
    metadata: dict | None = None


class VoiceCallOut(BaseModel):
    id: UUID
    patient_id: UUID
    vapi_call_id: str | None = None
    direction: str
    call_type: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    transcript: str | None = None
    summary: str | None = None
    context_version_used: int | None = None
    escalated: bool | None = None
    escalation_reason: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VoiceCallList(BaseModel):
    items: list[VoiceCallOut]
    total: int
