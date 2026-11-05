"""merge heads despacho y develop

Revision ID: 472fefbe1e8c
Revises: 5f4e2aeb2faf, b7d2e4f6a813
Create Date: 2026-11-05 00:40:16.295849

HU-32: une la migración de despacho (b7d2e4f6a813, ya aplicada en la base de
prueba) con la cabeza de develop. Se usa merge en vez de repuntar down_revision
porque esa migración ya se aplicó en un entorno. No altera el esquema.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "472fefbe1e8c"
down_revision: str | Sequence[str] | None = ("5f4e2aeb2faf", "b7d2e4f6a813")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
