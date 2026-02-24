from __future__ import annotations

import calendar
import logging
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.models import Patient, ScheduledAction, SmsMessage, VoiceCall
from app.services.context_builder import enqueue_context_rebuild
from app.services.telnyx_client import TelnyxClient
from app.services.vapi_client import VapiClient

logger = logging.getLogger(__name__)


def create_default_schedule(
    db: Session,
    patient: Patient,
    now: datetime | None = None,
) -> list[ScheduledAction]:
    existing = (
        db.query(ScheduledAction)
        .filter(ScheduledAction.patient_id == patient.id)
        .first()
    )
    if existing:
        return []

    now = now or datetime.utcnow()
    settings = get_settings()
    base_url = settings.frontend_base_url.rstrip("/")
    send_scheduled_sms = not settings.disable_scheduled_sms

    plan_url = f"{base_url}/plan" if base_url else ""
    labs_url = f"{base_url}/labs" if base_url else ""

    actions: list[ScheduledAction] = []

    actions.append(
        ScheduledAction(
            patient_id=patient.id,
            action_type="call",
            scheduled_for=now + timedelta(minutes=1),
            recurrence="once",
            payload={"call_type": "intake", "source": "default"},
            status="scheduled",
        )
    )

    plan_message = "Klen AI: Your prevention plan is ready."
    if plan_url:
        plan_message = f"{plan_message} View it here: {plan_url}."
    plan_message = f"{plan_message} Save this number for anytime questions."
    if send_scheduled_sms:
        actions.append(
            ScheduledAction(
                patient_id=patient.id,
                action_type="sms",
                scheduled_for=now + timedelta(hours=2),
                recurrence="once",
                payload={
                    "message_type": "plan_delivery",
                    "message": plan_message,
                    "source": "default",
                },
                status="scheduled",
            )
        )

    if send_scheduled_sms:
        actions.append(
            ScheduledAction(
                patient_id=patient.id,
                action_type="sms",
                scheduled_for=_next_time_of_day(now, 8, 0),
                recurrence="daily",
                payload={
                    "message_type": "medication_reminder",
                    "message": "Klen AI: Time for your potassium citrate. Reply took it or skipped.",
                    "source": "default",
                },
                status="scheduled",
            )
        )

    if send_scheduled_sms:
        actions.append(
            ScheduledAction(
                patient_id=patient.id,
                action_type="sms",
                scheduled_for=_next_time_of_day(now, 12, 0),
                recurrence="daily",
                payload={
                    "message_type": "hydration_check",
                    "message": "Klen AI: Hydration check: how is your water intake today? Goal 2.5L.",
                    "source": "default",
                },
                status="scheduled",
            )
        )

    if send_scheduled_sms:
        actions.append(
            ScheduledAction(
                patient_id=patient.id,
                action_type="sms",
                scheduled_for=_next_time_of_day(now, 18, 0),
                recurrence="daily",
                payload={
                    "message_type": "hydration_check",
                    "message": "Klen AI: Evening hydration check: did you reach your water goal?",
                    "source": "default",
                },
                status="scheduled",
            )
        )

    if send_scheduled_sms:
        actions.append(
            ScheduledAction(
                patient_id=patient.id,
                action_type="sms",
                scheduled_for=_next_weekday_time(now, 5, 10, 0),
                recurrence="weekly",
                payload={
                    "message_type": "diet_tip",
                    "message": "Klen AI: Weekly tip: limit high-oxalate foods like spinach and almonds.",
                    "source": "default",
                },
                status="scheduled",
            )
        )

    actions.append(
        ScheduledAction(
            patient_id=patient.id,
            action_type="call",
            scheduled_for=_next_month_day_time(now, 1, 10, 0),
            recurrence="monthly",
            payload={"call_type": "follow_up", "source": "default"},
            status="scheduled",
        )
    )

    record_message = "Klen AI: Want more personalized advice?"
    if labs_url:
        record_message = f"{record_message} Sync your records here: {labs_url}."
    if send_scheduled_sms:
        actions.append(
            ScheduledAction(
                patient_id=patient.id,
                action_type="sms",
                scheduled_for=_days_from_now_at(now, 14, 10, 0),
                recurrence="once",
                payload={
                    "message_type": "record_sync",
                    "message": record_message,
                    "source": "default",
                },
                status="scheduled",
            )
        )

    for action in actions:
        db.add(action)
    db.commit()
    return actions


class ScheduledActionDispatcher:
    def __init__(
        self,
        db: Session,
        telnyx: TelnyxClient | None = None,
        vapi: VapiClient | None = None,
    ) -> None:
        self.db = db
        self.telnyx = telnyx or TelnyxClient()
        self.vapi = vapi or VapiClient()

    def dispatch_due(self, limit: int = 50, dry_run: bool = False) -> list[ScheduledAction]:
        now = datetime.utcnow()
        query = (
            self.db.query(ScheduledAction)
            .filter(
                ScheduledAction.status == "scheduled",
                ScheduledAction.scheduled_for <= now,
            )
            .order_by(ScheduledAction.scheduled_for.asc())
            .limit(limit)
        )
        try:
            query = query.with_for_update(skip_locked=True)
        except Exception:
            pass

        actions = query.all()
        if dry_run or not actions:
            return actions

        for action in actions:
            action.status = "processing"
            self.db.add(action)
        self.db.commit()

        for action in actions:
            try:
                self._process_action(action)
            except Exception:
                logger.exception("Scheduled action failed: %s", action.id)
                self._mark_failed(action, "exception")

        self.db.commit()
        return actions

    def _process_action(self, action: ScheduledAction) -> None:
        settings = get_settings()
        if action.action_type == "sms" and settings.disable_scheduled_sms:
            self._mark_skipped(action, "scheduled_sms_disabled")
            return

        patient = (
            self.db.query(Patient)
            .filter(Patient.id == action.patient_id)
            .first()
        )
        if not patient:
            self._mark_failed(action, "patient_not_found")
            return

        now = datetime.utcnow()
        if action.action_type in {"sms", "call"}:
            if patient.communication_paused:
                self._mark_skipped(action, "communication_paused", schedule_next=True)
                return
            if not _channel_allowed(patient, action.action_type, action.payload):
                self._mark_skipped(action, "channel_disabled", schedule_next=True)
                return
            if not patient.phone:
                self._mark_failed(action, "missing_phone", schedule_next=True)
                return
            next_allowed = _next_allowed_time(patient, now)
            if next_allowed:
                action.status = "scheduled"
                action.scheduled_for = next_allowed
                action.executed_at = None
                action.result = {
                    "status": "deferred",
                    "reason": "quiet_hours",
                    "scheduled_for": next_allowed.isoformat(),
                }
                self.db.add(action)
                return

        if action.action_type == "sms":
            self._send_sms_action(action, patient)
        elif action.action_type == "call":
            self._send_call_action(action, patient)
        elif action.action_type == "context_rebuild":
            self._enqueue_context_action(action, patient)
        else:
            self._mark_failed(action, "unknown_action_type")

    def _send_sms_action(self, action: ScheduledAction, patient: Patient) -> None:
        payload = dict(action.payload or {})
        message = payload.get("message") or payload.get("content")
        if not message:
            self._mark_failed(action, "missing_message", schedule_next=True)
            return

        media_urls = payload.get("media_urls")
        message_type = payload.get("message_type") or payload.get("type")

        result = self.telnyx.send_sms(patient.phone, message, media_urls=media_urls)
        now = datetime.utcnow()
        status = "sent" if self.telnyx.mode == "mock" else (result.status or "queued")

        sms = SmsMessage(
            patient_id=patient.id,
            telnyx_message_id=result.message_id,
            direction="outbound",
            message_type=message_type,
            content=message,
            media_urls=media_urls or None,
            status=status,
            sent_at=now,
            delivered_at=now if self.telnyx.mode == "mock" else None,
        )
        self.db.add(sms)

        action.status = "sent"
        action.executed_at = now
        action.result = {
            "status": status,
            "message_id": result.message_id,
            "message_type": message_type,
        }
        self.db.add(action)
        self._schedule_next(action)

    def _send_call_action(self, action: ScheduledAction, patient: Patient) -> None:
        payload = dict(action.payload or {})
        call_type = payload.pop("call_type", None) or "follow_up"
        metadata = dict(payload.get("metadata") or {})
        if "reason" in payload:
            metadata.setdefault("reason", payload.get("reason"))
        for key in ("call_type", "message", "message_type", "media_urls", "source", "force"):
            metadata.pop(key, None)

        result = self.vapi.create_call(
            patient.phone,
            patient_id=str(patient.id),
            call_type=call_type,
            metadata=metadata or None,
        )
        now = datetime.utcnow()

        voice_call = VoiceCall(
            patient_id=patient.id,
            vapi_call_id=result.call_id,
            direction="outbound",
            call_type=call_type,
            status=result.status or "queued",
            started_at=now,
            context_version_used=patient.context_version,
        )
        self.db.add(voice_call)

        action.status = "sent"
        action.executed_at = now
        action.result = {
            "status": result.status or "queued",
            "call_id": result.call_id,
            "call_type": call_type,
        }
        self.db.add(action)
        self._schedule_next(action)

    def _enqueue_context_action(self, action: ScheduledAction, patient: Patient) -> None:
        payload = dict(action.payload or {})
        trigger = payload.get("trigger") or "scheduled"
        enqueue_context_rebuild(patient.id, trigger, payload or None)
        now = datetime.utcnow()
        action.status = "completed"
        action.executed_at = now
        action.result = {"status": "queued", "trigger": trigger}
        self.db.add(action)
        self._schedule_next(action)

    def _mark_failed(
        self,
        action: ScheduledAction,
        reason: str,
        schedule_next: bool = False,
    ) -> None:
        now = datetime.utcnow()
        action.status = "failed"
        action.executed_at = now
        action.result = {"status": "failed", "reason": reason}
        self.db.add(action)
        if schedule_next:
            self._schedule_next(action)

    def _mark_skipped(
        self,
        action: ScheduledAction,
        reason: str,
        schedule_next: bool = False,
    ) -> None:
        now = datetime.utcnow()
        action.status = "skipped"
        action.executed_at = now
        action.result = {"status": "skipped", "reason": reason}
        self.db.add(action)
        if schedule_next:
            self._schedule_next(action)

    def _schedule_next(self, action: ScheduledAction) -> None:
        next_time = _next_recurrence_time(action.scheduled_for, action.recurrence)
        if not next_time:
            return
        new_action = ScheduledAction(
            patient_id=action.patient_id,
            action_type=action.action_type,
            scheduled_for=next_time,
            recurrence=action.recurrence,
            payload=dict(action.payload or {}),
            status="scheduled",
        )
        self.db.add(new_action)


def _next_time_of_day(now: datetime, hour: int, minute: int = 0) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _next_weekday_time(now: datetime, weekday: int, hour: int, minute: int = 0) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (weekday - now.weekday()) % 7
    candidate = candidate + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _next_month_day_time(now: datetime, day: int, hour: int, minute: int = 0) -> datetime:
    candidate = _safe_month_datetime(now.year, now.month, day, hour, minute)
    if candidate <= now:
        year, month = _increment_month(now.year, now.month)
        candidate = _safe_month_datetime(year, month, day, hour, minute)
    return candidate


def _days_from_now_at(now: datetime, days: int, hour: int, minute: int = 0) -> datetime:
    candidate = now + timedelta(days=days)
    return candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _safe_month_datetime(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(day, last_day), hour, minute)


def _increment_month(year: int, month: int) -> tuple[int, int]:
    month += 1
    if month > 12:
        return year + 1, 1
    return year, month


def _next_recurrence_time(
    scheduled_for: datetime | None,
    recurrence: str | None,
) -> datetime | None:
    if not recurrence or recurrence == "once":
        return None
    base = scheduled_for or datetime.utcnow()
    if recurrence == "daily":
        return base + timedelta(days=1)
    if recurrence == "weekly":
        return base + timedelta(weeks=1)
    if recurrence == "monthly":
        year, month = _increment_month(base.year, base.month)
        return _safe_month_datetime(year, month, base.day, base.hour, base.minute)
    return None


def _channel_allowed(
    patient: Patient,
    action_type: str,
    payload: dict | None,
) -> bool:
    force = bool((payload or {}).get("force"))
    if force:
        return True
    prefs = patient.contact_preferences or {}
    if action_type == "sms":
        return bool(prefs.get("sms", True))
    if action_type == "call":
        return bool(prefs.get("voice", True))
    return True


def _next_allowed_time(patient: Patient, now: datetime) -> datetime | None:
    start: time | None = patient.quiet_hours_start
    end: time | None = patient.quiet_hours_end
    if not start or not end or start == end:
        return None

    now_time = now.time()
    if start < end:
        if start <= now_time < end:
            return datetime.combine(now.date(), end)
        return None

    if now_time >= start:
        return datetime.combine(now.date() + timedelta(days=1), end)
    if now_time < end:
        return datetime.combine(now.date(), end)
    return None
