from __future__ import annotations

import json
from typing import Sequence

from sqlalchemy.orm import Session

from app.db.models import Patient, PatientContext, PatientInteraction, PreventionPlan, StoneAnalysis
from app.services.medgemma_client import MedGemmaClient


ESCALATION_KEYWORDS = (
    "fever",
    "can't urinate",
    "cannot urinate",
    "severe pain",
    "blood clots",
    "vomiting",
    "emergency",
    "hospital",
)


class PatientChatService:
    SYSTEM_PROMPT = (
        "You are a supportive health assistant helping a patient manage kidney stones. "
        "Use clear, plain language and be encouraging. Keep responses short (2-4 sentences). "
        "If the patient describes emergency symptoms, advise them to contact their care team."
    )

    def __init__(self, db: Session, medgemma: MedGemmaClient | None = None):
        self.db = db
        self.medgemma = medgemma or MedGemmaClient()

    async def chat(self, patient_id, message: str) -> tuple[str, bool]:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise ValueError("Patient not found")

        plan = (
            self.db.query(PreventionPlan)
            .filter(PreventionPlan.patient_id == patient.id)
            .order_by(PreventionPlan.created_at.desc())
            .first()
        )

        analysis = (
            self.db.query(StoneAnalysis)
            .filter(StoneAnalysis.patient_id == patient.id)
            .order_by(StoneAnalysis.created_at.desc())
            .first()
        )

        needs_escalation = _needs_escalation(message, ESCALATION_KEYWORDS)

        context_doc = (
            self.db.query(PatientContext)
            .filter(PatientContext.patient_id == patient.id)
            .first()
        )
        if context_doc:
            context = json.dumps(context_doc.context, indent=2, ensure_ascii=True)
        else:
            context = _build_context(patient, plan, analysis)
        prompt = (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"PATIENT CONTEXT:\n{context}\n\n"
            f"Patient says: {message}\n\nRespond helpfully:"
        )

        try:
            response = await self.medgemma.generate_text(prompt)
        except Exception:
            response = (
                "Thanks for sharing that. Stay hydrated and follow your plan as closely as you can. "
                "If your symptoms worsen, contact your care team right away."
            )

        interaction = PatientInteraction(
            patient_id=patient.id,
            channel="chat",
            direction="inbound",
            content=message,
            ai_response=response,
            escalated_to_provider=needs_escalation,
            escalation_reason="keyword" if needs_escalation else None,
        )
        self.db.add(interaction)
        self.db.commit()

        return response, needs_escalation


def _needs_escalation(message: str, keywords: Sequence[str]) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in keywords)


def _build_context(patient: Patient, plan: PreventionPlan | None, analysis: StoneAnalysis | None) -> str:
    parts = [f"Name: {patient.first_name}"]

    if analysis:
        if analysis.predicted_composition:
            parts.append(f"Stone type: {analysis.predicted_composition}")
        if analysis.treatment_recommendation:
            parts.append(f"Treatment: {analysis.treatment_recommendation}")

    if plan:
        if plan.fluid_intake_target_ml:
            parts.append(f"Fluid goal: {plan.fluid_intake_target_ml}ml daily")
        if plan.dietary_recommendations:
            parts.append("Dietary guidance: personalized plan on file")

    return "\n".join(parts)
