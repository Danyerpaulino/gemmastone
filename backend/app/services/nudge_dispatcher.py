from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Nudge, NudgeCampaign, Patient, PatientInteraction, PreventionPlan, StoneAnalysis
from app.core.settings import get_settings
from app.services.messaging_service import MessagingService


class NudgeDispatcher:
    def __init__(self, db: Session, messaging: MessagingService | None = None):
        self.db = db
        self.messaging = messaging or MessagingService()

    def dispatch_due(self, limit: int = 50, dry_run: bool = False) -> list[Nudge]:
        now = datetime.utcnow()
        settings = get_settings()
        nudges = (
            self.db.query(Nudge)
            .filter(Nudge.status == "scheduled", Nudge.scheduled_time <= now)
            .order_by(Nudge.scheduled_time.asc())
            .limit(limit)
            .all()
        )

        if dry_run or not nudges:
            return nudges

        for nudge in nudges:
            if nudge.channel == "sms" and settings.disable_scheduled_sms:
                nudge.status = "skipped"
                nudge.response = "scheduled_sms_disabled"
                nudge.response_at = now
                continue

            patient = (
                self.db.query(Patient).filter(Patient.id == nudge.patient_id).first()
            )
            if not patient or not patient.phone:
                nudge.status = "failed"
                nudge.response = "Missing patient phone"
                nudge.response_at = now
                continue

            if not _is_contact_allowed(patient, nudge.channel):
                nudge.status = "skipped"
                nudge.response = f"Channel disabled in contact preferences: {nudge.channel}"
                nudge.response_at = now
                continue

            if not _is_plan_approved(self.db, nudge):
                # Keep nudges in scheduled state until provider approval.
                continue

            if nudge.channel == "sms":
                self.messaging.send_sms(patient.phone, nudge.message_content or "")
                nudge.status = "sent"
                nudge.sent_at = now
                nudge.delivered_at = now if self.messaging.mode == "mock" else None
            elif nudge.channel == "voice":
                self.messaging.initiate_voice_call(patient.phone, client_state=str(patient.id))
                nudge.status = "sent"
                nudge.sent_at = now
            else:
                nudge.status = "failed"
                nudge.response = f"Unsupported channel: {nudge.channel}"
                nudge.response_at = now
                continue

            interaction = PatientInteraction(
                patient_id=nudge.patient_id,
                channel=nudge.channel,
                direction="outbound",
                content=nudge.message_content,
            )
            self.db.add(interaction)

        self.db.commit()
        return nudges


def _is_contact_allowed(patient: Patient, channel: str) -> bool:
    prefs = patient.contact_preferences or {}
    if channel == "sms":
        return bool(prefs.get("sms", True))
    if channel == "voice":
        return bool(prefs.get("voice", False))
    if channel == "email":
        return bool(prefs.get("email", False))
    return False


def _is_plan_approved(db: Session, nudge: Nudge) -> bool:
    campaign = (
        db.query(NudgeCampaign).filter(NudgeCampaign.id == nudge.campaign_id).first()
    )
    if not campaign or campaign.status not in {"active", "scheduled", "running"}:
        return False

    plan = db.query(PreventionPlan).filter(PreventionPlan.id == campaign.plan_id).first()
    if not plan:
        return False

    analysis = (
        db.query(StoneAnalysis).filter(StoneAnalysis.id == plan.analysis_id).first()
    )
    if not analysis:
        return False

    return bool(analysis.provider_approved)
