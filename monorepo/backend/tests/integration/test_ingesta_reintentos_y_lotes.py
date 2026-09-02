"""La cola de ingesta no puede perder licitaciones ni clavar una conexión.

Tres defectos que estos tests fijan, los tres del mismo bucle:

1. **Un error de parseo perdía la licitación para siempre.** El `except
   Exception` marcaba `is_processed=True` "para no bloquear la cola". Si la API
   cambia un campo, eso quema la cuota del día y las licitaciones no vuelven a
   aparecer nunca, porque el listado deduplica por código.

2. **El SELECT no tenía LIMIT** y la sesión seguía abierta mientras se procesaba
   la cola entera. Con 5.000 pendientes son horas con una conexión del pooler de
   Supabase ocupada.

3. **Los detalles se pedían de a uno.** Con el detalle en ~3,3 s de mediana, una
   carga inicial de 5.000 licitaciones son ~4,6 h de las que más del 85% es
   espera de red.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.mercado_publico_client import (
    CuotaAgotadaError,
    ErrorTransitorioMercadoPublico,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    MAX_INTENTOS_INGESTA,
    TenderIngestionService,
)

pytestmark = pytest.mark.asyncio


def _detalle(code: str) -> dict:
    """Payload mínimo pero válido, con la forma que devuelve Compra Ágil v2."""
    return {
        "codigo": code,
        "nombre": f"Servicio {code}",
        "descripcion": "Descripción de prueba",
        "estado": {"id_estado": 2, "codigo": "publicada"},
        "fechas": {
            "fecha_publicacion": "2026-09-01T10:00:00Z",
            "fecha_cierre": "2026-12-01T10:00:00Z",
        },
        "institucion": {
            "rut": "61.000.000-0",
            "organismo_comprador": "Municipalidad de Santiago",
            "unidad_compra": "Abastecimiento",
            "region": 13,
            "nombre_region": "Región Metropolitana de Santiago",
        },
        "presupuesto": {"monto_disponible_clp": 1_000_000},
        "productos_solicitados": [
            {
                "codigo_producto": 4321,
                "nombre": "Producto",
                "descripcion": "Un producto",
                "cantidad": 1,
                "unidad_medida": "UN",
            }
        ],
    }


class ClienteFalso:
    """Cliente de Mercado Público controlable, que además mide concurrencia."""

    def __init__(self, comportamiento=None, demora: float = 0.0):
        self._comportamiento = comportamiento or {}
        self._demora = demora
        self.pedidos: list[str] = []
        self.en_vuelo = 0
        self.pico_en_vuelo = 0

    async def get_tender_detail(self, code: str) -> dict:
        self.pedidos.append(code)
        self.en_vuelo += 1
        self.pico_en_vuelo = max(self.pico_en_vuelo, self.en_vuelo)
        try:
            if self._demora:
                await asyncio.sleep(self._demora)
            accion = self._comportamiento.get(code)
            if isinstance(accion, Exception):
                raise accion
            if accion == "vacio":
                return {}
            if accion == "corrupto":
                # Detalle que revienta al mapear: no es un detalle vacío.
                return {"codigo": code, "fechas": "esto no es un dict"}
            return _detalle(code)
        finally:
            self.en_vuelo -= 1


class EmbeddingFalso:
    def __init__(self):
        self.llamadas = 0

    async def embed(self, textos: list[str]) -> list[list[float]]:
        self.llamadas += 1
        return [[0.1] * 1024 for _ in textos]


class VectorRepoFalso:
    def __init__(self):
        self.upserts: list[uuid.UUID] = []
        self.borrados: list[uuid.UUID] = []

    async def ensure_collection(self) -> None: ...

    async def upsert(self, tender_id, embedding, payload) -> None:
        self.upserts.append(tender_id)

    async def delete(self, tender_id) -> None:
        self.borrados.append(tender_id)

    async def search_by_vector(self, *a, **kw):
        return []

    async def count(self, *a, **kw):
        return 0


@pytest_asyncio.fixture
async def entorno(integration_engine, monkeypatch):
    """Base sembrada (regiones y estados) y sin la pausa entre peticiones.

    La pausa es real contra Mercado Público, pero acá el cliente es falso: lo
    único que aportaría es hacer la suite varios segundos más lenta.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "mercadopublico_detail_delay", 0.0)
    async with AsyncSession(integration_engine) as s:
        await seed_database_metadata(s)
    return integration_engine


async def _encolar(engine, codigos: list[str]) -> None:
    async with AsyncSession(engine) as s:
        for code in codigos:
            s.add(TenderMetadataModel(id=uuid.uuid4(), code=code))
        await s.commit()


async def _metadata(engine, code: str) -> TenderMetadataModel:
    async with AsyncSession(engine) as s:
        stmt = select(TenderMetadataModel).where(TenderMetadataModel.code == code)
        fila = (await s.exec(stmt)).one()
        return fila


def _servicio(engine, cliente, vector_repo=None) -> TenderIngestionService:
    return TenderIngestionService(
        engine=engine,
        client=cliente,  # type: ignore[arg-type]
        embedding_service=EmbeddingFalso(),  # type: ignore[arg-type]
        tender_vector_repo=vector_repo or VectorRepoFalso(),  # type: ignore[arg-type]
    )


class TestNoPerderLicitaciones:
    async def test_un_error_de_parseo_no_marca_procesada(self, entorno):
        """Antes se marcaba y la licitación no volvía a aparecer jamás."""
        await _encolar(entorno, ["ROTA-1"])
        cliente = ClienteFalso({"ROTA-1": "corrupto"})

        await _servicio(entorno, cliente).process_unprocessed_tenders()

        fila = await _metadata(entorno, "ROTA-1")
        assert fila.is_processed is False
        assert fila.attempts == 1
        assert fila.last_error

    async def test_se_rinde_al_llegar_al_maximo_de_intentos(self, entorno):
        """Un fallo permanente no puede bloquear la cola para siempre."""
        await _encolar(entorno, ["ROTA-1"])
        servicio = _servicio(entorno, ClienteFalso({"ROTA-1": "corrupto"}))

        for _ in range(MAX_INTENTOS_INGESTA):
            await servicio.process_unprocessed_tenders()

        fila = await _metadata(entorno, "ROTA-1")
        assert fila.attempts == MAX_INTENTOS_INGESTA
        assert fila.is_processed is True

    async def test_un_detalle_vacio_si_se_marca_de_inmediato(self, entorno):
        """Vacío significa que no hay nada que traer; reintentar no aporta."""
        await _encolar(entorno, ["VACIA-1"])

        await _servicio(
            entorno, ClienteFalso({"VACIA-1": "vacio"})
        ).process_unprocessed_tenders()

        fila = await _metadata(entorno, "VACIA-1")
        assert fila.is_processed is True
        assert fila.attempts == 0

    async def test_un_error_transitorio_deja_la_licitacion_pendiente(self, entorno):
        await _encolar(entorno, ["LENTA-1"])
        error = ErrorTransitorioMercadoPublico("timeout")

        await _servicio(
            entorno, ClienteFalso({"LENTA-1": error})
        ).process_unprocessed_tenders()

        fila = await _metadata(entorno, "LENTA-1")
        assert fila.is_processed is False
        assert fila.attempts == 1

    async def test_sin_cuota_no_se_marca_nada_ni_se_cuenta_el_intento(self, entorno):
        """La cuota agotada no es culpa de la licitación: no la penaliza."""
        await _encolar(entorno, ["SIN-CUOTA"])
        error = CuotaAgotadaError("cuota agotada")

        resultado = await _servicio(
            entorno, ClienteFalso({"SIN-CUOTA": error})
        ).process_unprocessed_tenders()

        fila = await _metadata(entorno, "SIN-CUOTA")
        assert fila.is_processed is False
        assert fila.attempts == 0
        assert resultado.cuota_agotada is True

    async def test_las_que_ya_fallaron_van_al_final_de_la_cola(self, entorno):
        """Con LIMIT, una fallona perpetua al frente congelaría el avance."""
        await _encolar(entorno, ["ROTA-1", "BUENA-1"])
        cliente = ClienteFalso({"ROTA-1": "corrupto"})
        servicio = _servicio(entorno, cliente)

        await servicio.process_unprocessed_tenders(limite=1)
        await servicio.process_unprocessed_tenders(limite=1)

        assert cliente.pedidos == ["ROTA-1", "BUENA-1"]


class TestLotesAcotados:
    async def test_no_procesa_mas_de_lo_pedido(self, entorno):
        await _encolar(entorno, [f"COD-{i}" for i in range(10)])
        cliente = ClienteFalso()

        resultado = await _servicio(entorno, cliente).process_unprocessed_tenders(
            limite=4
        )

        assert len(cliente.pedidos) == 4
        assert resultado.procesadas == 4

    async def test_rondas_sucesivas_vacian_la_cola(self, entorno):
        await _encolar(entorno, [f"COD-{i}" for i in range(10)])
        cliente = ClienteFalso()
        servicio = _servicio(entorno, cliente)

        for _ in range(3):
            await servicio.process_unprocessed_tenders(limite=4)

        assert len(cliente.pedidos) == 10


class TestConcurrencia:
    async def test_varios_detalles_en_vuelo_a_la_vez(self, entorno, monkeypatch):
        """El cuello de botella es la red, no el modelo: hay que solaparla."""
        from app.config import settings

        monkeypatch.setattr(settings, "mercadopublico_detail_concurrency", 4)
        monkeypatch.setattr(settings, "mercadopublico_detail_delay", 0.0)
        await _encolar(entorno, [f"COD-{i}" for i in range(8)])
        cliente = ClienteFalso(demora=0.05)

        await _servicio(entorno, cliente).process_unprocessed_tenders()

        assert cliente.pico_en_vuelo > 1
        assert cliente.pico_en_vuelo <= 4

    async def test_nunca_supera_el_limite_configurado(self, entorno, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "mercadopublico_detail_concurrency", 2)
        monkeypatch.setattr(settings, "mercadopublico_detail_delay", 0.0)
        await _encolar(entorno, [f"COD-{i}" for i in range(6)])
        cliente = ClienteFalso(demora=0.05)

        await _servicio(entorno, cliente).process_unprocessed_tenders()

        assert cliente.pico_en_vuelo <= 2


class TestIngestaCompleta:
    async def test_una_licitacion_valida_llega_a_sql_y_a_qdrant(self, entorno):
        await _encolar(entorno, ["OK-1"])
        vector_repo = VectorRepoFalso()

        resultado = await _servicio(
            entorno, ClienteFalso(), vector_repo
        ).process_unprocessed_tenders()

        fila = await _metadata(entorno, "OK-1")
        assert fila.is_processed is True
        assert resultado.procesadas == 1
        assert len(vector_repo.upserts) == 1

    async def test_no_vuelve_a_pedir_las_ya_procesadas(self, entorno):
        await _encolar(entorno, ["OK-1"])
        cliente = ClienteFalso()
        servicio = _servicio(entorno, cliente)

        await servicio.process_unprocessed_tenders()
        await servicio.process_unprocessed_tenders()

        assert cliente.pedidos == ["OK-1"]


class TestCarrerasEntreTareasConcurrentes:
    """Lo que la concurrencia rompió y hubo que arreglar en el repositorio.

    `get_or_create_buyer` y `get_or_create_status` hacían SELECT y después
    INSERT. Con las descargas en serie eso nunca falla; en paralelo, dos
    licitaciones del mismo organismo hacen el SELECT a la vez, las dos lo ven
    vacío, y la segunda revienta con UniqueViolationError.

    No es un caso raro: es el caso normal. Un municipio publica decenas de
    compras ágiles y todas comparten RUT comprador.
    """

    async def test_varias_licitaciones_del_mismo_organismo_a_la_vez(self, entorno):
        # Todas las que arma `_detalle` comparten comprador y estado.
        await _encolar(entorno, [f"MISMO-{i}" for i in range(6)])

        resultado = await _servicio(entorno, ClienteFalso()).process_unprocessed_tenders()

        assert resultado.procesadas == 6
        assert resultado.fallidas == 0

    async def test_el_organismo_se_crea_una_sola_vez(self, entorno):
        from app.infrastructure.repositories.tender_model import (
            BuyerInstitutionModel,
        )

        await _encolar(entorno, [f"MISMO-{i}" for i in range(6)])

        await _servicio(entorno, ClienteFalso()).process_unprocessed_tenders()

        async with AsyncSession(entorno) as s:
            compradores = (await s.exec(select(BuyerInstitutionModel))).all()
        assert len(compradores) == 1


class TestColaVacia:
    async def test_sin_pendientes_no_consulta_a_la_api(self, entorno):
        cliente = ClienteFalso()

        resultado = await _servicio(entorno, cliente).process_unprocessed_tenders()

        assert cliente.pedidos == []
        assert resultado.procesadas == 0
        assert resultado.cuota_agotada is False


class TestOrdenEstable:
    async def test_a_igual_intentos_se_respeta_el_orden_de_llegada(self, entorno):
        await _encolar(entorno, ["PRIMERA", "SEGUNDA"])
        async with AsyncSession(entorno) as s:
            stmt = select(TenderMetadataModel).where(
                col(TenderMetadataModel.code) == "PRIMERA"
            )
            fila = (await s.exec(stmt)).one()
            fila.created_at = fila.created_at.replace(year=2020)
            s.add(fila)
            await s.commit()
        cliente = ClienteFalso()

        await _servicio(entorno, cliente).process_unprocessed_tenders(limite=1)

        assert cliente.pedidos == ["PRIMERA"]
