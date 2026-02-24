from __future__ import annotations

from datetime import datetime

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.crud import patient as patient_crud
from app.db.models import ComplianceLog, PreventionPlan, SmsMessage
from app.db.session import get_db
from app.services.auth import normalize_phone
from app.services.context_builder import enqueue_context_rebuild
from app.services.patient_chat import PatientChatService
from app.services.telnyx_client import TelnyxClient

router = APIRouter()
logger = logging.getLogger(__name__)

OPT_IN_MESSAGE = (
    "Klen AI: You are now subscribed to Klen AI Job Alerts. Message frequency varies. "
    "Msg&data rates may apply. Reply HELP for help, STOP to cancel."
)
OPT_OUT_MESSAGE = (
    "Klen AI: You have successfully unsubscribed and will no longer receive messages. "
    "Reply START to resubscribe."
)
HELP_MESSAGE = "Klen AI: For support, visit klen.ai or email support@klen.ai. Reply STOP to cancel."
UNKNOWN_SENDER_MESSAGE = "Klen AI: Please sign up at https://www.klen.ai/talent to receive job alerts."
COMPLIANCE_THANKS_MESSAGE = "Klen AI: Thanks for the update."
FALLBACK_MESSAGE = "Klen AI: Thanks for your message. We'll follow up soon."


def _dig(data: dict, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _parse_yes_no(text: str) -> bool | None:
    value = text.strip().lower()
    if value in {"1", "yes", "y", "yeah", "yep", "took", "taken"}:
        return True
    if value in {"2", "no", "n", "nope", "skip", "skipped"}:
        return False
    return None


def _is_stop(text: str) -> bool:
    value = text.strip().lower()
    return value in {"stop", "pause", "unsubscribe", "cancel", "end", "quit"}


def _is_start(text: str) -> bool:
    value = text.strip().lower()
    return value in {"start", "unstop", "resume"}


def _is_help(text: str) -> bool:
    value = text.strip().lower()
    return value in {"help", "info"}


def _infer_compliance_channel(db: Session, patient_id, default: str = "diet") -> str:
    last_outbound = (
        db.query(SmsMessage)
        .filter(SmsMessage.patient_id == patient_id, SmsMessage.direction == "outbound")
        .order_by(SmsMessage.created_at.desc())
        .first()
    )
    if not last_outbound:
        return default
    hint = f"{last_outbound.message_type or ''} {last_outbound.content or ''}".lower()
    if any(token in hint for token in ("hydration", "water", "fluid")):
        return "hydration"
    if any(token in hint for token in ("medication", "citrate", "pill", "dose")):
        return "medication"
    return default


def _record_compliance_response(db: Session, patient_id, response: bool) -> None:
    log_date = datetime.utcnow().date()
    log = (
        db.query(ComplianceLog)
        .filter(ComplianceLog.patient_id == patient_id, ComplianceLog.log_date == log_date)
        .first()
    )
    if not log:
        log = ComplianceLog(patient_id=patient_id, log_date=log_date)
        db.add(log)

    channel = _infer_compliance_channel(db, patient_id)
    if channel == "hydration":
        plan = (
            db.query(PreventionPlan)
            .filter(PreventionPlan.patient_id == patient_id)
            .order_by(PreventionPlan.created_at.desc())
            .first()
        )
        target = plan.fluid_intake_target_ml if plan and plan.fluid_intake_target_ml else None
        log.fluid_intake_ml = target if response and target is not None else 0
    elif channel == "medication":
        log.medication_taken = response
    else:
        log.dietary_compliance_score = 1.0 if response else 0.0
    log.notes = "Auto logged from SMS response"
    db.add(log)


@router.post("/inbound")
async def telnyx_inbound_sms(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload = await request.json()
    event_type = _dig(payload, "data", "event_type") or payload.get("event_type")
    if event_type and not str(event_type).startswith("message.received"):
        return {"status": "ignored"}

    message_id = (
        _dig(payload, "data", "payload", "id")
        or _dig(payload, "data", "payload", "message_id")
    )
    text = (
        _dig(payload, "data", "payload", "text")
        or _dig(payload, "data", "payload", "body")
        or ""
    )
    from_number = (
        _dig(payload, "data", "payload", "from", "phone_number")
        or _dig(payload, "data", "payload", "from")
    )
    media = _dig(payload, "data", "payload", "media") or []
    media_urls = [item.get("url") for item in media if isinstance(item, dict) and item.get("url")]

    normalized = normalize_phone(from_number or "") if from_number else ""
    patient = patient_crud.get_patient_by_phone(db, normalized) if normalized else None

    if message_id:
        existing = (
            db.query(SmsMessage)
            .filter(SmsMessage.telnyx_message_id == message_id)
            .first()
        )
        if existing:
            return {"status": "duplicate"}

    message_type = "photo" if media_urls else "question"
    inbound_message = SmsMessage(
        patient_id=patient.id if patient else None,
        telnyx_message_id=message_id,
        direction="inbound",
        message_type=message_type,
        content=text,
        media_urls=media_urls or None,
        status="received",
    )
    if patient:
        db.add(inbound_message)

    response_text = None
    response_type = "response"
    compliance = _parse_yes_no(text) if text else None
    if _is_stop(text):
        if patient:
            patient.communication_paused = True
            prefs = dict(patient.contact_preferences or {})
            prefs["sms"] = False
            patient.contact_preferences = prefs
            db.add(patient)
        response_text = OPT_OUT_MESSAGE
    elif _is_start(text):
        if patient:
            patient.communication_paused = False
            prefs = dict(patient.contact_preferences or {})
            prefs["sms"] = True
            patient.contact_preferences = prefs
            db.add(patient)
        response_text = OPT_IN_MESSAGE
    elif _is_help(text):
        response_text = HELP_MESSAGE
    elif patient and compliance is not None:
        _record_compliance_response(db, patient.id, compliance)
        response_text = COMPLIANCE_THANKS_MESSAGE
    elif not patient and normalized:
        response_text = UNKNOWN_SENDER_MESSAGE
    elif patient and text and normalized and not patient.communication_paused:
        try:
            chat_service = PatientChatService(db)
            response_text, _needs_escalation = await chat_service.chat(patient.id, text)
            response_type = "ai_response"
        except Exception:
            logger.exception("Failed to generate SMS auto-response for patient %s", patient.id)
            response_text = FALLBACK_MESSAGE

    if response_text and normalized:
        client = TelnyxClient()
        result = client.send_sms(normalized, response_text)
        if patient:
            outbound = SmsMessage(
                patient_id=patient.id,
                telnyx_message_id=result.message_id,
                direction="outbound",
                message_type=response_type,
                content=response_text,
                status="sent" if client.mode == "mock" else "queued",
                sent_at=datetime.utcnow(),
                delivered_at=datetime.utcnow() if client.mode == "mock" else None,
            )
            db.add(outbound)

    db.commit()
    if patient and normalized:
        should_rebuild = False
        trigger = None
        if media_urls:
            should_rebuild = True
            trigger = "lab_photo"
        elif compliance is None and not _is_stop(text) and not _is_start(text):
            should_rebuild = True
            trigger = "sms_inbound"
        if should_rebuild and trigger:
            enqueue_context_rebuild(
                patient.id,
                trigger,
                {"message": text, "media_urls": media_urls or None},
            )
    return {"status": "ok"}


@router.post("/status")
async def telnyx_sms_status(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload = await request.json()
    event_type = _dig(payload, "data", "event_type") or payload.get("event_type")
    if event_type and not str(event_type).startswith("message."):
        return {"status": "ignored"}

    message_id = (
        _dig(payload, "data", "payload", "id")
        or _dig(payload, "data", "payload", "message_id")
    )
    status = _dig(payload, "data", "payload", "status")
    if not message_id:
        return {"status": "ignored"}

    sms = db.query(SmsMessage).filter(SmsMessage.telnyx_message_id == message_id).first()
    if not sms:
        return {"status": "ignored"}

    if status:
        sms.status = status
        if status == "delivered":
            sms.delivered_at = datetime.utcnow()
    db.add(sms)
    db.commit()
    return {"status": "ok"}
