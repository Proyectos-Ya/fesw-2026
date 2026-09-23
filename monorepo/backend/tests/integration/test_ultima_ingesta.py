"""Fin de la última corrida de ingesta que trajo datos.

Es la señal con la que se invalida la caché de recomendaciones: una vez por
corrida del cron, no una vez por licitación que entra durante la corrida.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import IngestionRunModel
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.shared.datetime_utils import utc_now_naive

pytestmark = pytest.mark.asyncio


async def _corrida(
    engine, *, status: str, finished_at: datetime | None, processed: int
) -> None:
    ahora = utc_now_naive()
    async with AsyncSession(engine) as s:
        s.add(
            IngestionRunModel(
                id=uuid.uuid4(),
                window_from=ahora - timedelta(days=1),
                window_to=ahora,
                status=status,
                finished_at=finished_at,
                processed=processed,
            )
        )
        await s.commit()


async def _ultima(engine) -> datetime | None:
    async with AsyncSession(engine) as s:
        return await TenderRepository(s).get_latest_ingestion_finished_at()


async def test_sin_corridas_devuelve_none(integration_engine):
    assert await _ultima(integration_engine) is None


async def test_devuelve_el_fin_mas_reciente(integration_engine):
    ahora = utc_now_naive()
    reciente = ahora - timedelta(hours=1)
    await _corrida(
        integration_engine,
        status="ok",
        finished_at=ahora - timedelta(days=1),
        processed=5,
    )
    await _corrida(integration_engine, status="ok", finished_at=reciente, processed=5)

    assert await _ultima(integration_engine) == reciente


async def test_ignora_corridas_en_curso_y_sin_datos(integration_engine):
    ahora = utc_now_naive()
    buena = ahora - timedelta(days=1)
    await _corrida(integration_engine, status="ok", finished_at=buena, processed=5)
    await _corrida(integration_engine, status="running", finished_at=None, processed=3)
    await _corrida(
        integration_engine,
        status="ok",
        finished_at=ahora - timedelta(hours=1),
        processed=0,
    )

    assert await _ultima(integration_engine) == buena


async def test_cuenta_las_corridas_parciales_con_datos(integration_engine):
    """Una corrida cortada a mitad igual insertó licitaciones."""
    ahora = utc_now_naive()
    parcial = ahora - timedelta(hours=1)
    await _corrida(
        integration_engine,
        status="ok",
        finished_at=ahora - timedelta(days=1),
        processed=5,
    )
    await _corrida(
        integration_engine, status="partial", finished_at=parcial, processed=2
    )

    assert await _ultima(integration_engine) == parcial
