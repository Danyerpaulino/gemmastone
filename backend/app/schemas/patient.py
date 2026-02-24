from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    provider_id: UUID | None = None
    mrn: str | None = None
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    email: str | None = None
    phone: str | None = None
    contact_preferences: dict[str, Any] | None = None
    phone_verified: bool | None = None
    auth_method: str | None = None
    onboarding_completed: bool | None = None
    onboarding_source: str | None = None
    context_version: int | None = None
    last_context_build: datetime | None = None
    communication_paused: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class PatientCreate(PatientBase):
    pass


class PatientOut(PatientBase):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PatientList(BaseModel):
    items: list[PatientOut]
    total: int
