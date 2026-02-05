from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PreventionPlanBase(BaseModel):
    analysis_id: UUID
    patient_id: UUID
    dietary_recommendations: list[dict[str, Any]] | None = None
    fluid_intake_target_ml: int | None = None
    medications_recommended: list[dict[str, Any]] | None = None
    lifestyle_modifications: list[str] | None = None
    education_materials: list[dict[str, Any]] | None = None
    personalized_summary: str | None = None
    active: bool | None = None
    superseded_by: UUID | None = None


class PreventionPlanCreate(PreventionPlanBase):
    pass


class PreventionPlanUpdate(BaseModel):
    dietary_recommendations: list[dict[str, Any]] | None = None
    fluid_intake_target_ml: int | None = None
    medications_recommended: list[dict[str, Any]] | None = None
    lifestyle_modifications: list[str] | None = None
    education_materials: list[dict[str, Any]] | None = None
    personalized_summary: str | None = None
    active: bool | None = None
    superseded_by: UUID | None = None


class PreventionPlanOut(PreventionPlanBase):
    id: UUID
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PlanApproval(BaseModel):
    provider_notes: str | None = None
    modifications: PreventionPlanUpdate | None = None


class NudgeCampaignBase(BaseModel):
    patient_id: UUID
    plan_id: UUID
    status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class NudgeCampaignCreate(NudgeCampaignBase):
    pass


class NudgeCampaignOut(NudgeCampaignBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class NudgeBase(BaseModel):
    campaign_id: UUID
    patient_id: UUID
    scheduled_time: datetime
    channel: str
    template: str | None = None
    message_content: str | None = None
    status: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    response: str | None = None
    response_at: datetime | None = None


class NudgeCreate(NudgeBase):
    pass


class NudgeOut(NudgeBase):
    id: UUID
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
