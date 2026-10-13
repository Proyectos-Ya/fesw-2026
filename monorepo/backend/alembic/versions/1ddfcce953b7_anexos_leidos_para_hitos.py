"""anexos_leidos_para_hitos

Revision ID: 1ddfcce953b7
Revises: b4c9e1d8a735
Create Date: 2026-10-12 12:00:00.000000

Plan 233 (disparar la IA con anexos). Qué anexos ya leyó la extracción de hitos
de cada usuario. Los hitos son por usuario y los anexos por empresa. Solo crea
una tabla: compatible con la versión anterior durante el despliegue.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ddfcce953b7"
down_revision: str | Sequence[str] | None = "b4c9e1d8a735"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tender_milestone_attachment",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("attachment_file_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.Column("milestones_found", sa.Integer(), nullable=False),
        # Borrar el archivo borra su registro: si se vuelve a subir, se vuelve a leer.
        sa.ForeignKeyConstraint(
            ["attachment_file_id"], ["attachment_file.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "attachment_file_id"),
    )
    # La PK empieza por `user_id`: cubre esa FK. Las otras dos necesitan índice
    # propio para que el borrado en cascada no recorra la tabla entera.
    op.create_index(
        "ix_tender_milestone_attachment_user_tender",
        "tender_milestone_attachment",
        ["user_id", "tender_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tender_milestone_attachment_attachment_file_id"),
        "tender_milestone_attachment",
        ["attachment_file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tender_milestone_attachment_tender_id"),
        "tender_milestone_attachment",
        ["tender_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tender_milestone_attachment_tender_id"),
        table_name="tender_milestone_attachment",
    )
    op.drop_index(
        op.f("ix_tender_milestone_attachment_attachment_file_id"),
        table_name="tender_milestone_attachment",
    )
    op.drop_index(
        "ix_tender_milestone_attachment_user_tender",
        table_name="tender_milestone_attachment",
    )
    op.drop_table("tender_milestone_attachment")
