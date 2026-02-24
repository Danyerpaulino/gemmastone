from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextRebuildRequest(BaseModel):
    trigger: str | None = None
    event_data: dict[str, Any] | None = None


class PatientContextOut(BaseModel):
    id: UUID
    patient_id: UUID
    context: dict[str, Any]
    version: int
    built_at: datetime | None = None
    trigger: str | None = None
    processing_time_ms: int | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ContextBuildOut(BaseModel):
    id: UUID
    patient_id: UUID
    trigger: str
    version: int
    status: str | None = None
    input_summary: dict[str, Any] | None = None
    processing_time_ms: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ContextBuildList(BaseModel):
    items: list[ContextBuildOut]
    total: int
