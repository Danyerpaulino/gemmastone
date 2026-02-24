from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import patient as patient_crud
from app.db.models import PatientContext, VoiceCall
from app.db.session import get_db
from app.schemas.voice import VoiceCallList, VoiceCallOut, VoiceCallRequest
from app.services.vapi_client import VapiClient
from app.services.vapi_prompts import build_system_prompt

router = APIRouter()


@router.post("/call/{patient_id}", response_model=VoiceCallOut)
def trigger_outbound_call(
    patient_id: UUID,
    payload: VoiceCallRequest | None = None,
    db: Session = Depends(get_db),
) -> VoiceCallOut:
    patient = patient_crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not patient.phone:
        raise HTTPException(status_code=400, detail="Patient is missing a phone number")

    call_type = payload.call_type if payload and payload.call_type else "intake"
    metadata = payload.metadata if payload else None

    ctx = db.query(PatientContext).filter(PatientContext.patient_id == patient.id).first()
    context = ctx.context if ctx else None
    system_prompt = build_system_prompt(context=context, call_type=call_type)

    client = VapiClient()
    result = client.create_call(
        patient.phone,
        patient_id=str(patient.id),
        call_type=call_type,
        metadata=metadata,
        system_prompt=system_prompt,
    )

    voice_call = VoiceCall(
        patient_id=patient.id,
        vapi_call_id=result.call_id,
        direction="outbound",
        call_type=call_type,
        status=result.status or "queued",
        started_at=datetime.utcnow(),
        context_version_used=patient.context_version,
    )
    db.add(voice_call)
    db.commit()
    db.refresh(voice_call)
    return VoiceCallOut.model_validate(voice_call)


@router.get("/calls/{patient_id}", response_model=VoiceCallList)
def list_calls(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> VoiceCallList:
    patient = patient_crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    calls = (
        db.query(VoiceCall)
        .filter(VoiceCall.patient_id == patient.id)
        .order_by(VoiceCall.created_at.desc())
        .all()
    )
    return VoiceCallList(items=[VoiceCallOut.model_validate(call) for call in calls], total=len(calls))


@router.get("/call/{call_id}", response_model=VoiceCallOut)
def get_call(
    call_id: UUID,
    db: Session = Depends(get_db),
) -> VoiceCallOut:
    voice_call = db.query(VoiceCall).filter(VoiceCall.id == call_id).first()
    if not voice_call:
        raise HTTPException(status_code=404, detail="Call not found")
    return VoiceCallOut.model_validate(voice_call)
