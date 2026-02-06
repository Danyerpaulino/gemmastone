from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.analysis import StoneAnalysisPublic
from app.schemas.plan import NudgeCampaignOut, NudgeOut, PreventionPlanOut


class CTAnalysisResponse(BaseModel):
    analysis: StoneAnalysisPublic
    prevention_plan: PreventionPlanOut | None = None
    nudge_campaign: NudgeCampaignOut | None = None
    nudges: list[NudgeOut] | None = None
    workflow_state: dict[str, Any] | None = None


class CTSignedUploadRequest(BaseModel):
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None


class CTSignedUploadResponse(BaseModel):
    upload_url: str
    gcs_uri: str
    headers: dict[str, str]
    expires_in: int


class CTAnalyzeUriRequest(BaseModel):
    gcs_uri: str
    patient_id: UUID
    provider_id: UUID
    crystallography_results: dict[str, Any] | None = None
    urine_24hr_results: dict[str, Any] | None = None
