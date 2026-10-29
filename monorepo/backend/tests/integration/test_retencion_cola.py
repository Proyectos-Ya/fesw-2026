"""Retención de la cola de ingesta (plan 305).

`tender_metadata` crece ~5.600 filas por día hábil y nunca se borraba. Lo que ya
no sirve:

- Procesadas hace más de 30 días cuya licitación ya no está activa: el listado
  nocturno solo encola publicadas abiertas, y si una reabre, el cron de estados
  la vuelve a crear como `actualizar`.
- Terminales de hace más de 60 días.

Lo que se queda: lo pendiente, lo procesado reciente y lo procesado de una
licitación que sigue publicada.
"""

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    TenderMetadataModel,
    TenderModel,
)
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.shared.datetime_utils import utc_now_naive

pytestmark = pytest.mark.asyncio

AHORA = utc_now_naive()
PUBLICADA, CERRADA = 2, 3


@pytest_asyncio.fixture
async def servicio(integration_engine) -> TenderIngestionService:
    async with AsyncSession(integration_engine) as s:
        await seed_database_metadata(s)
        s.add(
            BuyerInstitutionModel(
                rut="1-9",
                name="Comprador",
                region_id=13,
                created_at=AHORA,
                updated_at=AHORA,
            )
        )
        await s.commit()
    return TenderIngestionService(
        engine=integration_engine,
        client=None,  # type: ignore[arg-type]
        embedding_service=None,  # type: ignore[arg-type]
    )


async def _licitacion(engine, code: str, status_id: int) -> None:
    async with AsyncSession(engine) as s:
        s.add(
            TenderModel(
                id=uuid.uuid4(),
                code=code,
                name="Licitación",
                status_id=status_id,
                published_at=AHORA,
                closing_at=AHORA,
                last_change_at=AHORA,
                buyer_rut="1-9",
                buyer_unit="Unidad",
                created_at=AHORA,
                updated_at=AHORA,
            )
        )
        await s.commit()


async def _fila(engine, code: str, **campos) -> None:
    async with AsyncSession(engine) as s:
        valores = {"created_at": AHORA, "updated_at": AHORA, **campos}
        s.add(TenderMetadataModel(id=uuid.uuid4(), code=code, **valores))
        await s.commit()


async def _codigos(engine) -> set[str]:
    async with AsyncSession(engine) as s:
        return set((await s.exec(select(TenderMetadataModel.code))).all())


async def test_borra_solo_lo_que_ya_no_sirve(servicio, integration_engine):
    viejo = AHORA - timedelta(days=40)
    muy_viejo = AHORA - timedelta(days=70)
    await _licitacion(integration_engine, "CERRADA-VIEJA", CERRADA)
    await _licitacion(integration_engine, "PUBLICADA-VIEJA", PUBLICADA)
    await _licitacion(integration_engine, "CERRADA-RECIENTE", CERRADA)
    await _fila(
        integration_engine, "CERRADA-VIEJA", is_processed=True, detail_fetched_at=viejo
    )
    await _fila(
        integration_engine,
        "PUBLICADA-VIEJA",
        is_processed=True,
        detail_fetched_at=viejo,
    )
    await _fila(
        integration_engine,
        "CERRADA-RECIENTE",
        is_processed=True,
        detail_fetched_at=AHORA - timedelta(days=2),
    )
    # Procesada sin licitación (detalle vacío), de antes del puntero.
    await _fila(
        integration_engine,
        "SIN-LICITACION",
        is_processed=True,
        updated_at=viejo,
    )
    await _fila(integration_engine, "PENDIENTE-VIEJA", created_at=muy_viejo)
    await _fila(
        integration_engine,
        "TERMINAL-VIEJA",
        discarded_at=muy_viejo,
        discard_reason="reintentos_agotados",
    )
    await _fila(
        integration_engine,
        "TERMINAL-RECIENTE",
        discarded_at=viejo,
        discard_reason="reintentos_agotados",
    )

    borradas = await servicio.purgar_cola(ahora=AHORA)

    assert await _codigos(integration_engine) == {
        "PUBLICADA-VIEJA",
        "CERRADA-RECIENTE",
        "PENDIENTE-VIEJA",
        "TERMINAL-RECIENTE",
    }
    assert borradas == 3
