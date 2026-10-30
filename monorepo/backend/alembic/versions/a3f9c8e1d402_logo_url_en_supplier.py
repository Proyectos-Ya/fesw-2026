"""logo_url en supplier

Revision ID: a3f9c8e1d402
Revises: b7f3c1a9d2e4
Create Date: 2026-10-29 19:15:00.000000

HU-31: Agrega columna logo_url nullable a la tabla supplier para persistir
el logotipo corporativo en la nube y sincronizarlo entre workspaces.
Compatible hacia atrás durante el despliegue (columna nullable).
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f9c8e1d402"
down_revision: str | Sequence[str] | None = "3e7ba2172180"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "supplier",
        sa.Column(
            "logo_url",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("supplier", "logo_url")
