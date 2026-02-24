from datetime import time

from pydantic import BaseModel

from app.schemas.compliance import ComplianceLogOut
from app.schemas.lab_result import LabResultOut
from app.schemas.patient import PatientOut
from app.schemas.plan import PreventionPlanOut


class PatientPreferencesUpdate(BaseModel):
    contact_preferences: dict[str, bool] | None = None
    communication_paused: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class PatientDashboardOut(BaseModel):
    patient: PatientOut
    plan: PreventionPlanOut | None = None
    today: ComplianceLogOut | None = None
    latest_lab: LabResultOut | None = None
