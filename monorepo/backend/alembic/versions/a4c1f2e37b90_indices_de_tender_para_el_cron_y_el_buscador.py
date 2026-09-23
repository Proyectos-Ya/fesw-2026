"""indices de tender para el cron y el buscador

`tender` solo tenía índice en `code` (por ser único). Mientras el corpus fueron
337 filas eso dio igual; medido contra la API el 2026-09-10, entran **~4.500
licitaciones por día hábil**, o sea ~1,15M al año, y las consultas que recorren
la tabla entera dejan de ser gratis.

Dos índices, para dos consultas que existen hoy:

- `(status_id, closing_at)` — `get_expired_published_ids()` tiene exactamente esa
  forma (igualdad de estado, rango de cierre) y el cron la corre **todos los
  días** sobre toda la tabla. Es también el par de filtros más común del
  buscador. El orden no es arbitrario: la columna de igualdad va primera y la de
  rango después, porque un índice compuesto solo sirve desde su prefijo
  izquierdo.
- `published_at` — la ventana de publicación, que es como el cron descubre
  licitaciones nuevas desde el 10-sep-2026, y el filtro de fecha de publicación
  del buscador.

**Compatible hacia atrás**: agregar un índice no cambia el contrato de la tabla,
así que la versión anterior del código convive con él sin enterarse, como exige
el `preDeployCommand` de `railway.toml` (ver AGENTS.md §3).

**Sin `CONCURRENTLY` a propósito.** `CREATE INDEX` toma un lock exclusivo de
escritura sobre la tabla, y `CONCURRENTLY` no puede correr dentro de la
transacción que abre Alembic. Con 337 filas el lock dura milisegundos y no vale
la pena complicar la migración. **Si esto se aplicara con el corpus ya cargado,
la decisión sería la contraria**: con cientos de miles de filas hay que crear el
índice a mano y con `CONCURRENTLY`, fuera de Alembic.

Lo que **no** entra acá es el índice de búsqueda de texto. La consulta usa
`to_tsvector('spanish', coalesce(name,'') || ' ' || coalesce(description,''))`
con la configuración pasada como parámetro ligado, y un índice de expresión solo
lo aprovecha si el árbol de la expresión coincide exactamente — cosa que un
parámetro `text` frente a un `regconfig` literal no garantiza. El camino
confiable es una columna generada `tsvector` con su índice GIN y cambiar la
consulta para usarla, y eso es un cambio de código además de uno de esquema.
Queda anotado en PENDIENTES.

Revision ID: a4c1f2e37b90
Revises: a227c0150001
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c1f2e37b90"
down_revision: str | Sequence[str] | None = "a227c0150001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_tender_estado_cierre", "tender", ["status_id", "closing_at"], unique=False
    )
    op.create_index("ix_tender_published_at", "tender", ["published_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tender_published_at", table_name="tender")
    op.drop_index("ix_tender_estado_cierre", table_name="tender")
