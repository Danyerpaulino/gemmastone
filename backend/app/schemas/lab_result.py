from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LabResultBase(BaseModel):
    patient_id: UUID
    analysis_id: UUID | None = None
    result_type: str
    result_date: date | None = None
    results: dict[str, Any]


class LabResultCreate(LabResultBase):
    pass


class LabResultUpdate(BaseModel):
    analysis_id: UUID | None = None
    result_type: str | None = None
    result_date: date | None = None
    results: dict[str, Any] | None = None


class LabResultOut(LabResultBase):
    id: UUID
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LabResultList(BaseModel):
    items: list[LabResultOut]
    total: int
