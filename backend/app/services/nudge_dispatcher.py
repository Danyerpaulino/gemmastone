from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Nudge, Patient, PatientInteraction
from app.services.messaging_service import MessagingService


class NudgeDispatcher:
    def __init__(self, db: Session, messaging: MessagingService | None = None):
        self.db = db
        self.messaging = messaging or MessagingService()

    def dispatch_due(self, limit: int = 50, dry_run: bool = False) -> list[Nudge]:
        now = datetime.utcnow()
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
            patient = (
                self.db.query(Patient).filter(Patient.id == nudge.patient_id).first()
            )
            if not patient or not patient.phone:
                nudge.status = "failed"
                nudge.response = "Missing patient phone"
                nudge.response_at = now
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
