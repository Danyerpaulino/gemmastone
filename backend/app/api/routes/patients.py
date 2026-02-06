from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.crud import compliance as compliance_crud
from app.crud import patient as patient_crud
from app.crud import prevention_plan as plan_crud
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.compliance import ComplianceLogList, ComplianceLogOut
from app.schemas.patient import PatientCreate, PatientList, PatientOut
from app.schemas.plan import PreventionPlanOut
from app.services.patient_chat import PatientChatService

router = APIRouter()


@router.post("/", response_model=PatientOut, status_code=201)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
) -> PatientOut:
    return patient_crud.create_patient(db, payload)


@router.get("/", response_model=PatientList)
def list_patients(
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> PatientList:
    items = patient_crud.list_patients(db, offset=offset, limit=limit)
    total = patient_crud.count_patients(db)
    return PatientList(items=items, total=total)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> PatientOut:
    patient = patient_crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/{patient_id}/plan", response_model=PreventionPlanOut | None)
def get_latest_plan(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> PreventionPlanOut | None:
    """Return the newest prevention plan for a patient (or None if missing)."""
    patient = patient_crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    plan = plan_crud.get_latest_plan(db, patient_id)
    if not plan:
        return None
    return PreventionPlanOut.model_validate(plan)


@router.get("/{patient_id}/compliance", response_model=ComplianceLogList)
def list_compliance_logs(
    patient_id: UUID,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> ComplianceLogList:
    """List compliance logs for a patient to power the progress view."""
    patient = patient_crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    logs = compliance_crud.list_compliance_logs(
        db, patient_id=patient_id, offset=offset, limit=limit
    )
    total = compliance_crud.count_compliance_logs(db, patient_id=patient_id)
    return ComplianceLogList(
        items=[ComplianceLogOut.model_validate(log) for log in logs],
        total=total,
    )


@router.post("/{patient_id}/chat", response_model=ChatResponse)
async def chat_patient(
    patient_id: UUID,
    payload: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    service = PatientChatService(db)
    try:
        response, escalated = await service.chat(patient_id, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatResponse(response=response, escalated=escalated)
