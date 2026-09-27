"""Recordatorio configurable por hito (HU-16, criterio 10).

Compatible hacia atrás: solo agrega dos columnas nullable y un índice. La
versión anterior sigue funcionando porque nunca las escribe y su ausencia
equivale a "sin recordatorio".
"""

import sqlalchemy as sa

from alembic import op

revision = "d27a9c3f1b84"
down_revision = "c16d5f2a8b31"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tender_milestone",
        sa.Column("reminder_days_before", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tender_milestone",
        sa.Column("reminder_sent_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_tender_milestone_recordatorio",
        "tender_milestone",
        ["reminder_days_before", "reminder_sent_at"],
    )


def downgrade():
    op.drop_index("ix_tender_milestone_recordatorio", table_name="tender_milestone")
    op.drop_column("tender_milestone", "reminder_sent_at")
    op.drop_column("tender_milestone", "reminder_days_before")
