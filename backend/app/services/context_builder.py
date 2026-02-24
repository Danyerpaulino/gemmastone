from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.models import (
    ComplianceLog,
    ContextBuild,
    LabResult,
    Patient,
    PatientContext,
    PreventionPlan,
    SmsMessage,
    StoneAnalysis,
    VoiceCall,
)
from app.db.session import SessionLocal
from app.services.medgemma_client import MedGemmaClient

logger = logging.getLogger(__name__)

MAX_CALLS = 5
MAX_MESSAGES = 12
MAX_LABS = 20
MAX_TEXT_LEN = 1200


def enqueue_context_rebuild(patient_id, trigger: str, event_data: dict | None = None) -> bool:
    settings = get_settings()
    mode = getattr(settings, "context_rebuild_mode", "async")
    if mode == "disabled":
        return False
    if mode == "sync":
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _run_context_rebuild_sync(patient_id, trigger, event_data)
            return True
        loop.create_task(_rebuild_context_task(patient_id, trigger, event_data))
        return True

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        thread = threading.Thread(
            target=_run_context_rebuild_sync,
            args=(patient_id, trigger, event_data),
            daemon=True,
        )
        thread.start()
        return True

    loop.create_task(_rebuild_context_task(patient_id, trigger, event_data))
    return True


def _run_context_rebuild_sync(patient_id, trigger: str, event_data: dict | None) -> None:
    asyncio.run(_rebuild_context_task(patient_id, trigger, event_data))


async def _rebuild_context_task(patient_id, trigger: str, event_data: dict | None) -> None:
    db = SessionLocal()
    try:
        builder = ContextBuilder(db)
        await builder.build_context(patient_id, trigger, event_data)

        # After a completed intake call, generate a prevention plan if none exists
        if (
            trigger == "call_complete"
            and isinstance(event_data, dict)
            and event_data.get("call_type") == "intake"
        ):
            await _maybe_generate_intake_plan(db, patient_id, event_data)
    except Exception:
        logger.exception("Context rebuild failed for patient %s", patient_id)
    finally:
        db.close()


async def _maybe_generate_intake_plan(
    db: Session, patient_id, event_data: dict
) -> None:
    """Generate a prevention plan from intake call data if no active plan exists."""
    from app.services.plan_generator import generate_intake_plan

    existing_plan = (
        db.query(PreventionPlan)
        .filter(
            PreventionPlan.patient_id == patient_id,
            PreventionPlan.active == True,  # noqa: E712
        )
        .first()
    )
    if existing_plan:
        logger.info(
            "Patient %s already has active plan %s — skipping intake plan generation",
            patient_id,
            existing_plan.id,
        )
        return

    transcript = event_data.get("transcript", "")
    summary = event_data.get("summary", "")
    if not transcript and not summary:
        logger.warning("No transcript or summary in intake event_data for patient %s", patient_id)
        return

    try:
        plan = await generate_intake_plan(db, patient_id, transcript, summary)
        logger.info("Intake prevention plan %s created for patient %s", plan.id, patient_id)
    except Exception:
        logger.exception("Failed to generate intake plan for patient %s", patient_id)


class ContextBuilder:
    def __init__(self, db: Session, medgemma: MedGemmaClient | None = None) -> None:
        self.db = db
        self.medgemma = medgemma or MedGemmaClient()

    async def build_context(
        self,
        patient_id,
        trigger: str,
        event_data: dict | None = None,
    ) -> PatientContext:
        start = time.time()
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
        labs = (
            self.db.query(LabResult)
            .filter(LabResult.patient_id == patient.id)
            .order_by(LabResult.result_date.desc().nullslast(), LabResult.created_at.desc())
            .limit(MAX_LABS)
            .all()
        )
        since_date = datetime.utcnow().date() - timedelta(days=7)
        compliance_logs = (
            self.db.query(ComplianceLog)
            .filter(ComplianceLog.patient_id == patient.id, ComplianceLog.log_date >= since_date)
            .order_by(ComplianceLog.log_date.desc())
            .all()
        )
        voice_calls = (
            self.db.query(VoiceCall)
            .filter(VoiceCall.patient_id == patient.id)
            .order_by(VoiceCall.created_at.desc())
            .limit(MAX_CALLS)
            .all()
        )
        sms_messages = (
            self.db.query(SmsMessage)
            .filter(SmsMessage.patient_id == patient.id)
            .order_by(SmsMessage.created_at.desc())
            .limit(MAX_MESSAGES)
            .all()
        )

        existing = (
            self.db.query(PatientContext)
            .filter(PatientContext.patient_id == patient.id)
            .first()
        )
        next_version = (existing.version + 1) if existing else 1

        input_summary = _build_input_summary(
            trigger=trigger,
            event_data=event_data,
            labs=labs,
            voice_calls=voice_calls,
            sms_messages=sms_messages,
            compliance_logs=compliance_logs,
        )

        build = ContextBuild(
            patient_id=patient.id,
            trigger=trigger or "manual",
            version=next_version,
            status="processing",
            input_summary=input_summary,
        )
        self.db.add(build)
        self.db.commit()
        self.db.refresh(build)

        adherence_snapshot = _compute_adherence_snapshot(compliance_logs, plan)
        priming = _compute_priming(voice_calls, sms_messages)

        prompt = _build_prompt(
            patient=patient,
            plan=plan,
            analysis=analysis,
            labs=labs,
            compliance_logs=compliance_logs,
            voice_calls=voice_calls,
            sms_messages=sms_messages,
            trigger=trigger,
            event_data=event_data,
            adherence_snapshot=adherence_snapshot,
            priming=priming,
            version=next_version,
        )

        raw_output = None
        context = None
        error_message = None
        try:
            raw_output = await self.medgemma.generate_text(prompt)
            context = _parse_context(raw_output)
        except Exception as exc:
            error_message = str(exc)

        if not isinstance(context, dict):
            context = _fallback_context(
                patient=patient,
                plan=plan,
                analysis=analysis,
                labs=labs,
                adherence_snapshot=adherence_snapshot,
                priming=priming,
                version=next_version,
            )
            if not error_message:
                error_message = "medgemma_output_invalid"

        context = _normalize_context(
            context=context,
            patient=patient,
            version=next_version,
            adherence_snapshot=adherence_snapshot,
            priming=priming,
        )

        now = datetime.utcnow()
        processing_ms = int((time.time() - start) * 1000)

        if existing:
            existing.context = context
            existing.version = next_version
            existing.built_at = now
            existing.trigger = trigger
            existing.processing_time_ms = processing_ms
            patient_context = existing
        else:
            patient_context = PatientContext(
                patient_id=patient.id,
                context=context,
                version=next_version,
                built_at=now,
                trigger=trigger,
                processing_time_ms=processing_ms,
            )
            self.db.add(patient_context)

        patient.context_version = next_version
        patient.last_context_build = now
        self.db.add(patient)

        build.status = "complete"
        build.processing_time_ms = processing_ms
        if error_message:
            build.error_message = error_message
        self.db.add(build)

        self.db.commit()
        self.db.refresh(patient_context)
        return patient_context


def _build_input_summary(
    trigger: str,
    event_data: dict | None,
    labs: list[LabResult],
    voice_calls: list[VoiceCall],
    sms_messages: list[SmsMessage],
    compliance_logs: list[ComplianceLog],
) -> dict[str, Any]:
    summary = {
        "trigger": trigger,
        "counts": {
            "labs": len(labs),
            "voice_calls": len(voice_calls),
            "sms_messages": len(sms_messages),
            "compliance_logs_7d": len(compliance_logs),
        },
    }
    if labs:
        summary["latest_lab_date"] = _iso_date(labs[0].result_date)
    if voice_calls:
        summary["latest_call"] = _iso_datetime(voice_calls[0].ended_at or voice_calls[0].started_at)
    if sms_messages:
        summary["latest_sms"] = _iso_datetime(sms_messages[0].created_at)
    if event_data:
        summary["event_data"] = _truncate_value(event_data, 600)
    return summary


def _compute_adherence_snapshot(
    logs: list[ComplianceLog], plan: PreventionPlan | None
) -> dict[str, Any]:
    medication_values = [1.0 if log.medication_taken else 0.0 for log in logs if log.medication_taken is not None]
    dietary_values = [
        float(log.dietary_compliance_score)
        for log in logs
        if log.dietary_compliance_score is not None
    ]

    hydration_values = []
    target = plan.fluid_intake_target_ml if plan and plan.fluid_intake_target_ml else None
    if target:
        for log in logs:
            if log.fluid_intake_ml is None:
                continue
            hydration_values.append(min(float(log.fluid_intake_ml) / float(target), 1.0))

    medication_avg = _average(medication_values)
    hydration_avg = _average(hydration_values)
    dietary_avg = _average(dietary_values)

    trend_values = hydration_values or medication_values or dietary_values
    trend = _trend_from_values(trend_values)

    return {
        "medication_adherence_7d": medication_avg,
        "hydration_adherence_7d": hydration_avg,
        "dietary_compliance_7d": dietary_avg,
        "trend": trend,
    }


def _compute_priming(
    voice_calls: list[VoiceCall], sms_messages: list[SmsMessage]
) -> dict[str, Any]:
    recent_changes = None
    if voice_calls:
        recent_changes = voice_calls[0].summary or _truncate_text(voice_calls[0].transcript, 400)
    if not recent_changes and sms_messages:
        recent_changes = _truncate_text(sms_messages[0].content, 300)

    areas = ["hydration goals", "dietary triggers", "medication adherence"]
    return {
        "recent_changes": recent_changes or "None",
        "areas_to_probe": areas,
        "tone_notes": "Encouraging and specific with goals",
        "escalation_flags": [],
    }


def _build_prompt(
    patient: Patient,
    plan: PreventionPlan | None,
    analysis: StoneAnalysis | None,
    labs: list[LabResult],
    compliance_logs: list[ComplianceLog],
    voice_calls: list[VoiceCall],
    sms_messages: list[SmsMessage],
    trigger: str,
    event_data: dict | None,
    adherence_snapshot: dict[str, Any],
    priming: dict[str, Any],
    version: int,
) -> str:
    payload = {
        "patient": {
            "id": str(patient.id),
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": _iso_date(patient.date_of_birth),
            "phone": patient.phone,
            "email": patient.email,
        },
        "analysis": _serialize_analysis(analysis),
        "prevention_plan": _serialize_plan(plan),
        "lab_results": [_serialize_lab(lab) for lab in labs],
        "compliance_logs_7d": [_serialize_log(log) for log in compliance_logs],
        "voice_calls": [_serialize_call(call) for call in voice_calls],
        "sms_messages": [_serialize_sms(msg) for msg in sms_messages],
        "trigger": trigger,
        "event_data": _truncate_value(event_data, 600) if event_data else None,
        "computed_adherence": adherence_snapshot,
        "computed_priming": priming,
        "context_version": version,
    }

    schema_hint = (
        "{\n"
        '  "patient_id": "uuid",\n'
        '  "generated_at": "ISO-8601 timestamp",\n'
        '  "version": 1,\n'
        '  "medical_summary": {\n'
        '    "stone_history": "string",\n'
        '    "current_medications": ["string"],\n'
        '    "comorbidities": ["string"],\n'
        '    "key_labs": { "name": { "value": 0, "unit": "string", "status": "low|ok|high", "target": "string" } }\n'
        "  },\n"
        '  "risk_assessment": {\n'
        '    "recurrence_risk": "low|moderate|high|unknown",\n'
        '    "primary_risk_factors": ["string"],\n'
        '    "stone_type": "string"\n'
        "  },\n"
        '  "prevention_plan": {\n'
        '    "fluid_target_ml": 0,\n'
        '    "dietary_recommendations": [],\n'
        '    "medication_guidance": [],\n'
        '    "monitoring": "string"\n'
        "  },\n"
        '  "conversation_priming": {\n'
        '    "recent_changes": "string",\n'
        '    "areas_to_probe": ["string"],\n'
        '    "tone_notes": "string",\n'
        '    "escalation_flags": []\n'
        "  },\n"
        '  "adherence_snapshot": {\n'
        '    "medication_adherence_7d": 0,\n'
        '    "hydration_adherence_7d": 0,\n'
        '    "dietary_compliance_7d": 0,\n'
        '    "trend": "improving|stable|declining|unknown"\n'
        "  }\n"
        "}\n"
    )

    return (
        "You are a clinical reasoning assistant helping build a patient context document "
        "for a kidney stone prevention voice agent.\n\n"
        "Return ONLY valid JSON. Do not wrap in markdown or code fences.\n"
        "If a field is unknown, use null or \"unknown\". Use [] for empty lists.\n\n"
        "Schema:\n"
        f"{schema_hint}\n"
        "Available data (JSON):\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=True)}\n"
    )


def _parse_context(text: str | None) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        lines = cleaned.splitlines()
        if lines and lines[0].strip().lower().startswith("json"):
            cleaned = "\n".join(lines[1:])
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            return parsed[0]
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return None
    return None


def _normalize_context(
    context: dict[str, Any],
    patient: Patient,
    version: int,
    adherence_snapshot: dict[str, Any],
    priming: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(context)
    normalized["patient_id"] = str(patient.id)
    normalized["generated_at"] = datetime.utcnow().isoformat()
    normalized["version"] = version

    if not isinstance(normalized.get("conversation_priming"), dict):
        normalized["conversation_priming"] = priming
    else:
        merged = dict(priming)
        merged.update(normalized["conversation_priming"])
        normalized["conversation_priming"] = merged

    if not isinstance(normalized.get("adherence_snapshot"), dict):
        normalized["adherence_snapshot"] = adherence_snapshot
    else:
        merged = dict(adherence_snapshot)
        merged.update(normalized["adherence_snapshot"])
        normalized["adherence_snapshot"] = merged

    normalized.setdefault("medical_summary", {})
    normalized.setdefault("risk_assessment", {})
    normalized.setdefault("prevention_plan", {})
    return normalized


def _fallback_context(
    patient: Patient,
    plan: PreventionPlan | None,
    analysis: StoneAnalysis | None,
    labs: list[LabResult],
    adherence_snapshot: dict[str, Any],
    priming: dict[str, Any],
    version: int,
) -> dict[str, Any]:
    return {
        "patient_id": str(patient.id),
        "generated_at": datetime.utcnow().isoformat(),
        "version": version,
        "medical_summary": {
            "stone_history": analysis.predicted_composition if analysis else "unknown",
            "current_medications": _extract_medications(plan),
            "comorbidities": [],
            "key_labs": _extract_key_labs(labs),
        },
        "risk_assessment": {
            "recurrence_risk": "unknown",
            "primary_risk_factors": [],
            "stone_type": analysis.predicted_composition if analysis else "unknown",
        },
        "prevention_plan": {
            "fluid_target_ml": plan.fluid_intake_target_ml if plan else None,
            "dietary_recommendations": plan.dietary_recommendations if plan else [],
            "medication_guidance": plan.medications_recommended if plan else [],
            "monitoring": "Follow up with your care team." if plan else "unknown",
        },
        "conversation_priming": priming,
        "adherence_snapshot": adherence_snapshot,
    }


def _serialize_analysis(analysis: StoneAnalysis | None) -> dict[str, Any] | None:
    if not analysis:
        return None
    return {
        "id": str(analysis.id),
        "predicted_composition": analysis.predicted_composition,
        "composition_confidence": analysis.composition_confidence,
        "treatment_recommendation": analysis.treatment_recommendation,
        "treatment_rationale": _truncate_text(analysis.treatment_rationale, 600),
        "urgency_level": analysis.urgency_level,
        "created_at": _iso_datetime(analysis.created_at),
    }


def _serialize_plan(plan: PreventionPlan | None) -> dict[str, Any] | None:
    if not plan:
        return None
    return {
        "id": str(plan.id),
        "fluid_intake_target_ml": plan.fluid_intake_target_ml,
        "dietary_recommendations": plan.dietary_recommendations,
        "medications_recommended": plan.medications_recommended,
        "lifestyle_modifications": plan.lifestyle_modifications,
        "personalized_summary": _truncate_text(plan.personalized_summary, 800),
        "created_at": _iso_datetime(plan.created_at),
    }


def _serialize_lab(lab: LabResult) -> dict[str, Any]:
    return {
        "id": str(lab.id),
        "result_type": lab.result_type,
        "result_date": _iso_date(lab.result_date),
        "results": lab.results,
        "created_at": _iso_datetime(lab.created_at),
    }


def _serialize_log(log: ComplianceLog) -> dict[str, Any]:
    return {
        "date": _iso_date(log.log_date),
        "fluid_intake_ml": log.fluid_intake_ml,
        "medication_taken": log.medication_taken,
        "dietary_compliance_score": log.dietary_compliance_score,
        "notes": _truncate_text(log.notes, 200),
    }


def _serialize_call(call: VoiceCall) -> dict[str, Any]:
    return {
        "id": str(call.id),
        "call_type": call.call_type,
        "direction": call.direction,
        "status": call.status,
        "started_at": _iso_datetime(call.started_at),
        "ended_at": _iso_datetime(call.ended_at),
        "summary": _truncate_text(call.summary, MAX_TEXT_LEN),
        "transcript": _truncate_text(call.transcript, MAX_TEXT_LEN),
    }


def _serialize_sms(msg: SmsMessage) -> dict[str, Any]:
    return {
        "id": str(msg.id),
        "direction": msg.direction,
        "message_type": msg.message_type,
        "content": _truncate_text(msg.content, 500),
        "created_at": _iso_datetime(msg.created_at),
    }


def _extract_key_labs(labs: list[LabResult]) -> dict[str, Any]:
    key_labs: dict[str, Any] = {}
    for lab in labs:
        if not isinstance(lab.results, dict):
            continue
        for key, value in lab.results.items():
            if key not in key_labs:
                key_labs[key] = {"value": value, "unit": None, "status": None, "target": None}
    return key_labs


def _extract_medications(plan: PreventionPlan | None) -> list[str]:
    if not plan or not plan.medications_recommended:
        return []
    meds = []
    for item in plan.medications_recommended:
        if isinstance(item, dict) and item.get("name"):
            meds.append(str(item["name"]))
        elif isinstance(item, str):
            meds.append(item)
    return meds


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / float(len(values))


def _trend_from_values(values: list[float]) -> str:
    if len(values) < 4:
        return "unknown"
    midpoint = len(values) // 2
    first = _average(values[:midpoint]) or 0.0
    last = _average(values[midpoint:]) or 0.0
    if last > first + 0.05:
        return "improving"
    if last < first - 0.05:
        return "declining"
    return "stable"


def _truncate_text(text: Any, limit: int) -> str | None:
    if text is None:
        return None
    raw = str(text)
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 3)] + "..."


def _truncate_value(value: Any, limit: int) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return _truncate_text(value, limit)
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        trimmed = value[:10]
        return [_truncate_value(item, limit) for item in trimmed]
    if isinstance(value, dict):
        return {k: _truncate_value(v, limit) for k, v in value.items()}
    return str(value)


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    try:
        return value.isoformat()
    except AttributeError:
        return None


def _iso_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        return value.isoformat()
    except AttributeError:
        return None
