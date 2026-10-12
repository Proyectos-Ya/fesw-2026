"""Historial del cron de estados: cuántas corridas incompletas van seguidas.

Es lo que decide si una corrida con la API fallando sale con 0 (pasajero, la
ventana de 2 h la cubre la siguiente) o con 1 (varias horas sin mirar, que sí
merece el correo de Railway). Ver `scripts/sync_estados.py`.

Tabla propia y no `ingestion_run`: `sync_diaria` se niega a correr si ve una
corrida en `running` ahí, y compartirla la bloquearía cada vez que coincidan.
"""

from datetime import timedelta

import pytest

from app.infrastructure.repositories.sync_estados_run_repository import (
    SyncEstadosRunRepository,
)
from app.shared.datetime_utils import utc_now_naive

pytestmark = pytest.mark.asyncio


async def test_sin_historial_una_incompleta_es_la_primera(db_session):
    repo = SyncEstadosRunRepository(db_session)

    assert await repo.registrar(completo=False, listadas=20) == 1


async def test_una_completa_devuelve_cero(db_session):
    repo = SyncEstadosRunRepository(db_session)

    assert await repo.registrar(completo=True, listadas=300) == 0


async def test_cuenta_las_incompletas_desde_la_ultima_completa(db_session):
    repo = SyncEstadosRunRepository(db_session)
    await repo.registrar(completo=False, listadas=1)
    await repo.registrar(completo=True, listadas=1)
    await repo.registrar(completo=False, listadas=1)
    await repo.registrar(completo=False, listadas=1)

    assert await repo.registrar(completo=False, listadas=1) == 3


async def test_ordena_por_cuando_corrio_no_por_cuando_se_inserto(db_session):
    """Una fila con fecha posterior a la completa cuenta aunque se cargue antes."""
    repo = SyncEstadosRunRepository(db_session)
    ahora = utc_now_naive()
    await repo.registrar(completo=False, listadas=1, momento=ahora)
    await repo.registrar(completo=True, listadas=1, momento=ahora - timedelta(hours=1))

    assert await repo.registrar(completo=False, listadas=1) == 2


async def test_poda_lo_viejo(db_session):
    """Corre cada hora: sin poda la tabla crece ~8.800 filas al año sin uso."""
    repo = SyncEstadosRunRepository(db_session)
    await repo.registrar(
        completo=False, listadas=1, momento=utc_now_naive() - timedelta(days=40)
    )

    await repo.registrar(completo=True, listadas=1)

    assert await repo.contar() == 1
