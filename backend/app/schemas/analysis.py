from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lab_result import LabResultOut


class StoneAnalysisBase(BaseModel):
    patient_id: UUID
    provider_id: UUID

    ct_scan_path: str | None = None
    ct_scan_date: date | None = None

    stones_detected: list[dict[str, Any]] = Field(default_factory=list)
    predicted_composition: str | None = None
    composition_confidence: float | None = None
    stone_3d_model: bytes | None = None

    treatment_recommendation: str | None = None
    treatment_rationale: str | None = None
    urgency_level: str | None = None

    workflow_state: dict[str, Any] | None = None

    provider_approved: bool | None = None
    approved_at: datetime | None = None
    provider_notes: str | None = None


class StoneAnalysisCreate(StoneAnalysisBase):
    pass


class StoneAnalysisOut(StoneAnalysisBase):
    id: UUID
    created_at: datetime | None = None
    lab_results: list[LabResultOut] | None = None

    model_config = ConfigDict(from_attributes=True)


class StoneAnalysisList(BaseModel):
    items: list[StoneAnalysisOut]
    total: int
