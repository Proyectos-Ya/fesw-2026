"""shipping_clp en quotation

Revision ID: b7d2e4f6a813
Revises: a3f9c8e1d402
Create Date: 2026-11-04 21:10:00.000000

HU-32: valor de despacho de la cotizacion, que la extension pega en el campo
"Despacho" de Compra Agil. Columna nullable sin default: compatible hacia atrás
y sin reescritura de la tabla.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2e4f6a813"
down_revision: str | Sequence[str] | None = "a3f9c8e1d402"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "quotation",
        sa.Column("shipping_clp", sa.Numeric(precision=14, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("quotation", "shipping_clp")
