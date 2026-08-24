"""Las migraciones de Alembic tienen que reflejar exactamente los modelos.

El bug que este test previene: el esquema lo creaba `SQLModel.metadata.create_all`
al arrancar, que agrega tablas nuevas pero **no altera las existentes**. Así se
acumuló deriva silenciosa —la restricción de unicidad de `matching_result` nunca
llegó a las bases ya creadas—, y nadie se enteró hasta revisarlo a mano.
"""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlmodel import SQLModel

import app.infrastructure.repositories.models  # noqa: F401  (registra los modelos)

pytestmark = pytest.mark.integration


async def test_el_esquema_migrado_coincide_con_los_modelos(integration_engine):
    """Equivale a `alembic check`, pero corriendo en la suite.

    `conftest` crea el esquema desde los modelos, así que comparar contra el
    metadata detecta el caso que importa: un modelo cambiado sin su migración.
    """

    def _comparar(connection):
        contexto = MigrationContext.configure(connection)
        return compare_metadata(contexto, SQLModel.metadata)

    async with integration_engine.connect() as conn:
        diferencias = await conn.run_sync(_comparar)

    assert not diferencias, (
        "El esquema no coincide con los modelos. Genera la migración con:\n"
        "  alembic revision --autogenerate -m '<descripción>'\n"
        f"Diferencias: {diferencias}"
    )
