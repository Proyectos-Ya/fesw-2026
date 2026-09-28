"""supplier: RUT único sin importar el formato

Hasta ahora solo `user_id` era único en `supplier`. El RUT se validaba con un
SELECT previo al INSERT, y entre esa lectura y la escritura había segundos —el
embedding va en medio—, así que dos peticiones podían pasar la validación y
guardar el mismo RUT dos veces.

El índice es **funcional** sobre el RUT sin puntos ni guion y en mayúsculas, no
sobre la columna tal cual. Las filas anteriores a la normalización del dominio
(`format_rut`) pueden estar guardadas como `76086428-5` o `76.086.428-5`: un
índice sobre el texto exacto las trataría como distintas.

Compatible hacia atrás: la versión anterior del código sigue funcionando con el
índice creado. Si en la base ya hay dos filas con el mismo RUT normalizado, la
creación del índice falla y el despliegue se aborta sin cambios; hay que
resolver esos duplicados antes.

Revision ID: d7f2a9c41b58
Revises: b1c4a7e93f10
Create Date: 2026-09-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f2a9c41b58"
down_revision: str | Sequence[str] | None = "b1c4a7e93f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# El repositorio traduce la violación de este índice a SupplierAlreadyExists
# buscando este nombre, así que no se puede cambiar solo acá.
INDEX_NAME = "ix_supplier_rut_normalizado"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        INDEX_NAME,
        "supplier",
        [sa.text("upper(replace(replace(rut, '.', ''), '-', ''))")],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(INDEX_NAME, table_name="supplier")
