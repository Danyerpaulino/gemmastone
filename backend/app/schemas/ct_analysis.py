from typing import Any

from pydantic import BaseModel

from app.schemas.analysis import StoneAnalysisOut
from app.schemas.plan import NudgeCampaignOut, NudgeOut, PreventionPlanOut


class CTAnalysisResponse(BaseModel):
    analysis: StoneAnalysisOut
    prevention_plan: PreventionPlanOut | None = None
    nudge_campaign: NudgeCampaignOut | None = None
    nudges: list[NudgeOut] | None = None
    workflow_state: dict[str, Any] | None = None
