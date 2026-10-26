"""El puntero de cambios que el cron de estados deja en la cola (plan 305).

`registrar_punteros` decide en el mismo upsert si una licitación conocida tiene
que volver a bajarse. Lo decide el SQL y no el caso de uso porque la referencia,
`detail_fetched_at`, la escribe el ingest en paralelo: comparar contra una
lectura previa abre una carrera en la que un cambio queda sin bajar.

Reglas que protege:

- `nueva` solo crea filas: una que ya estaba (procesada, terminal o pendiente)
  no cambia de estado.
- `actualizar` solo si el cambio es posterior a la bajada, con un margen de
  5 min por la conversión de hora de Chile. No resetea `night_retries`, y
  `attempts` solo vuelve a 0 si la fila venía procesada.
- Una reapertura se encola sin condición y revive lo descartado por inactivo,
  pero no lo descartado por fallar siempre.
- `inactiva` pasa a terminal lo pendiente y no crea filas.
- La fecha de la API nunca retrocede, y repetir la llamada no cambia nada.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.models.cambio_estado import Intencion, PunteroDeCambio
from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)

pytestmark = pytest.mark.asyncio

BAJADA = datetime(2026, 10, 10, 12, 0)


@pytest_asyncio.fixture
async def servicio(integration_engine) -> TenderIngestionService:
    return TenderIngestionService(
        engine=integration_engine,
        client=None,  # type: ignore[arg-type]
        embedding_service=None,  # type: ignore[arg-type]
    )


async def _crear(engine, code: str, **campos) -> None:
    valores = {
        "id": uuid4(),
        "code": code,
        "is_processed": True,
        "attempts": 0,
        "detail_fetched_at": BAJADA,
        "created_at": BAJADA,
        "updated_at": BAJADA,
        **campos,
    }
    async with AsyncSession(engine) as s:
        s.add(TenderMetadataModel(**valores))
        await s.commit()


async def _fila(engine, code: str) -> TenderMetadataModel | None:
    async with AsyncSession(engine) as s:
        return (
            await s.exec(
                select(TenderMetadataModel).where(TenderMetadataModel.code == code)
            )
        ).first()


def _p(
    code: str,
    intencion: Intencion,
    *,
    changed_at: datetime | None = BAJADA + timedelta(hours=1),
    status: str = "publicada",
) -> PunteroDeCambio:
    return PunteroDeCambio(
        code=code, status_code=status, changed_at=changed_at, intencion=intencion
    )


class TestNueva:
    async def test_crea_la_fila_pendiente_con_el_puntero(
        self, servicio, integration_engine
    ):
        resultado = await servicio.registrar_punteros([_p("N", Intencion.NUEVA)])

        fila = await _fila(integration_engine, "N")
        assert fila is not None
        assert (fila.is_processed, fila.pending_reason) == (False, "nueva")
        assert fila.api_status_code == "publicada"
        assert fila.api_changed_at == BAJADA + timedelta(hours=1)
        assert resultado.nuevas == 1

    async def test_no_reabre_una_ya_procesada(self, servicio, integration_engine):
        """Procesada sin fila en `tender`: detalle vacío o de otra región."""
        await _crear(integration_engine, "N")

        resultado = await servicio.registrar_punteros([_p("N", Intencion.NUEVA)])

        fila = await _fila(integration_engine, "N")
        assert fila is not None
        assert fila.is_processed is True and fila.pending_reason is None
        assert fila.api_changed_at == BAJADA + timedelta(hours=1)
        assert resultado.nuevas == 0

    async def test_no_revive_una_terminal(self, servicio, integration_engine):
        await _crear(
            integration_engine,
            "N",
            is_processed=False,
            discarded_at=BAJADA,
            discard_reason="reintentos_agotados",
        )

        await servicio.registrar_punteros([_p("N", Intencion.NUEVA)])

        fila = await _fila(integration_engine, "N")
        assert fila is not None and fila.discarded_at == BAJADA


class TestActualizarSiCambio:
    async def test_un_cambio_posterior_a_la_bajada_la_encola(
        self, servicio, integration_engine
    ):
        await _crear(integration_engine, "A", attempts=2, night_retries=1)

        resultado = await servicio.registrar_punteros(
            [_p("A", Intencion.ACTUALIZAR_SI_CAMBIO)]
        )

        fila = await _fila(integration_engine, "A")
        assert fila is not None
        assert (fila.is_processed, fila.pending_reason) == (False, "actualizar")
        # Venía procesada: empieza de cero en el modo frecuente...
        assert fila.attempts == 0
        # ...pero los reintentos nocturnos no se regalan.
        assert fila.night_retries == 1
        assert resultado.actualizar == 1

    async def test_un_cambio_viejo_no_la_encola(self, servicio, integration_engine):
        await _crear(integration_engine, "A")

        resultado = await servicio.registrar_punteros(
            [
                _p(
                    "A",
                    Intencion.ACTUALIZAR_SI_CAMBIO,
                    changed_at=BAJADA - timedelta(hours=1),
                )
            ]
        )

        fila = await _fila(integration_engine, "A")
        assert fila is not None and fila.is_processed is True
        assert resultado.actualizar == 0

    async def test_un_cambio_dentro_del_margen_si_la_encola(
        self, servicio, integration_engine
    ):
        """Pudo no alcanzar a salir en el detalle que se pidió justo después."""
        await _crear(integration_engine, "A")

        await servicio.registrar_punteros(
            [
                _p(
                    "A",
                    Intencion.ACTUALIZAR_SI_CAMBIO,
                    changed_at=BAJADA - timedelta(minutes=2),
                )
            ]
        )

        fila = await _fila(integration_engine, "A")
        assert fila is not None and fila.pending_reason == "actualizar"

    async def test_sin_fecha_de_cambio_no_la_encola(self, servicio, integration_engine):
        await _crear(integration_engine, "A")

        await servicio.registrar_punteros(
            [_p("A", Intencion.ACTUALIZAR_SI_CAMBIO, changed_at=None)]
        )

        fila = await _fila(integration_engine, "A")
        assert fila is not None and fila.is_processed is True

    async def test_una_pendiente_conserva_sus_intentos(
        self, servicio, integration_engine
    ):
        """Resetearlos haría que una que falla siempre nunca llegue a la noche."""
        await _crear(
            integration_engine,
            "A",
            is_processed=False,
            attempts=1,
            pending_reason="actualizar",
        )

        await servicio.registrar_punteros([_p("A", Intencion.ACTUALIZAR_SI_CAMBIO)])

        fila = await _fila(integration_engine, "A")
        assert fila is not None and fila.attempts == 1

    async def test_no_revive_una_terminal(self, servicio, integration_engine):
        await _crear(
            integration_engine,
            "A",
            is_processed=False,
            discarded_at=BAJADA,
            discard_reason="reintentos_agotados",
        )

        await servicio.registrar_punteros([_p("A", Intencion.ACTUALIZAR_SI_CAMBIO)])

        fila = await _fila(integration_engine, "A")
        assert fila is not None and fila.discarded_at == BAJADA

    async def test_sin_fila_la_crea_pendiente(self, servicio, integration_engine):
        """Licitaciones cargadas desde un dump, sin fila en la cola."""
        await servicio.registrar_punteros([_p("A", Intencion.ACTUALIZAR_SI_CAMBIO)])

        fila = await _fila(integration_engine, "A")
        assert fila is not None
        assert (fila.is_processed, fila.pending_reason) == (False, "actualizar")


class TestReabierta:
    async def test_se_encola_aunque_el_cambio_sea_viejo(
        self, servicio, integration_engine
    ):
        await _crear(integration_engine, "R")

        await servicio.registrar_punteros(
            [_p("R", Intencion.REABIERTA, changed_at=BAJADA - timedelta(days=1))]
        )

        fila = await _fila(integration_engine, "R")
        assert fila is not None and fila.pending_reason == "actualizar"

    async def test_revive_lo_descartado_por_inactivo(
        self, servicio, integration_engine
    ):
        await _crear(
            integration_engine,
            "R",
            is_processed=False,
            discarded_at=BAJADA,
            discard_reason="inactiva_en_listado",
        )

        await servicio.registrar_punteros([_p("R", Intencion.REABIERTA)])

        fila = await _fila(integration_engine, "R")
        assert fila is not None
        assert fila.discarded_at is None and fila.discard_reason is None
        assert (fila.is_processed, fila.pending_reason) == (False, "actualizar")

    async def test_no_revive_lo_que_falla_siempre(self, servicio, integration_engine):
        await _crear(
            integration_engine,
            "R",
            is_processed=False,
            discarded_at=BAJADA,
            discard_reason="reintentos_agotados",
        )

        await servicio.registrar_punteros([_p("R", Intencion.REABIERTA)])

        fila = await _fila(integration_engine, "R")
        assert fila is not None and fila.discard_reason == "reintentos_agotados"


class TestInactiva:
    async def test_una_pendiente_pasa_a_terminal(self, servicio, integration_engine):
        await _crear(
            integration_engine, "I", is_processed=False, pending_reason="nueva"
        )

        resultado = await servicio.registrar_punteros(
            [_p("I", Intencion.INACTIVA, status="desierta")]
        )

        fila = await _fila(integration_engine, "I")
        assert fila is not None
        assert fila.discarded_at is not None
        assert fila.discard_reason == "inactiva_en_listado"
        assert fila.pending_reason is None
        assert fila.api_status_code == "desierta"
        assert resultado.descartadas == 1

    async def test_una_procesada_solo_guarda_el_estado(
        self, servicio, integration_engine
    ):
        await _crear(integration_engine, "I")

        resultado = await servicio.registrar_punteros(
            [_p("I", Intencion.INACTIVA, status="cerrada")]
        )

        fila = await _fila(integration_engine, "I")
        assert fila is not None
        assert fila.discarded_at is None and fila.api_status_code == "cerrada"
        assert resultado.descartadas == 0

    async def test_no_crea_filas(self, servicio, integration_engine):
        await servicio.registrar_punteros(
            [_p("X", Intencion.INACTIVA, status="cerrada")]
        )

        assert await _fila(integration_engine, "X") is None


class TestBordes:
    async def test_la_fecha_de_la_api_no_retrocede(self, servicio, integration_engine):
        await servicio.registrar_punteros([_p("N", Intencion.NUEVA)])
        await servicio.registrar_punteros(
            [_p("N", Intencion.NUEVA, changed_at=BAJADA - timedelta(days=1))]
        )

        fila = await _fila(integration_engine, "N")
        assert fila is not None and fila.api_changed_at == BAJADA + timedelta(hours=1)

    async def test_repetir_la_llamada_no_cambia_nada(
        self, servicio, integration_engine
    ):
        await _crear(integration_engine, "A")
        punteros = [
            _p("A", Intencion.ACTUALIZAR_SI_CAMBIO),
            _p("N", Intencion.NUEVA),
        ]

        await servicio.registrar_punteros(punteros)
        segunda = await servicio.registrar_punteros(punteros)

        assert (segunda.nuevas, segunda.actualizar, segunda.descartadas) == (0, 0, 0)

    async def test_un_codigo_repetido_no_rompe_el_upsert(self, servicio):
        """Postgres no deja que un ON CONFLICT toque la misma fila dos veces."""
        resultado = await servicio.registrar_punteros(
            [_p("N", Intencion.NUEVA), _p("N", Intencion.NUEVA)]
        )

        assert resultado.nuevas == 1

    async def test_lista_vacia(self, servicio):
        resultado = await servicio.registrar_punteros([])

        assert (resultado.nuevas, resultado.actualizar, resultado.descartadas) == (
            0,
            0,
            0,
        )
