"""add stone burden and hydronephrosis fields

Revision ID: 0002_stone_burden_hydronephrosis
Revises: 0001_initial
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_stone_burden_hydronephrosis"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stone_analyses", sa.Column("total_stone_burden_mm3", sa.Float(), nullable=True))
    op.add_column("stone_analyses", sa.Column("hydronephrosis_level", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("stone_analyses", "hydronephrosis_level")
    op.drop_column("stone_analyses", "total_stone_burden_mm3")
