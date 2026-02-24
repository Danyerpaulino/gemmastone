from __future__ import annotations

import json
from datetime import datetime, timedelta, time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.crud import patient as patient_crud
from app.db.models import ComplianceLog, PatientContext, PatientInteraction, ScheduledAction, VoiceCall
from app.db.session import get_db
from app.services.auth import normalize_phone
from app.services.context_builder import enqueue_context_rebuild
from app.services.vapi_prompts import UNKNOWN_CALLER_MESSAGE, build_system_prompt

router = APIRouter()


def _dig(data: dict, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _parse_timestamp(value) -> datetime | None:
    if isinstance(value, str):
        try:
            cleaned = value.strip()
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value)
        except (OverflowError, OSError):
            return None
    return None


def _get_event_type(event: dict) -> str | None:
    return (
        _dig(event, "message", "type")
        or event.get("type")
        or event.get("event_type")
        or event.get("event")
    )


def _get_call(event: dict) -> dict:
    return _dig(event, "message", "call") or event.get("call") or {}


def _get_call_id(call: dict) -> str | None:
    return call.get("id") or call.get("callId") or call.get("call_id")


def _get_call_direction(call: dict) -> str:
    return call.get("direction") or call.get("directionType") or "inbound"


def _get_call_status(call: dict) -> str | None:
    return call.get("status") or call.get("state")


def _get_call_metadata(call: dict) -> dict:
    return _dig(call, "assistantOverrides", "metadata") or call.get("metadata") or {}


def _resolve_patient(db: Session, call: dict):
    metadata = _get_call_metadata(call)
    patient_id = metadata.get("patient_id")
    patient = None
    if patient_id:
        patient = patient_crud.get_patient(db, patient_id)
    if not patient:
        caller = _dig(call, "customer", "number") or _dig(call, "customer", "phoneNumber")
        normalized = normalize_phone(caller) if caller else ""
        if normalized:
            patient = patient_crud.get_patient_by_phone(db, normalized)
    return patient, metadata


def _ensure_voice_call(
    db: Session,
    patient_id,
    call: dict,
    call_type: str,
    direction: str,
    status_value: str | None,
    context_version: int | None = None,
) -> VoiceCall | None:
    call_id = _get_call_id(call)
    if not call_id:
        return None
    voice_call = db.query(VoiceCall).filter(VoiceCall.vapi_call_id == call_id).first()
    started_at = _parse_timestamp(call.get("startedAt") or call.get("started_at"))
    if not voice_call:
        voice_call = VoiceCall(
            patient_id=patient_id,
            vapi_call_id=call_id,
            direction=direction,
            call_type=call_type,
            status=status_value or "initiated",
            started_at=started_at,
            context_version_used=context_version,
        )
        db.add(voice_call)
        db.commit()
        db.refresh(voice_call)
        return voice_call

    updated = False
    if status_value and voice_call.status != status_value:
        voice_call.status = status_value
        updated = True
    if started_at and not voice_call.started_at:
        voice_call.started_at = started_at
        updated = True
    if call_type and voice_call.call_type != call_type:
        voice_call.call_type = call_type
        updated = True
    if context_version is not None and voice_call.context_version_used is None:
        voice_call.context_version_used = context_version
        updated = True
    if updated:
        db.add(voice_call)
        db.commit()
        db.refresh(voice_call)
    return voice_call


def _verify_vapi_secret(request: Request) -> None:
    settings = get_settings()
    if not settings.vapi_webhook_secret:
        return
    provided = request.headers.get("x-vapi-secret") or request.headers.get("x-vapi-signature")
    if not provided or provided != settings.vapi_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Vapi webhook secret.")


def _extract_function_call(event: dict) -> dict:
    return (
        _dig(event, "message", "functionCall")
        or _dig(event, "message", "toolCall")
        or event.get("functionCall")
        or event.get("toolCall")
        or {}
    )


def _parse_function_args(arguments):
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "took", "taken"}:
        return True
    if text in {"false", "no", "n", "0", "skip", "skipped"}:
        return False
    return None


def _parse_amount_ml(args: dict) -> int | None:
    for key in ("amount_ml", "amountMl", "ml"):
        if key in args:
            try:
                return int(float(args[key]))
            except (TypeError, ValueError):
                return None
    for key in ("amount_liters", "liters", "l"):
        if key in args:
            try:
                return int(float(args[key]) * 1000)
            except (TypeError, ValueError):
                return None
    return None


def _parse_time(value) -> time | None:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%H:%M").time()
        except ValueError:
            return None
    return None


def _get_or_create_log(db: Session, patient_id) -> ComplianceLog:
    log_date = datetime.utcnow().date()
    log = (
        db.query(ComplianceLog)
        .filter(ComplianceLog.patient_id == patient_id, ComplianceLog.log_date == log_date)
        .first()
    )
    if not log:
        log = ComplianceLog(patient_id=patient_id, log_date=log_date)
        db.add(log)
    return log


def _record_interaction(db: Session, patient_id, content: str) -> None:
    interaction = PatientInteraction(
        patient_id=patient_id,
        channel="voice",
        direction="inbound",
        content=content,
    )
    db.add(interaction)


@router.post("")
async def vapi_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    _verify_vapi_secret(request)
    event = await request.json()
    event_type = _get_event_type(event)

    if event_type in {"assistant-request", "assistant_request"}:
        return await _handle_assistant_request(event, db)
    if event_type in {"end-of-call-report", "end_of_call_report", "end-of-call"}:
        return await _handle_call_end(event, db)
    if event_type in {"status-update", "status_update"}:
        return await _handle_status_update(event, db)
    if event_type in {"function-call", "function_call"}:
        return await _handle_function_call(event, db)

    return {"status": "ignored"}


@router.post("/function")
async def vapi_function_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    _verify_vapi_secret(request)
    event = await request.json()
    return await _handle_function_call(event, db)


async def _handle_assistant_request(event: dict, db: Session) -> dict:
    settings = get_settings()
    call = _get_call(event)
    patient, metadata = _resolve_patient(db, call)
    call_type = (metadata.get("call_type") if metadata else None) or "inbound"
    direction = _get_call_direction(call)
    status_value = _get_call_status(call) or "initiated"

    if not patient:
        system_message = UNKNOWN_CALLER_MESSAGE
        return {
            "assistant": {
                "model": {
                    "provider": "openai",
                    "model": settings.vapi_model,
                    "messages": [{"role": "system", "content": system_message}],
                }
            }
        }

    ctx = (
        db.query(PatientContext)
        .filter(PatientContext.patient_id == patient.id)
        .first()
    )
    context = ctx.context if ctx else None
    context_version = ctx.version if ctx else patient.context_version

    _ensure_voice_call(
        db,
        patient.id,
        call,
        call_type=call_type,
        direction=direction,
        status_value=status_value,
        context_version=context_version,
    )
    system_message = build_system_prompt(context=context, call_type=call_type)

    return {
        "assistant": {
            "model": {
                "provider": "openai",
                "model": settings.vapi_model,
                "messages": [{"role": "system", "content": system_message}],
            }
        }
    }


async def _handle_call_end(event: dict, db: Session) -> dict:
    call = _get_call(event)
    call_id = _get_call_id(call)
    if not call_id:
        return {"status": "ignored"}

    voice_call = db.query(VoiceCall).filter(VoiceCall.vapi_call_id == call_id).first()
    if not voice_call:
        patient, metadata = _resolve_patient(db, call)
        if not patient:
            return {"status": "ignored"}
        call_type = (metadata.get("call_type") if metadata else None) or "inbound"
        voice_call = _ensure_voice_call(
            db,
            patient.id,
            call,
            call_type=call_type,
            direction=_get_call_direction(call),
            status_value="completed",
            context_version=patient.context_version,
        )
    if not voice_call:
        return {"status": "ignored"}

    analysis = _dig(event, "message", "analysis") or {}
    transcript = (
        _dig(analysis, "transcript")
        or _dig(event, "message", "transcript")
        or _dig(event, "transcript")
    )
    summary = (
        _dig(analysis, "summary")
        or _dig(event, "message", "summary")
        or _dig(event, "summary")
    )
    segments = (
        _dig(analysis, "transcriptSegments")
        or _dig(event, "message", "transcriptSegments")
        or _dig(event, "transcriptSegments")
    )
    duration = (
        _dig(event, "message", "durationSeconds")
        or _dig(event, "message", "duration")
        or call.get("duration")
    )

    if transcript is not None and not isinstance(transcript, str):
        transcript = json.dumps(transcript, ensure_ascii=True)
    if summary is not None and not isinstance(summary, str):
        summary = json.dumps(summary, ensure_ascii=True)

    voice_call.status = "completed"
    voice_call.transcript = transcript
    voice_call.summary = summary
    voice_call.transcript_segments = segments
    if duration is not None:
        try:
            voice_call.duration_seconds = int(float(duration))
        except (TypeError, ValueError):
            pass
    voice_call.ended_at = _parse_timestamp(call.get("endedAt") or call.get("ended_at")) or datetime.utcnow()

    db.add(voice_call)
    db.commit()
    enqueue_context_rebuild(
        voice_call.patient_id,
        "call_complete",
        {
            "call_id": voice_call.vapi_call_id,
            "call_type": voice_call.call_type,
            "summary": summary,
        },
    )
    return {"status": "ok"}


async def _handle_status_update(event: dict, db: Session) -> dict:
    call = _get_call(event)
    call_id = _get_call_id(call)
    if not call_id:
        return {"status": "ignored"}
    status_value = _get_call_status(call) or _dig(event, "message", "status")
    voice_call = db.query(VoiceCall).filter(VoiceCall.vapi_call_id == call_id).first()
    if not voice_call:
        return {"status": "ignored"}
    if status_value:
        voice_call.status = status_value
        db.add(voice_call)
        db.commit()
    return {"status": "ok"}


async def _handle_function_call(event: dict, db: Session) -> dict:
    call = _get_call(event)
    function_call = _extract_function_call(event)
    name = function_call.get("name") or _dig(function_call, "function", "name")
    arguments = _parse_function_args(
        function_call.get("arguments") or _dig(function_call, "function", "arguments")
    )

    patient, metadata = _resolve_patient(db, call)
    if not patient or not name:
        return {"result": {"status": "ignored"}}

    call_type = (metadata.get("call_type") if metadata else None) or "inbound"
    _ensure_voice_call(
        db,
        patient.id,
        call,
        call_type=call_type,
        direction=_get_call_direction(call),
        status_value=_get_call_status(call),
        context_version=patient.context_version,
    )

    response_payload: dict[str, object] = {"status": "ok"}

    if name == "log_medication_taken":
        taken = _parse_bool(arguments.get("taken") or arguments.get("value") or arguments.get("status"))
        if taken is not None:
            log = _get_or_create_log(db, patient.id)
            log.medication_taken = taken
            log.notes = "Logged via voice agent"
            db.add(log)
        _record_interaction(db, patient.id, f"medication_taken:{taken}")

    elif name == "log_fluid_intake":
        amount_ml = _parse_amount_ml(arguments)
        if amount_ml is not None:
            log = _get_or_create_log(db, patient.id)
            current = log.fluid_intake_ml or 0
            log.fluid_intake_ml = max(current, amount_ml)
            log.notes = "Logged via voice agent"
            db.add(log)
        _record_interaction(db, patient.id, f"fluid_intake_ml:{amount_ml}")

    elif name == "log_dietary_event":
        food = arguments.get("food") or arguments.get("item") or "diet_update"
        _record_interaction(db, patient.id, f"dietary_event:{food}")

    elif name == "schedule_callback":
        reason = arguments.get("reason") or "patient_update"
        scheduled = ScheduledAction(
            patient_id=patient.id,
            action_type="call",
            scheduled_for=datetime.utcnow() + timedelta(minutes=10),
            recurrence="once",
            payload={"call_type": "callback", "reason": reason},
            status="scheduled",
        )
        db.add(scheduled)
        response_payload["scheduled_for"] = scheduled.scheduled_for.isoformat()
        enqueue_context_rebuild(
            patient.id,
            "schedule_callback",
            {"reason": reason, "call_type": call_type},
        )

    elif name == "escalate_to_provider":
        reason = arguments.get("reason") or "escalation requested"
        voice_call = None
        call_id = _get_call_id(call)
        if call_id:
            voice_call = db.query(VoiceCall).filter(VoiceCall.vapi_call_id == call_id).first()
        if voice_call:
            voice_call.escalated = True
            voice_call.escalation_reason = reason
            db.add(voice_call)
        interaction = PatientInteraction(
            patient_id=patient.id,
            channel="voice",
            direction="inbound",
            content="escalate_to_provider",
            escalated_to_provider=True,
            escalation_reason=reason,
        )
        db.add(interaction)

    elif name == "update_preferences":
        prefs = dict(patient.contact_preferences or {})
        for channel in ("sms", "voice", "email"):
            if channel in arguments:
                prefs[channel] = bool(arguments[channel])
        patient.contact_preferences = prefs
        if "pause" in arguments:
            patient.communication_paused = bool(arguments.get("pause"))
        if "quiet_hours_start" in arguments:
            parsed = _parse_time(arguments.get("quiet_hours_start"))
            if parsed:
                patient.quiet_hours_start = parsed
        if "quiet_hours_end" in arguments:
            parsed = _parse_time(arguments.get("quiet_hours_end"))
            if parsed:
                patient.quiet_hours_end = parsed
        db.add(patient)
        response_payload["preferences"] = prefs

    elif name == "get_dietary_info":
        food = str(arguments.get("food") or arguments.get("item") or "").strip().lower()
        if not food:
            response_payload["answer"] = "Let me know the specific food, and I can help."
        elif food in {"spinach", "almonds", "rhubarb", "beets"}:
            response_payload["answer"] = (
                f"{food.title()} is higher in oxalate. Keep portions small and balance with fluids."
            )
        else:
            response_payload["answer"] = f"For {food}, aim for moderation and plenty of fluids."

    else:
        response_payload = {"status": "unhandled", "name": name}

    db.commit()
    return {"result": response_payload}
