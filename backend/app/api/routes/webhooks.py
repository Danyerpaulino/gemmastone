from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.models import Nudge, Patient, PatientInteraction, PreventionPlan
from app.db.session import get_db
from app.services.messaging_service import MessagingService

router = APIRouter()


def _dig(data: dict, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _parse_patient_id(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


@router.post("/comms/sms")
async def comms_sms_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload = await request.json()
    text = (
        _dig(payload, "data", "payload", "text")
        or _dig(payload, "data", "payload", "body")
        or _dig(payload, "data", "payload", "message")
    )
    from_number = (
        _dig(payload, "data", "payload", "from", "phone_number")
        or _dig(payload, "data", "payload", "from")
        or _dig(payload, "data", "payload", "sender")
    )
    client_state = _dig(payload, "data", "payload", "client_state")
    patient_id = _parse_patient_id(client_state)

    patient = None
    if patient_id:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient and from_number:
        patient = db.query(Patient).filter(Patient.phone == from_number).first()

    if not patient:
        return {"status": "ignored"}

    interaction = PatientInteraction(
        patient_id=patient.id,
        channel="sms",
        direction="inbound",
        content=text,
    )
    db.add(interaction)

    nudge = (
        db.query(Nudge)
        .filter(
            Nudge.patient_id == patient.id,
            Nudge.status.in_(["sent", "delivered"]),
        )
        .order_by(Nudge.sent_at.desc().nullslast(), Nudge.scheduled_time.desc())
        .first()
    )
    if nudge:
        nudge.status = "responded"
        nudge.response = text
        nudge.response_at = datetime.utcnow()

    db.commit()
    return {"status": "ok"}


@router.post("/comms/voice/answer")
async def comms_voice_answer(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    payload = await request.json()
    client_state = _dig(payload, "data", "payload", "client_state")
    patient_id = _parse_patient_id(client_state)

    patient = None
    plan = None
    if patient_id:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient:
            plan = (
                db.query(PreventionPlan)
                .filter(PreventionPlan.patient_id == patient.id)
                .order_by(PreventionPlan.created_at.desc())
                .first()
            )

    patient_name = patient.first_name if patient else "there"
    fluid_goal = plan.fluid_intake_target_ml if plan and plan.fluid_intake_target_ml else 2500

    response_xml = MessagingService().generate_voice_response_xml(patient_name, fluid_goal)
    return Response(content=response_xml, media_type="application/xml")


@router.post("/comms/voice/gather")
async def comms_voice_gather(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload = await request.json()
    digits = _dig(payload, "data", "payload", "digits") or _dig(payload, "data", "payload", "dtmf")
    client_state = _dig(payload, "data", "payload", "client_state")
    patient_id = _parse_patient_id(client_state)

    if patient_id:
        interaction = PatientInteraction(
            patient_id=patient_id,
            channel="voice",
            direction="inbound",
            content=str(digits) if digits is not None else None,
        )
        db.add(interaction)
        db.commit()

    return {"status": "ok"}
