"""make prevention_plans.analysis_id nullable for intake-based plans

Revision ID: 0004_plan_analysis_id_nullable
Revises: 0003_voice_agent_pivot
Create Date: 2026-02-11
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0004_plan_analysis_id_nullable"
down_revision = "0003_voice_agent_pivot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("prevention_plans", "analysis_id", nullable=True)


def downgrade() -> None:
    op.execute("UPDATE prevention_plans SET analysis_id = gen_random_uuid() WHERE analysis_id IS NULL")
    op.alter_column("prevention_plans", "analysis_id", nullable=False)
