"""indices de tender_id para el borrado de licitaciones

Cuatro tablas apuntan a `tender` con una clave foránea sin índice (medido en
producción el 2026-10-13 con `pg_constraint`): `tender_item`,
`matching_result`, `export_job` y `calendar_oauth_state`. `matching_result`
tiene un único `(supplier_id, tender_id)`, pero `tender_id` va segundo y ese
índice no sirve para buscar por licitación.

El plan 306 borra cada noche las licitaciones cerradas sin uso. Al borrar una
fila de `tender`, Postgres comprueba cada clave foránea que la apunta, y sin
índice eso es recorrer la tabla entera. La primera corrida borra ~18.800
licitaciones y `tender_item` tenía ~104.000 filas.

**Con `CONCURRENTLY`, al revés que `a4c1f2e37b90`.** Esa migración creó sus
índices sin él porque la tabla tenía 337 filas, y dejó dicho que con el corpus
cargado la decisión sería la contraria. `CREATE INDEX` a secas bloquea las
escrituras de la tabla mientras se construye, y la ingesta escribe partidas en
cualquier momento. `CONCURRENTLY` no puede ir dentro de la transacción de
Alembic, por eso va en `autocommit_block()`.

Un `CREATE INDEX CONCURRENTLY` que falla a medias deja un índice `INVALID`
con el nombre tomado, y un `IF NOT EXISTS` lo daría por bueno. Por eso cada
índice se borra antes de crearse: si la migración se reintenta, reconstruye en
vez de saltarse el inválido.

**Compatible hacia atrás**: un índice no cambia el contrato de la tabla.

Revision ID: 3e7ba2172180
Revises: e7123e26c0be
Create Date: 2026-10-15 01:08:40.520833

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e7ba2172180"
down_revision: str | Sequence[str] | None = "e7123e26c0be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (nombre, tabla). Los nombres son los que genera SQLModel con `index=True`,
# para que el autogenerado no vea diferencias con los modelos.
_INDICES = (
    ("ix_tender_item_tender_id", "tender_item"),
    ("ix_matching_result_tender_id", "matching_result"),
    ("ix_export_job_tender_id", "export_job"),
    ("ix_calendar_oauth_state_tender_id", "calendar_oauth_state"),
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        for nombre, tabla in _INDICES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {nombre}")
            op.execute(f"CREATE INDEX CONCURRENTLY {nombre} ON {tabla} (tender_id)")


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        for nombre, _ in reversed(_INDICES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {nombre}")
