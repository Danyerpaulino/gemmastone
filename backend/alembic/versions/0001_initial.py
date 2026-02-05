"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("npi", sa.String(length=10), nullable=True),
        sa.Column("specialty", sa.String(length=100), nullable=True),
        sa.Column("practice_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("providers.id"), nullable=True),
        sa.Column("mrn", sa.String(length=50), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column(
            "contact_preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{\"sms\": true, \"email\": true, \"voice\": false}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "stone_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("ct_scan_path", sa.String(length=500), nullable=True),
        sa.Column("ct_scan_date", sa.Date(), nullable=True),
        sa.Column("stones_detected", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("predicted_composition", sa.String(length=50), nullable=True),
        sa.Column("composition_confidence", sa.Float(), nullable=True),
        sa.Column("stone_3d_model", sa.LargeBinary(), nullable=True),
        sa.Column("treatment_recommendation", sa.String(length=50), nullable=True),
        sa.Column("treatment_rationale", sa.Text(), nullable=True),
        sa.Column("urgency_level", sa.String(length=20), nullable=True),
        sa.Column("workflow_state", postgresql.JSONB(), nullable=True),
        sa.Column("provider_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "lab_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stone_analyses.id"), nullable=True),
        sa.Column("result_type", sa.String(length=50), nullable=False),
        sa.Column("result_date", sa.Date(), nullable=True),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "prevention_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stone_analyses.id"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("dietary_recommendations", postgresql.JSONB(), nullable=True),
        sa.Column("fluid_intake_target_ml", sa.Integer(), nullable=True),
        sa.Column("medications_recommended", postgresql.JSONB(), nullable=True),
        sa.Column("lifestyle_modifications", postgresql.JSONB(), nullable=True),
        sa.Column("education_materials", postgresql.JSONB(), nullable=True),
        sa.Column("personalized_summary", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("prevention_plans.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "nudge_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prevention_plans.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'active'")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "nudges",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nudge_campaigns.id"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("scheduled_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("template", sa.String(length=100), nullable=True),
        sa.Column("message_content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'scheduled'")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "patient_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("ai_response", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(length=20), nullable=True),
        sa.Column("escalated_to_provider", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
    )

    op.create_table(
        "compliance_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("fluid_intake_ml", sa.Integer(), nullable=True),
        sa.Column("medication_taken", sa.Boolean(), nullable=True),
        sa.Column("dietary_compliance_score", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.UniqueConstraint("patient_id", "log_date", name="uq_compliance_patient_date"),
    )

    op.create_index("idx_analyses_patient", "stone_analyses", ["patient_id"])
    op.create_index(
        "idx_nudges_scheduled",
        "nudges",
        ["scheduled_time"],
        postgresql_where=sa.text("status = 'scheduled'"),
    )
    op.create_index("idx_nudges_patient", "nudges", ["patient_id"])
    op.create_index("idx_interactions_patient", "patient_interactions", ["patient_id", "created_at"])
    op.create_index("idx_compliance_patient_date", "compliance_logs", ["patient_id", "log_date"])


def downgrade() -> None:
    op.drop_index("idx_compliance_patient_date", table_name="compliance_logs")
    op.drop_index("idx_interactions_patient", table_name="patient_interactions")
    op.drop_index("idx_nudges_patient", table_name="nudges")
    op.drop_index("idx_nudges_scheduled", table_name="nudges")
    op.drop_index("idx_analyses_patient", table_name="stone_analyses")

    op.drop_table("compliance_logs")
    op.drop_table("patient_interactions")
    op.drop_table("nudges")
    op.drop_table("nudge_campaigns")
    op.drop_table("prevention_plans")
    op.drop_table("lab_results")
    op.drop_table("stone_analyses")
    op.drop_table("patients")
    op.drop_table("providers")
