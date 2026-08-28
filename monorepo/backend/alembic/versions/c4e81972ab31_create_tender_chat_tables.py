"""create tender chat tables

Revision ID: c4e81972ab31
Revises: 9a1c4f7b2e08
Create Date: 2026-08-27 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision: str = "c4e81972ab31"
down_revision: str | Sequence[str] | None = "9a1c4f7b2e08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the message and document persistence used by tender chat."""
    op.create_table(
        "tender_chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tender_chat_messages_tender_id"),
        "tender_chat_messages",
        ["tender_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tender_chat_messages_user_id"),
        "tender_chat_messages",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "tender_chat_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "file_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "file_type", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False
        ),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tender.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tender_chat_documents_tender_id"),
        "tender_chat_documents",
        ["tender_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tender_chat_documents_user_id"),
        "tender_chat_documents",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove tender chat persistence."""
    op.drop_index(
        op.f("ix_tender_chat_documents_user_id"),
        table_name="tender_chat_documents",
    )
    op.drop_index(
        op.f("ix_tender_chat_documents_tender_id"),
        table_name="tender_chat_documents",
    )
    op.drop_table("tender_chat_documents")
    op.drop_index(
        op.f("ix_tender_chat_messages_user_id"),
        table_name="tender_chat_messages",
    )
    op.drop_index(
        op.f("ix_tender_chat_messages_tender_id"),
        table_name="tender_chat_messages",
    )
    op.drop_table("tender_chat_messages")
