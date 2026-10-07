"""bases ya leídas por la extracción de hitos (HU-16, criterio 1)

Revision ID: b16e7a2c9d40
Revises: b3c2d1e0f9a8
Create Date: 2026-10-06 12:00:00.000000

Solo agrega una tabla: compatible con la versión anterior de la API durante el
despliegue. Cada documento se lee una sola vez; volver a leerlo duplicaba o
borraba hitos.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b16e7a2c9d40"
down_revision: str | Sequence[str] | None = "b3c2d1e0f9a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tender_milestone_document",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.Column("milestones_found", sa.Integer(), nullable=False),
        # Borrar la base en el asistente borra su registro: si se vuelve a
        # subir, se vuelve a leer.
        sa.ForeignKeyConstraint(
            ["document_id"], ["tender_chat_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "ix_tender_milestone_document_user_tender",
        "tender_milestone_document",
        ["user_id", "tender_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tender_milestone_document_tender_id"),
        "tender_milestone_document",
        ["tender_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tender_milestone_document_tender_id"), table_name="tender_milestone_document"
    )
    op.drop_index(
        "ix_tender_milestone_document_user_tender", table_name="tender_milestone_document"
    )
    op.drop_table("tender_milestone_document")
