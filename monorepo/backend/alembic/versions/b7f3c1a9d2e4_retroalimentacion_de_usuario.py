"""retroalimentacion de usuario (#315)

Tres tablas nuevas para la HU-24:

- `match_report`: reportes de mal match o de análisis incorrecto, únicos por
  (empresa, licitación, tipo).
- `assistant_message_feedback`: dislikes a mensajes del asistente con su
  motivo, únicos por (mensaje, usuario).
- `app_feedback`: comentarios, quejas y reseñas desde ajustes.

Solo tablas nuevas: la versión anterior del backend no las conoce y sigue
funcionando con el esquema nuevo.

Revision ID: b7f3c1a9d2e4
Revises: e7123e26c0be
Create Date: 2026-10-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f3c1a9d2e4"
down_revision: str | Sequence[str] | None = "e7123e26c0be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "match_report",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"]),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_id",
            "tender_id",
            "kind",
            name="uq_match_report_supplier_tender_kind",
        ),
    )
    op.create_index(
        op.f("ix_match_report_supplier_id"), "match_report", ["supplier_id"]
    )
    op.create_index(op.f("ix_match_report_tender_id"), "match_report", ["tender_id"])

    op.create_table(
        "assistant_message_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["tender_chat_messages.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"]),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "user_id", name="uq_assistant_feedback_message_user"
        ),
    )
    op.create_index(
        op.f("ix_assistant_message_feedback_message_id"),
        "assistant_message_feedback",
        ["message_id"],
    )
    op.create_index(
        op.f("ix_assistant_message_feedback_supplier_id"),
        "assistant_message_feedback",
        ["supplier_id"],
    )
    op.create_index(
        op.f("ix_assistant_message_feedback_tender_id"),
        "assistant_message_feedback",
        ["tender_id"],
    )

    op.create_table(
        "app_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_feedback_user_id"), "app_feedback", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_app_feedback_user_id"), table_name="app_feedback")
    op.drop_table("app_feedback")
    op.drop_index(
        op.f("ix_assistant_message_feedback_tender_id"),
        table_name="assistant_message_feedback",
    )
    op.drop_index(
        op.f("ix_assistant_message_feedback_supplier_id"),
        table_name="assistant_message_feedback",
    )
    op.drop_index(
        op.f("ix_assistant_message_feedback_message_id"),
        table_name="assistant_message_feedback",
    )
    op.drop_table("assistant_message_feedback")
    op.drop_index(op.f("ix_match_report_tender_id"), table_name="match_report")
    op.drop_index(op.f("ix_match_report_supplier_id"), table_name="match_report")
    op.drop_table("match_report")
