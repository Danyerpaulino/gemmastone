"""voice agent pivot tables and columns

Revision ID: 0003_voice_agent_pivot
Revises: 0002_stone_burden_hydronephrosis
Create Date: 2026-02-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0003_voice_agent_pivot"
down_revision = "0002_stone_burden_hydronephrosis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("referral_code", sa.String(length=20), nullable=True))
    op.add_column("providers", sa.Column("qr_code_url", sa.Text(), nullable=True))
    op.execute(
        "UPDATE providers "
        "SET referral_code = CONCAT('provider-', SUBSTRING(gen_random_uuid()::text, 1, 8)) "
        "WHERE referral_code IS NULL"
    )
    op.create_unique_constraint("uq_providers_referral_code", "providers", ["referral_code"])
    op.alter_column("providers", "referral_code", nullable=False)

    op.add_column(
        "patients",
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "patients",
        sa.Column("auth_method", sa.String(length=20), nullable=True, server_default=sa.text("'otp'")),
    )
    op.add_column(
        "patients",
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("patients", sa.Column("onboarding_source", sa.String(length=50), nullable=True))
    op.add_column(
        "patients",
        sa.Column("context_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("patients", sa.Column("last_context_build", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "patients",
        sa.Column("communication_paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("patients", sa.Column("quiet_hours_start", sa.Time(), nullable=True))
    op.add_column("patients", sa.Column("quiet_hours_end", sa.Time(), nullable=True))

    op.create_table(
        "voice_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("vapi_call_id", sa.String(length=100), nullable=True, unique=True),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("call_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'initiated'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("transcript_segments", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("context_version_used", sa.Integer(), nullable=True),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "sms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("telnyx_message_id", sa.String(length=100), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_urls", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'queued'")),
        sa.Column("ai_response", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "patient_contexts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, unique=True),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("trigger", sa.String(length=50), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )
    op.create_index("idx_patient_contexts_patient", "patient_contexts", ["patient_id"])

    op.create_table(
        "context_builds",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'pending'")),
        sa.Column("input_summary", postgresql.JSONB(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "scheduled_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recurrence", sa.String(length=30), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'scheduled'")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("scheduled_actions")
    op.drop_table("context_builds")
    op.drop_index("idx_patient_contexts_patient", table_name="patient_contexts")
    op.drop_table("patient_contexts")
    op.drop_table("sms_messages")
    op.drop_table("voice_calls")

    op.drop_column("patients", "quiet_hours_end")
    op.drop_column("patients", "quiet_hours_start")
    op.drop_column("patients", "communication_paused")
    op.drop_column("patients", "last_context_build")
    op.drop_column("patients", "context_version")
    op.drop_column("patients", "onboarding_source")
    op.drop_column("patients", "onboarding_completed")
    op.drop_column("patients", "auth_method")
    op.drop_column("patients", "phone_verified")

    op.drop_constraint("uq_providers_referral_code", "providers", type_="unique")
    op.drop_column("providers", "qr_code_url")
    op.drop_column("providers", "referral_code")
