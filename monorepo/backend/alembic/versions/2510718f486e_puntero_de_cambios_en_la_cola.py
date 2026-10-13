"""puntero_de_cambios_en_la_cola

Revision ID: 2510718f486e
Revises: 1ddfcce953b7
Create Date: 2026-10-13 12:00:00.000000

Plan 305 (ingesta cada 2 h y sync-estados con etiquetado). El cron de estados
deja en `tender_metadata` qué hay que bajar y por qué, y la ingesta baja solo
eso. Agrega:

- En `tender_metadata`, el puntero (`pending_reason`, `api_status_code`,
  `api_changed_at`, `detail_fetched_at`), los reintentos nocturnos y el estado
  terminal (`discarded_at`, `discard_reason`), más un índice parcial con solo
  lo que todavía se puede pedir.
- En `ingestion_run`, el tipo de corrida y las peticiones que hizo.
- En `sync_estados_run`, el cierre de la corrida y las peticiones.

Compatible con la versión anterior durante el despliegue: todas las columnas son
nullable salvo `night_retries`, que tiene un default constante. En Postgres 11 o
más, las dos cosas cambian solo el catálogo y no reescriben la tabla. La versión
anterior no lee las columnas nuevas, y las filas que inserte toman `null` o `0`.

El paso de datos deja la cola de producción como la espera el diseño nuevo:

1. `detail_fetched_at` desde `tender.last_change_at`, que hasta ahora marcaba la
   última bajada del detalle.
2. Las compras cuyo detalle falla siempre pasan a terminal. Medido el
   2026-10-12: 240 filas con 13 a 21 intentos, todas con 504, que tampoco cargan
   en la página oficial. Se filtran por el texto que deja `_describir`
   (`ErrorTransitorioMercadoPublico: ...`), que incluye los 504 y los timeouts y
   excluye la cuota agotada (`CuotaAgotadaError: ...`).
3. Lo que sigue pendiente queda etiquetado: `nueva` si no está en `tender`,
   `actualizar` si ya está.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2510718f486e"
down_revision: str | Sequence[str] | None = "1ddfcce953b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLA = "is_processed = false AND discarded_at IS NULL"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tender_metadata", sa.Column("pending_reason", sa.String(), nullable=True)
    )
    op.add_column(
        "tender_metadata", sa.Column("api_status_code", sa.String(), nullable=True)
    )
    op.add_column(
        "tender_metadata", sa.Column("api_changed_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "tender_metadata",
        sa.Column("detail_fetched_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tender_metadata",
        sa.Column("night_retries", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tender_metadata", sa.Column("discarded_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "tender_metadata", sa.Column("discard_reason", sa.String(), nullable=True)
    )
    op.add_column("ingestion_run", sa.Column("kind", sa.String(), nullable=True))
    op.add_column("ingestion_run", sa.Column("requests", sa.Integer(), nullable=True))
    op.add_column(
        "sync_estados_run", sa.Column("finished_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "sync_estados_run", sa.Column("requests", sa.Integer(), nullable=True)
    )

    op.execute(
        """
        UPDATE tender_metadata m
           SET detail_fetched_at = t.last_change_at
          FROM tender t
         WHERE t.code = m.code
           AND m.detail_fetched_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE tender_metadata
           SET discarded_at = (now() AT TIME ZONE 'utc'),
               discard_reason = 'reintentos_agotados',
               updated_at = (now() AT TIME ZONE 'utc')
         WHERE is_processed = false
           AND attempts >= 3
           AND last_error LIKE 'ErrorTransitorioMercadoPublico:%'
        """
    )
    op.execute(
        f"""
        UPDATE tender_metadata m
           SET pending_reason = CASE
                   WHEN EXISTS (SELECT 1 FROM tender t WHERE t.code = m.code)
                   THEN 'actualizar'
                   ELSE 'nueva'
               END
         WHERE {_COLA}
        """
    )

    # Sin CONCURRENTLY: Alembic corre dentro de una transacción, y la tabla
    # (~42.000 filas medidas el 2026-10-12) se indexa en menos de un segundo.
    op.create_index(
        "ix_tender_metadata_pendientes",
        "tender_metadata",
        ["attempts", "created_at"],
        unique=False,
        postgresql_where=sa.text(_COLA),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tender_metadata_pendientes",
        table_name="tender_metadata",
        postgresql_where=sa.text(_COLA),
    )
    op.drop_column("sync_estados_run", "requests")
    op.drop_column("sync_estados_run", "finished_at")
    op.drop_column("ingestion_run", "requests")
    op.drop_column("ingestion_run", "kind")
    for columna in (
        "discard_reason",
        "discarded_at",
        "night_retries",
        "detail_fetched_at",
        "api_changed_at",
        "api_status_code",
        "pending_reason",
    ):
        op.drop_column("tender_metadata", columna)
