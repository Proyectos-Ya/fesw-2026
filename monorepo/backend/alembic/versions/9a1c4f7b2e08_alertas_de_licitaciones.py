"""alertas de licitaciones

Revision ID: 9a1c4f7b2e08
Revises: 82786321a8db
Create Date: 2026-08-26 12:00:00.000000

Crea las tres tablas de la HdU 08: `notification_preference`, `notification` y
`notification_delivery`.

Esta migración también creaba `saved_tender`. El autogenerate se la llevó porque
esta rama fue la primera en registrar `SavedTenderModel` en
`app/infrastructure/repositories/models.py`, y hasta entonces Alembic no veía ese
modelo. Mientras tanto, en `develop` la HU9 creó su propia migración para la misma
tabla (`82786321a8db`), así que acá se quitó y esta pasa a colgar de aquella: la
cadena queda lineal y `saved_tender` tiene un solo dueño.

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
down_revision: str | Sequence[str] | None = "82786321a8db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
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
