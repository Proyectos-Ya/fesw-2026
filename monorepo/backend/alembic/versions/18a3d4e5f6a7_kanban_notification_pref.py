"""kanban notification preference

Revision ID: 18a3d4e5f6a7
Revises: 18a2c3d4e5f6
Create Date: 2026-10-27 10:10:00.000000

HU-18: cada miembro del workspace decide si quiere recibir notificaciones
cuando otro miembro mueve el tablero. Default `false` para no spamear a
usuarios que no esperan avisos del tablero.

`NotificationKind` es un `Literal` de Python a nivel de dominio (no un enum
Postgres), así que agregar el valor `"kanban_change"` **no requiere** tocar
el schema de la DB: solo se declara en el entity de dominio. Esta migración
se limita a la nueva columna booleana.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "18a3d4e5f6a7"
down_revision: str | Sequence[str] | None = "18a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preference",
        sa.Column(
            "kanban_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_preference", "kanban_notifications_enabled")
