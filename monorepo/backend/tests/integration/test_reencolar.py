"""Devolver a la cola licitaciones ya procesadas, para que el ingest las actualice.

El listado nocturno inserta con `ON CONFLICT DO NOTHING`: una licitación ya
procesada nunca vuelve a la cola, y `_actualizar` nunca se ejecutaba. El cron de
estados usa `reencolar` para las publicadas que cambiaron.
"""

import uuid

import pytest
import pytest_asyncio
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_model import (
    TenderMetadataModel,
    TenderModel,
)
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from app.shared.datetime_utils import fecha_mp_a_utc

pytestmark = pytest.mark.asyncio


def _detalle(code: str, fecha_cierre: str) -> dict:
    return {
        "codigo": code,
        "nombre": f"Servicio {code}",
        "descripcion": "Descripción de prueba",
        "estado": {"id_estado": 2, "codigo": "publicada"},
        "fechas": {
            "fecha_publicacion": "2026-09-01 10:00",
            "fecha_cierre": fecha_cierre,
        },
        "institucion": {
            "rut": "61.000.000-0",
            "organismo_comprador": "Municipalidad de Santiago",
            "unidad_compra": "Abastecimiento",
            "region": 13,
            "nombre_region": "Región Metropolitana de Santiago",
        },
        "presupuesto": {"monto_disponible_clp": 1_000_000},
        "productos_solicitados": [],
    }


class ClienteFalso:
    def __init__(self, fecha_cierre: str = "2026-12-01 10:00") -> None:
        self.fecha_cierre = fecha_cierre

    async def get_tender_detail(self, code: str) -> dict:
        return _detalle(code, self.fecha_cierre)


class EmbeddingFalso:
    async def embed(self, textos: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in textos]


class VectorRepoFalso:
    async def upsert(self, tender_id, embedding, payload) -> None: ...

    async def set_payload(self, tender_id, payload) -> None: ...

    async def delete(self, tender_id) -> None: ...


@pytest_asyncio.fixture
async def entorno(integration_engine, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "mercadopublico_detail_delay", 0.0)
    async with AsyncSession(integration_engine) as s:
        await seed_database_metadata(s)
    return integration_engine


def _servicio(engine, cliente: ClienteFalso) -> TenderIngestionService:
    return TenderIngestionService(
        engine=engine,
        client=cliente,  # type: ignore[arg-type]
        embedding_service=EmbeddingFalso(),  # type: ignore[arg-type]
        tender_vector_repo=VectorRepoFalso(),  # type: ignore[arg-type]
    )


async def _fila(engine, code: str) -> TenderMetadataModel:
    async with AsyncSession(engine) as s:
        stmt = select(TenderMetadataModel).where(TenderMetadataModel.code == code)
        return (await s.exec(stmt)).one()


async def _procesada_con_error(engine, code: str) -> None:
    async with AsyncSession(engine) as s:
        s.add(
            TenderMetadataModel(
                id=uuid.uuid4(),
                code=code,
                is_processed=True,
                attempts=2,
                last_error="HTTP 500",
            )
        )
        await s.commit()


class TestReencolar:
    async def test_una_procesada_vuelve_a_quedar_pendiente_y_limpia(self, entorno):
        await _procesada_con_error(entorno, "A")

        reencoladas = await _servicio(entorno, ClienteFalso()).reencolar(["A"])

        fila = await _fila(entorno, "A")
        assert reencoladas == 1
        assert fila.is_processed is False
        assert fila.attempts == 0
        assert fila.last_error is None

    async def test_un_codigo_sin_fila_en_la_cola_se_inserta(self, entorno):
        """Una licitación cargada desde un dump no pasó nunca por la cola."""
        reencoladas = await _servicio(entorno, ClienteFalso()).reencolar(["DUMP-1"])

        assert reencoladas == 1
        assert (await _fila(entorno, "DUMP-1")).is_processed is False

    async def test_codigos_repetidos_no_fallan(self, entorno):
        reencoladas = await _servicio(entorno, ClienteFalso()).reencolar(["A", "A"])

        assert reencoladas == 1

    async def test_lista_vacia(self, entorno):
        assert await _servicio(entorno, ClienteFalso()).reencolar([]) == 0


class TestElIngestActualizaLaReencolada:
    async def test_pasa_por_actualizar_sin_duplicar(self, entorno):
        async with AsyncSession(entorno) as s:
            s.add(TenderMetadataModel(id=uuid.uuid4(), code="A"))
            await s.commit()
        await _servicio(entorno, ClienteFalso()).process_unprocessed_tenders()

        # La API amplió el plazo; el cron de estados la reencola.
        cliente = ClienteFalso(fecha_cierre="2026-12-15 10:00")
        await _servicio(entorno, cliente).reencolar(["A"])
        await _servicio(entorno, cliente).process_unprocessed_tenders()

        async with AsyncSession(entorno) as s:
            filas = (
                await s.exec(select(TenderModel).where(TenderModel.code == "A"))
            ).all()
            total = (await s.exec(select(func.count()).select_from(TenderModel))).one()
        assert total == 1
        assert filas[0].closing_at == fecha_mp_a_utc("2026-12-15 10:00")
        assert (await _fila(entorno, "A")).is_processed is True
