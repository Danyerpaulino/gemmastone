from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func, text

from app.db.base import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    npi = Column(String(10))
    specialty = Column(String(100))
    practice_name = Column(String(200))
    referral_code = Column(String(20), unique=True, nullable=False)
    qr_code_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Patient(Base):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"))
    mrn = Column(String(50))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date)
    email = Column(String(255))
    phone = Column(String(20))
    contact_preferences = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"sms\": true, \"email\": true, \"voice\": false}'::jsonb"),
    )
    phone_verified = Column(Boolean, nullable=False, server_default=text("false"))
    auth_method = Column(String(20), server_default=text("'otp'"))
    onboarding_completed = Column(Boolean, nullable=False, server_default=text("false"))
    onboarding_source = Column(String(50))
    context_version = Column(Integer, nullable=False, server_default=text("0"))
    last_context_build = Column(DateTime(timezone=True))
    communication_paused = Column(Boolean, nullable=False, server_default=text("false"))
    quiet_hours_start = Column(Time)
    quiet_hours_end = Column(Time)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StoneAnalysis(Base):
    __tablename__ = "stone_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)

    ct_scan_path = Column(String(500))
    ct_scan_date = Column(Date)

    stones_detected = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    predicted_composition = Column(String(50))
    composition_confidence = Column(Float)
    stone_3d_model = Column(LargeBinary)
    total_stone_burden_mm3 = Column(Float)
    hydronephrosis_level = Column(String(20))

    treatment_recommendation = Column(String(50))
    treatment_rationale = Column(Text)
    urgency_level = Column(String(20))

    workflow_state = Column(JSONB)

    provider_approved = Column(Boolean, nullable=False, server_default=text("false"))
    approved_at = Column(DateTime(timezone=True))
    provider_notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("stone_analyses.id"))
    result_type = Column(String(50), nullable=False)
    result_date = Column(Date)
    results = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PreventionPlan(Base):
    __tablename__ = "prevention_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("stone_analyses.id"), nullable=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    dietary_recommendations = Column(JSONB)
    fluid_intake_target_ml = Column(Integer)
    medications_recommended = Column(JSONB)
    lifestyle_modifications = Column(JSONB)
    education_materials = Column(JSONB)
    personalized_summary = Column(Text)
    active = Column(Boolean, nullable=False, server_default=text("true"))
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("prevention_plans.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NudgeCampaign(Base):
    __tablename__ = "nudge_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("prevention_plans.id"), nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'active'"))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class Nudge(Base):
    __tablename__ = "nudges"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("nudge_campaigns.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    channel = Column(String(20), nullable=False)
    template = Column(String(100))
    message_content = Column(Text)
    status = Column(String(20), nullable=False, server_default=text("'scheduled'"))
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    response = Column(Text)
    response_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PatientInteraction(Base):
    __tablename__ = "patient_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    channel = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)
    content = Column(Text)
    ai_response = Column(Text)
    sentiment = Column(String(20))
    escalated_to_provider = Column(Boolean, nullable=False, server_default=text("false"))
    escalation_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ComplianceLog(Base):
    __tablename__ = "compliance_logs"
    __table_args__ = (
        UniqueConstraint("patient_id", "log_date", name="uq_compliance_patient_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    log_date = Column(Date, nullable=False)
    fluid_intake_ml = Column(Integer)
    medication_taken = Column(Boolean)
    dietary_compliance_score = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VoiceCall(Base):
    __tablename__ = "voice_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    vapi_call_id = Column(String(100), unique=True)
    direction = Column(String(10), nullable=False)
    call_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'initiated'"))
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    transcript = Column(Text)
    transcript_segments = Column(JSONB)
    summary = Column(Text)
    context_version_used = Column(Integer)
    escalated = Column(Boolean, nullable=False, server_default=text("false"))
    escalation_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    telnyx_message_id = Column(String(100))
    direction = Column(String(10), nullable=False)
    message_type = Column(String(30))
    content = Column(Text)
    media_urls = Column(JSONB)
    status = Column(String(20), server_default=text("'queued'"))
    ai_response = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PatientContext(Base):
    __tablename__ = "patient_contexts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, unique=True)
    context = Column(JSONB, nullable=False)
    version = Column(Integer, nullable=False, server_default=text("1"))
    built_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    trigger = Column(String(50))
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContextBuild(Base):
    __tablename__ = "context_builds"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    trigger = Column(String(50), nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String(20), server_default=text("'pending'"))
    input_summary = Column(JSONB)
    processing_time_ms = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScheduledAction(Base):
    __tablename__ = "scheduled_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    action_type = Column(String(30), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    recurrence = Column(String(30))
    payload = Column(JSONB)
    status = Column(String(20), server_default=text("'scheduled'"))
    executed_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
