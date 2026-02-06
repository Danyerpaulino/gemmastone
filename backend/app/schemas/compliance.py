from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ComplianceLogBase(BaseModel):
    patient_id: UUID
    log_date: date
    fluid_intake_ml: int | None = None
    medication_taken: bool | None = None
    dietary_compliance_score: float | None = None
    notes: str | None = None


class ComplianceLogOut(ComplianceLogBase):
    id: UUID
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ComplianceLogList(BaseModel):
    items: list[ComplianceLogOut]
    total: int
