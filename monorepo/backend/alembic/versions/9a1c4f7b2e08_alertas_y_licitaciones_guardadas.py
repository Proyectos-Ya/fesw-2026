"""alertas de licitaciones y licitaciones guardadas

Revision ID: 9a1c4f7b2e08
Revises: 2d2720796d82
Create Date: 2026-08-26 12:00:00.000000

`saved_tender` entra acá y no en la migración inicial porque su modelo nunca se
registró en `app/infrastructure/repositories/models.py`: Alembic no lo veía y la
tabla no existía en una base creada desde cero, aunque el código la consultara.

"""

from collections.abc import Sequence

import sqlalchemy as sa

# El submódulo se importa explícitamente: `sqlmodel/__init__.py` no expone
# `sql`, así que el `import sqlmodel` que genera alembic deja
# `sqlmodel.sql.sqltypes.AutoString` sin resolver para el type checker.
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a1c4f7b2e08"
down_revision: str | Sequence[str] | None = "2d2720796d82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "saved_tender",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("saved_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tender_id"],
            ["tender.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tender_id", name="uq_saved_tender_user_tender"),
    )
    op.create_index(
        op.f("ix_saved_tender_tender_id"), "saved_tender", ["tender_id"], unique=False
    )
    op.create_index(
        op.f("ix_saved_tender_user_id"), "saved_tender", ["user_id"], unique=False
    )

    op.create_table(
        "notification_preference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("delivery_mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email_delivery_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "last_failure_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_preference_user_id"),
        "notification_preference",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tender_id"],
            ["tender.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tender_id", name="uq_notification_user_tender"),
    )
    op.create_index(
        op.f("ix_notification_tender_id"), "notification", ["tender_id"], unique=False
    )
    op.create_index(
        op.f("ix_notification_user_id"), "notification", ["user_id"], unique=False
    )
    op.create_index(
        "ix_notification_user_read",
        "notification",
        ["user_id", "read_at"],
        unique=False,
    )

    op.create_table(
        "notification_delivery",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("notification_ids", sa.JSON(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_delivery_user_id"),
        "notification_delivery",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_delivery_pendientes",
        "notification_delivery",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_notification_delivery_pendientes", table_name="notification_delivery"
    )
    op.drop_index(
        op.f("ix_notification_delivery_user_id"), table_name="notification_delivery"
    )
    op.drop_table("notification_delivery")
    op.drop_index("ix_notification_user_read", table_name="notification")
    op.drop_index(op.f("ix_notification_user_id"), table_name="notification")
    op.drop_index(op.f("ix_notification_tender_id"), table_name="notification")
    op.drop_table("notification")
    op.drop_index(
        op.f("ix_notification_preference_user_id"), table_name="notification_preference"
    )
    op.drop_table("notification_preference")
    op.drop_index(op.f("ix_saved_tender_user_id"), table_name="saved_tender")
    op.drop_index(op.f("ix_saved_tender_tender_id"), table_name="saved_tender")
    op.drop_table("saved_tender")
