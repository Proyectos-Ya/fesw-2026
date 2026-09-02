"""cola de ingesta con contador de intentos

Revision ID: 0af9129cc120
Revises: 7df7c9a1ca0a
Create Date: 2026-09-01

El bucle de ingesta marcaba `is_processed=True` ante cualquier excepción "para no
bloquear la cola". Como el listado de Mercado Público deduplica por código, esa
licitación no vuelve a ofrecerse nunca: un error de parseo la perdía para
siempre y de paso quemaba la petición que costó traerla.

`attempts` permite reintentar unas cuantas veces antes de rendirse, y ordena la
cola para que una licitación que falla siempre se vaya al final en vez de
acaparar cada lote. `last_error` guarda el motivo para no tener que reproducirlo.

Ambas columnas son compatibles hacia atrás, como exige el `preDeployCommand` de
`railway.toml`: la versión anterior del código convive con este esquema sin
enterarse. `attempts` lleva `server_default` porque la tabla ya tiene filas en
producción y un NOT NULL sin default las rechazaría.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0af9129cc120"
down_revision: str | Sequence[str] | None = "7df7c9a1ca0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tender_metadata",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tender_metadata",
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    # El SELECT de pendientes filtra por is_processed y ordena por attempts. El
    # índice existente sobre is_processed ya no basta: sin esto, cada lote
    # ordena en memoria toda la cola pendiente.
    op.create_index(
        "ix_tender_metadata_cola",
        "tender_metadata",
        ["is_processed", "attempts", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tender_metadata_cola", table_name="tender_metadata")
    op.drop_column("tender_metadata", "last_error")
    op.drop_column("tender_metadata", "attempts")
