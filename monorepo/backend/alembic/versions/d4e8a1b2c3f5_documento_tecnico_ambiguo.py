"""documento tecnico ambiguo (#292)

Una columna nullable en `proposal_drafts`:

- `technical_document_ambiguous` (boolean): las bases mencionan un informe o
  documento técnico sin aclarar si va con la oferta o se entrega al ejecutar el
  servicio (plan 292, §2.8).

Nullable y sin default: en Postgres es un cambio solo de catálogo, sin
reescribir la tabla, y la versión anterior del backend sigue funcionando con el
esquema nuevo. Los borradores anteriores quedan con NULL. Ninguna consulta
filtra por ella, así que no lleva índice.

Revision ID: d4e8a1b2c3f5
Revises: c73c53020ffd
Create Date: 2026-10-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e8a1b2c3f5"
down_revision: str | Sequence[str] | None = "c73c53020ffd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "proposal_drafts",
        sa.Column("technical_document_ambiguous", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("proposal_drafts", "technical_document_ambiguous")
