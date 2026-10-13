"""La cola de ingesta con modos, cortacircuito y estado terminal (plan 305).

Reglas que protege:

- **`NUEVAS`** baja solo lo que nunca falló, con las `nueva` antes que las
  `actualizar`. Es lo que corre cada 2 h: una que falla queda para la noche.
- **`REINTENTOS`** es la pasada nocturna. Toma lo que falló antes de que
  empezara la corrida y gasta un reintento nocturno por fila. Al quinto fallo,
  la fila pasa a terminal.
- **Terminal** (`discarded_at`) no se vuelve a pedir en ningún modo. Un error
  que no es de la API, al tercer intento, también termina ahí.
- **Cortacircuito.** Diez errores transitorios seguidos cortan la pasada sin
  cobrarle intentos a las filas que no se alcanzaron a pedir.
- **Carrera con el cron de estados.** Si el listado vio un cambio posterior al
  pedido del detalle, no se escribe ese detalle viejo: la fila queda pendiente.
"""

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlmodel import update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.tender_ingestion_service import ModoCola
from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.mercado_publico_client import (
    ErrorTransitorioMercadoPublico,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    MAX_INTENTOS_INGESTA,
    MAX_REINTENTOS_NOCTURNOS,
    UMBRAL_CORTACIRCUITO,
)
from app.shared.datetime_utils import utc_now_naive
from scripts.ingesta_compartida import contar_pendientes
from tests.integration.test_ingesta_reintentos_y_lotes import (
    ClienteFalso,
    VectorRepoFalso,
    _encolar,
    _metadata,
    _servicio,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def entorno(integration_engine, monkeypatch):
    """Base sembrada y sin la pausa entre peticiones, como en la suite de la cola."""
    from app.config import settings

    monkeypatch.setattr(settings, "mercadopublico_detail_delay", 0.0)
    async with AsyncSession(integration_engine) as s:
        await seed_database_metadata(s)
    return integration_engine


async def _ajustar(engine, code: str, **campos) -> None:
    async with AsyncSession(engine) as s:
        await s.exec(  # type: ignore[call-overload]
            update(TenderMetadataModel)
            .where(TenderMetadataModel.code == code)  # type: ignore[arg-type]
            .values(**campos)
        )
        await s.commit()


class TestModoNuevas:
    async def test_solo_toma_las_que_nunca_fallaron(self, entorno):
        await _encolar(entorno, ["OK-1", "FALLO-1"])
        await _ajustar(entorno, "FALLO-1", attempts=1)
        cliente = ClienteFalso()

        await _servicio(entorno, cliente).process_unprocessed_tenders(
            modo=ModoCola.NUEVAS
        )

        assert cliente.pedidos == ["OK-1"]

    async def test_las_nuevas_van_antes_que_las_de_actualizar(
        self, entorno, monkeypatch
    ):
        from app.config import settings

        monkeypatch.setattr(settings, "mercadopublico_detail_concurrency", 1)
        await _encolar(entorno, ["ACT-1", "NUEVA-1"])
        await _ajustar(entorno, "ACT-1", pending_reason="actualizar")
        await _ajustar(entorno, "NUEVA-1", pending_reason="nueva")
        cliente = ClienteFalso()

        await _servicio(entorno, cliente).process_unprocessed_tenders(
            modo=ModoCola.NUEVAS
        )

        assert cliente.pedidos == ["NUEVA-1", "ACT-1"]

    async def test_una_que_falla_queda_para_la_noche(self, entorno):
        await _encolar(entorno, ["CAE-1"])
        servicio = _servicio(
            entorno, ClienteFalso({"CAE-1": ErrorTransitorioMercadoPublico("504")})
        )

        await servicio.process_unprocessed_tenders(modo=ModoCola.NUEVAS)
        segunda = await servicio.process_unprocessed_tenders(modo=ModoCola.NUEVAS)

        fila = await _metadata(entorno, "CAE-1")
        assert fila.attempts == 1 and fila.night_retries == 0
        assert segunda.procesadas == segunda.fallidas == 0

    async def test_contar_coincide_con_lo_que_toma(self, entorno):
        await _encolar(entorno, ["A", "B", "C"])
        await _ajustar(entorno, "B", attempts=1)
        await _ajustar(entorno, "C", discarded_at=utc_now_naive())

        assert await contar_pendientes(entorno, ModoCola.NUEVAS) == 1
        assert await contar_pendientes(entorno, ModoCola.TODAS) == 2


class TestModoReintentos:
    async def test_un_fallo_gasta_un_reintento_nocturno(self, entorno):
        await _encolar(entorno, ["CAE-1"])
        await _ajustar(entorno, "CAE-1", attempts=1)
        servicio = _servicio(
            entorno, ClienteFalso({"CAE-1": ErrorTransitorioMercadoPublico("504")})
        )

        await servicio.process_unprocessed_tenders(
            modo=ModoCola.REINTENTOS, antes_de=utc_now_naive()
        )

        fila = await _metadata(entorno, "CAE-1")
        assert fila.night_retries == 1
        assert fila.discarded_at is None

    async def test_al_quinto_fallo_pasa_a_terminal(self, entorno):
        await _encolar(entorno, ["CAE-1"])
        await _ajustar(
            entorno,
            "CAE-1",
            attempts=1,
            night_retries=MAX_REINTENTOS_NOCTURNOS - 1,
        )
        servicio = _servicio(
            entorno, ClienteFalso({"CAE-1": ErrorTransitorioMercadoPublico("504")})
        )

        await servicio.process_unprocessed_tenders(
            modo=ModoCola.REINTENTOS, antes_de=utc_now_naive()
        )

        fila = await _metadata(entorno, "CAE-1")
        assert fila.discarded_at is not None
        assert fila.discard_reason == "reintentos_agotados"
        assert fila.pending_reason is None

    async def test_un_reintento_que_entra_queda_procesado(self, entorno):
        await _encolar(entorno, ["VUELVE-1"])
        await _ajustar(entorno, "VUELVE-1", attempts=2, night_retries=3)

        await _servicio(entorno, ClienteFalso()).process_unprocessed_tenders(
            modo=ModoCola.REINTENTOS, antes_de=utc_now_naive()
        )

        fila = await _metadata(entorno, "VUELVE-1")
        assert fila.is_processed is True and fila.discarded_at is None

    async def test_no_toma_las_que_fallaron_en_esta_misma_corrida(self, entorno):
        """Reintentarlas minutos después, en la misma ráfaga de 504, no sirve."""
        inicio = utc_now_naive()
        await _encolar(entorno, ["RECIEN-1"])
        await _ajustar(
            entorno,
            "RECIEN-1",
            attempts=1,
            updated_at=inicio + timedelta(minutes=1),
        )
        cliente = ClienteFalso()

        await _servicio(entorno, cliente).process_unprocessed_tenders(
            modo=ModoCola.REINTENTOS, antes_de=inicio
        )

        assert cliente.pedidos == []

    async def test_no_toma_las_que_nunca_fallaron(self, entorno):
        await _encolar(entorno, ["NUEVA-1"])
        cliente = ClienteFalso()

        await _servicio(entorno, cliente).process_unprocessed_tenders(
            modo=ModoCola.REINTENTOS, antes_de=utc_now_naive() + timedelta(hours=1)
        )

        assert cliente.pedidos == []


class TestTerminal:
    @pytest.mark.parametrize("modo", list(ModoCola))
    async def test_ningun_modo_pide_una_terminal(self, entorno, modo):
        await _encolar(entorno, ["MUERTA-1"])
        await _ajustar(
            entorno,
            "MUERTA-1",
            attempts=1,
            discarded_at=utc_now_naive() - timedelta(days=1),
            updated_at=utc_now_naive() - timedelta(days=1),
        )
        cliente = ClienteFalso()

        await _servicio(entorno, cliente).process_unprocessed_tenders(
            modo=modo, antes_de=utc_now_naive()
        )

        assert cliente.pedidos == []

    async def test_un_error_que_no_es_de_la_api_termina_en_terminal(self, entorno):
        await _encolar(entorno, ["ROTA-1"])
        servicio = _servicio(entorno, ClienteFalso({"ROTA-1": "corrupto"}))

        for _ in range(MAX_INTENTOS_INGESTA):
            await servicio.process_unprocessed_tenders()

        fila = await _metadata(entorno, "ROTA-1")
        assert fila.discarded_at is not None
        assert fila.discard_reason == "abandono_por_error"


class TestCortacircuito:
    async def test_corta_la_pasada_sin_cobrar_a_las_que_no_pidio(
        self, entorno, monkeypatch
    ):
        from app.config import settings

        monkeypatch.setattr(settings, "mercadopublico_detail_concurrency", 1)
        codigos = [f"CAE-{i:02d}" for i in range(UMBRAL_CORTACIRCUITO + 5)]
        await _encolar(entorno, codigos)
        cliente = ClienteFalso(
            {c: ErrorTransitorioMercadoPublico("504") for c in codigos}
        )

        resultado = await _servicio(entorno, cliente).process_unprocessed_tenders(
            modo=ModoCola.NUEVAS
        )

        assert resultado.api_caida is True
        assert len(cliente.pedidos) == UMBRAL_CORTACIRCUITO
        sin_pedir = await _metadata(entorno, codigos[-1])
        assert sin_pedir.attempts == 0

    async def test_un_exito_reinicia_la_cuenta(self, entorno, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "mercadopublico_detail_concurrency", 1)
        fallan = [f"CAE-{i:02d}" for i in range(UMBRAL_CORTACIRCUITO - 1)]
        codigos = [*fallan, "OK-50", *[f"CAE-B{i}" for i in range(3)]]
        await _encolar(entorno, codigos)
        comportamiento = {
            c: ErrorTransitorioMercadoPublico("504") for c in codigos if c != "OK-50"
        }

        resultado = await _servicio(
            entorno, ClienteFalso(comportamiento)
        ).process_unprocessed_tenders(modo=ModoCola.NUEVAS)

        assert resultado.api_caida is False


class ClienteQueCambiaDuranteElPedido(ClienteFalso):
    """Simula que el cron de estados vio un cambio mientras se bajaba el detalle."""

    def __init__(self, engine, desfase: timedelta):
        super().__init__()
        self.engine = engine
        self.desfase = desfase

    async def get_tender_detail(self, code: str) -> dict:
        detalle = await super().get_tender_detail(code)
        await _ajustar(self.engine, code, api_changed_at=utc_now_naive() + self.desfase)
        return detalle


class TestCarreraConElCronDeEstados:
    async def test_procesada_guarda_cuando_se_pidio_y_limpia_la_etiqueta(self, entorno):
        await _encolar(entorno, ["OK-1"])
        await _ajustar(entorno, "OK-1", pending_reason="nueva")
        antes = utc_now_naive()

        await _servicio(entorno, ClienteFalso()).process_unprocessed_tenders(
            modo=ModoCola.NUEVAS
        )

        fila = await _metadata(entorno, "OK-1")
        assert fila.is_processed is True and fila.pending_reason is None
        assert fila.detail_fetched_at is not None and fila.detail_fetched_at >= antes

    async def test_un_cambio_posterior_al_pedido_no_escribe_el_detalle(self, entorno):
        await _encolar(entorno, ["CAMBIA-1"])
        vectores = VectorRepoFalso()
        cliente = ClienteQueCambiaDuranteElPedido(entorno, timedelta(minutes=1))

        resultado = await _servicio(
            entorno, cliente, vectores
        ).process_unprocessed_tenders(modo=ModoCola.NUEVAS)

        fila = await _metadata(entorno, "CAMBIA-1")
        assert vectores.upserts == []
        assert (fila.is_processed, fila.pending_reason) == (False, "actualizar")
        assert fila.attempts == 0
        assert resultado.desactualizadas == 1

    async def test_un_cambio_dentro_del_margen_la_deja_para_otra_bajada(self, entorno):
        """El cambio pudo no alcanzar a salir en el detalle: se pide otra vez."""
        await _encolar(entorno, ["CAMBIA-1"])
        cliente = ClienteQueCambiaDuranteElPedido(entorno, -timedelta(minutes=2))
        vectores = VectorRepoFalso()

        await _servicio(entorno, cliente, vectores).process_unprocessed_tenders(
            modo=ModoCola.NUEVAS
        )

        fila = await _metadata(entorno, "CAMBIA-1")
        assert len(vectores.upserts) == 1
        assert (fila.is_processed, fila.pending_reason) == (False, "actualizar")


class ClienteSinFechas(ClienteFalso):
    async def get_tender_detail(self, code: str) -> dict:
        detalle = await super().get_tender_detail(code)
        detalle["fechas"] = {"fecha_publicacion": "2026-09-01 10:00"}
        return detalle


class TestDetalleSinFechas:
    async def test_no_se_guarda_con_la_hora_actual(self, entorno):
        """El parser ponía "ahora" en la fecha que faltaba, y `_actualizar` lo
        leía como un cambio de cierre. Con las `actualizar` del cron de estados
        ese camino deja de ser raro (plan 305)."""
        await _encolar(entorno, ["SIN-FECHA-1"])
        vectores = VectorRepoFalso()

        await _servicio(
            entorno, ClienteSinFechas(), vectores
        ).process_unprocessed_tenders()

        fila = await _metadata(entorno, "SIN-FECHA-1")
        assert vectores.upserts == []
        assert fila.is_processed is False
        assert fila.attempts == 1
        assert "fecha_cierre" in (fila.last_error or "")
