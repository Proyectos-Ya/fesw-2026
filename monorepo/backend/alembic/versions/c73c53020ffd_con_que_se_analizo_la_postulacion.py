"""con que se analizo la postulacion (#292)

Dos columnas nullable en `proposal_drafts`:

- `analysis_documents` (JSONB): los adjuntos que leyó la factibilidad, como lista
  de `{name, corrupted}`.
- `mentions_attachments` (boolean): si la ficha menciona bases, TDR o anexos.

Con eso la pantalla recomienda subir las bases. Nullable y sin default: en
Postgres es un cambio solo de catálogo, sin reescribir la tabla, y la versión
anterior del backend sigue funcionando con el esquema nuevo. Los borradores
anteriores quedan con NULL. Ninguna consulta filtra por ellas, así que no llevan
índice.

Revision ID: c73c53020ffd
Revises: b3c2d1e0f9a8
Create Date: 2026-10-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c73c53020ffd"
down_revision: str | Sequence[str] | None = "b3c2d1e0f9a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "proposal_drafts",
        sa.Column(
            "analysis_documents",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "proposal_drafts",
        sa.Column("mentions_attachments", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("proposal_drafts", "mentions_attachments")
    op.drop_column("proposal_drafts", "analysis_documents")
