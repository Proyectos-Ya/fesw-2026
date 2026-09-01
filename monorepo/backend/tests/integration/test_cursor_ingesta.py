"""El cursor: hasta dónde llegó la última corrida que listó su ventana entera.

Sin él, cada corrida pedía "las últimas 24 h desde ahora" y una ejecución que no
corría dejaba un hueco irrecuperable. Con un cron diario eso pasa de hipótesis a
rutina: basta un despliegue fallido a las 02:00.

La distinción que importa y que estos tests fijan: el cursor avanza cuando se
**listó** la ventana completa, no cuando se procesó todo. Son cosas distintas
porque la cola `tender_metadata` es persistente: una vez encolado el código, el
detalle lo retoma la corrida siguiente. Lo que no se puede perder es un tramo de
la ventana sin listar.
"""

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import IngestionRunModel
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.shared.datetime_utils import utc_now_naive
from app.shared.ingestion_window import PISO_VENTANA

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def servicio(integration_engine) -> TenderIngestionService:
    return TenderIngestionService(
        engine=integration_engine,
        client=None,  # type: ignore[arg-type]
        embedding_service=None,  # type: ignore[arg-type]
    )


async def _corrida(engine, *, status: str, hasta_hace: timedelta) -> None:
    hasta = utc_now_naive() - hasta_hace
    async with AsyncSession(engine) as s:
        s.add(
            IngestionRunModel(
                id=uuid.uuid4(),
                window_from=hasta - PISO_VENTANA,
                window_to=hasta,
                status=status,
                finished_at=hasta,
            )
        )
        await s.commit()


class TestLecturaDelCursor:
    async def test_sin_corridas_previas_la_ventana_es_el_piso(self, servicio):
        desde, hasta = await servicio.ventana_a_sincronizar()

        assert (hasta - desde) == PISO_VENTANA

    async def test_retoma_desde_la_ultima_corrida_buena(
        self, servicio, integration_engine
    ):
        await _corrida(integration_engine, status="ok", hasta_hace=timedelta(days=5))

        desde, hasta = await servicio.ventana_a_sincronizar()

        assert timedelta(days=4, hours=23) < (hasta - desde) < timedelta(days=5, hours=1)

    async def test_una_corrida_truncada_no_mueve_el_cursor(
        self, servicio, integration_engine
    ):
        """`partial` es justo el caso que el cursor viene a proteger."""
        await _corrida(integration_engine, status="ok", hasta_hace=timedelta(days=5))
        await _corrida(
            integration_engine, status="partial", hasta_hace=timedelta(hours=1)
        )

        desde, hasta = await servicio.ventana_a_sincronizar()

        assert (hasta - desde) > timedelta(days=4)

    async def test_una_corrida_fallida_no_mueve_el_cursor(
        self, servicio, integration_engine
    ):
        await _corrida(integration_engine, status="ok", hasta_hace=timedelta(days=3))
        await _corrida(
            integration_engine, status="failed", hasta_hace=timedelta(hours=1)
        )

        desde, hasta = await servicio.ventana_a_sincronizar()

        assert (hasta - desde) > timedelta(days=2)

    async def test_una_corrida_en_curso_no_mueve_el_cursor(
        self, servicio, integration_engine
    ):
        """Si no, dos corridas solapadas se pisarían la ventana."""
        await _corrida(integration_engine, status="ok", hasta_hace=timedelta(days=3))
        await _corrida(
            integration_engine, status="running", hasta_hace=timedelta(minutes=1)
        )

        desde, hasta = await servicio.ventana_a_sincronizar()

        assert (hasta - desde) > timedelta(days=2)


class TestRegistroDeCorridas:
    async def test_una_corrida_queda_registrada_de_punta_a_punta(
        self, servicio, integration_engine
    ):
        desde, hasta = await servicio.ventana_a_sincronizar()

        run_id = await servicio.registrar_inicio(desde, hasta)
        await servicio.registrar_fin(
            run_id, status="ok", listed=10, processed=8, failed=2
        )

        async with AsyncSession(integration_engine) as s:
            fila = await s.get(IngestionRunModel, run_id)
        assert fila is not None
        assert fila.status == "ok"
        assert (fila.listed, fila.processed, fila.failed) == (10, 8, 2)
        assert fila.finished_at is not None

    async def test_la_corrida_nace_en_running(self, servicio, integration_engine):
        """Si el proceso muere sin cerrarla, queda visible como colgada."""
        desde, hasta = await servicio.ventana_a_sincronizar()

        run_id = await servicio.registrar_inicio(desde, hasta)

        async with AsyncSession(integration_engine) as s:
            fila = await s.get(IngestionRunModel, run_id)
        assert fila is not None
        assert fila.status == "running"
        assert fila.finished_at is None

    async def test_el_cursor_avanza_tras_una_corrida_buena(
        self, servicio, integration_engine
    ):
        desde, hasta = await servicio.ventana_a_sincronizar()
        run_id = await servicio.registrar_inicio(desde, hasta)
        await servicio.registrar_fin(run_id, status="ok", listed=1)

        nueva_desde, _ = await servicio.ventana_a_sincronizar()

        # La ventana siguiente arranca donde terminó esta, salvo por el piso.
        assert nueva_desde >= desde
