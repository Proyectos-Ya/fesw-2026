"""add has_completed_onboarding to users

Revision ID: a9810a282f7a
Revises: a3f9c8e1d402
Create Date: 2026-11-03 15:54:52.546384

HU-28: Agrega columna has_completed_onboarding a la tabla users para persistir
el estado del onboarding/tour interactivo en la base de datos (Cross-device).
Compatible hacia atrás durante el despliegue con server_default=false.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "a9810a282f7a"
down_revision: str | Sequence[str] | None = "a3f9c8e1d402"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "has_completed_onboarding",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "has_completed_onboarding")
