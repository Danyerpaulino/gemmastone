from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_patient
from app.core.settings import get_settings
from app.crud import lab_result as lab_crud
from app.crud import patient as patient_crud
from app.crud import prevention_plan as plan_crud
from app.db.models import (
    ComplianceLog,
    ContextBuild,
    LabResult,
    Nudge,
    NudgeCampaign,
    Patient,
    PatientContext,
    PatientInteraction,
    PreventionPlan,
    ScheduledAction,
    SmsMessage,
    StoneAnalysis,
    VoiceCall,
)
from app.db.session import get_db
from app.schemas.compliance import ComplianceLogOut
from app.schemas.lab_result import LabResultList, LabResultOut
from app.schemas.patient import PatientOut
from app.schemas.patient_portal import PatientDashboardOut, PatientPreferencesUpdate
from app.schemas.plan import PreventionPlanOut
from app.services.auth import clear_session
from app.services.redis_client import get_redis

router = APIRouter()


@router.get("/dashboard", response_model=PatientDashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    current_patient=Depends(get_current_patient),
) -> PatientDashboardOut:
    plan = plan_crud.get_latest_plan(db, current_patient.id)
    today_log = (
        db.query(ComplianceLog)
        .filter(
            ComplianceLog.patient_id == current_patient.id,
            ComplianceLog.log_date == date.today(),
        )
        .first()
    )
    latest_lab = lab_crud.get_latest_lab_result(db, current_patient.id)
    return PatientDashboardOut(
        patient=PatientOut.model_validate(current_patient),
        plan=PreventionPlanOut.model_validate(plan) if plan else None,
        today=ComplianceLogOut.model_validate(today_log) if today_log else None,
        latest_lab=LabResultOut.model_validate(latest_lab) if latest_lab else None,
    )


@router.get("/plan", response_model=PreventionPlanOut | None)
def get_current_plan(
    db: Session = Depends(get_db),
    current_patient=Depends(get_current_patient),
) -> PreventionPlanOut | None:
    plan = plan_crud.get_latest_plan(db, current_patient.id)
    if not plan:
        return None
    return PreventionPlanOut.model_validate(plan)


@router.get("/labs", response_model=LabResultList)
def list_lab_results(
    offset: int = 0,
    limit: int = 100,
    result_type: str | None = None,
    db: Session = Depends(get_db),
    current_patient=Depends(get_current_patient),
) -> LabResultList:
    items = lab_crud.list_lab_results(
        db,
        offset=offset,
        limit=limit,
        patient_id=current_patient.id,
        result_type=result_type,
    )
    total = lab_crud.count_lab_results(db, patient_id=current_patient.id, result_type=result_type)
    return LabResultList(
        items=[LabResultOut.model_validate(item) for item in items],
        total=total,
    )


@router.patch("/preferences", response_model=PatientOut)
def update_preferences(
    payload: PatientPreferencesUpdate,
    db: Session = Depends(get_db),
    current_patient=Depends(get_current_patient),
) -> PatientOut:
    updates: dict = {}
    if payload.contact_preferences is not None:
        prefs = dict(current_patient.contact_preferences or {})
        prefs.update(payload.contact_preferences)
        updates["contact_preferences"] = prefs
    if payload.communication_paused is not None:
        updates["communication_paused"] = payload.communication_paused
    if payload.quiet_hours_start is not None:
        updates["quiet_hours_start"] = payload.quiet_hours_start
    if payload.quiet_hours_end is not None:
        updates["quiet_hours_end"] = payload.quiet_hours_end

    if not updates:
        return PatientOut.model_validate(current_patient)

    patient = patient_crud.update_patient(db, current_patient, updates)
    return PatientOut.model_validate(patient)


@router.delete("/account")
def delete_account(
    db: Session = Depends(get_db),
    current_patient=Depends(get_current_patient),
) -> JSONResponse:
    patient_id = current_patient.id

    db.query(Nudge).filter(Nudge.patient_id == patient_id).delete(synchronize_session=False)
    db.query(NudgeCampaign).filter(NudgeCampaign.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(PreventionPlan).filter(PreventionPlan.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(LabResult).filter(LabResult.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(StoneAnalysis).filter(StoneAnalysis.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(PatientInteraction).filter(PatientInteraction.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(ComplianceLog).filter(ComplianceLog.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(VoiceCall).filter(VoiceCall.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(SmsMessage).filter(SmsMessage.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(PatientContext).filter(PatientContext.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(ContextBuild).filter(ContextBuild.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(ScheduledAction).filter(ScheduledAction.patient_id == patient_id).delete(
        synchronize_session=False
    )
    db.query(Patient).filter(Patient.id == patient_id).delete(synchronize_session=False)
    db.commit()

    settings = get_settings()
    clear_session(get_redis(), str(patient_id))
    response = JSONResponse({"status": "deleted"})
    response.delete_cookie(settings.jwt_cookie_name)
    return response
