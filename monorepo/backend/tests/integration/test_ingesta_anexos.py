"""La ingesta guarda la lista oficial de anexos que trae el detalle (plan 233, decisión 1).

Recorre el camino real con Postgres: alta, reingesta con la lista cambiada y
reingesta con un detalle que no trae `documentos`. El segundo paso cambia la
fecha de cierre a propósito: fuerza el camino "updated", que hace commit antes de
sincronizar los anexos. Si ahí se leyera un atributo expirado de la licitación,
la sesión async reventaría con MissingGreenlet y la licitación contaría como
fallida.
"""

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.repositories.tender_attachment_model import (
    TenderAttachmentModel,
)
from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.seeder import seed_database_metadata
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)

pytestmark = pytest.mark.asyncio

BASES = {"id": 1, "nombre": "Bases.pdf"}
ANEXO = {"id": 2, "nombre": "Anexo 1.docx"}


def _detalle(code: str, fecha_cierre: str, documentos: list[dict] | None) -> dict:
    detalle: dict[str, Any] = {
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
    if documentos is not None:
        detalle["documentos"] = documentos
    return detalle


class ClienteFalso:
    def __init__(
        self,
        documentos: list[dict] | None,
        fecha_cierre: str = "2026-12-01 10:00",
    ) -> None:
        self.documentos = documentos
        self.fecha_cierre = fecha_cierre

    async def get_tender_detail(self, code: str) -> dict:
        return _detalle(code, self.fecha_cierre, self.documentos)


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
        s.add(TenderMetadataModel(id=uuid.uuid4(), code="A"))
        await s.commit()
    return integration_engine


def _servicio(engine, cliente: ClienteFalso) -> TenderIngestionService:
    return TenderIngestionService(
        engine=engine,
        client=cliente,  # type: ignore[arg-type]
        embedding_service=EmbeddingFalso(),  # type: ignore[arg-type]
        tender_vector_repo=VectorRepoFalso(),  # type: ignore[arg-type]
    )


async def _filas(engine) -> list[TenderAttachmentModel]:
    async with AsyncSession(engine) as s:
        resultado = await s.exec(
            select(TenderAttachmentModel).order_by(
                col(TenderAttachmentModel.mp_document_id)
            )
        )
        return list(resultado.all())


async def test_la_ingesta_guarda_la_lista_y_la_reingesta_la_refresca(entorno):
    primera = await _servicio(entorno, ClienteFalso([BASES, ANEXO])).process_unprocessed_tenders()

    assert (primera.procesadas, primera.fallidas) == (1, 0)
    filas = await _filas(entorno)
    assert [f.mp_document_id for f in filas] == [1, 2]
    assert all(f.removed_at is None for f in filas)

    await _servicio(entorno, ClienteFalso([BASES])).reencolar(["A"])
    # Otra fecha de cierre: fuerza el camino "updated" (ver el docstring).
    segunda = await _servicio(
        entorno, ClienteFalso([BASES], fecha_cierre="2026-12-15 10:00")
    ).process_unprocessed_tenders()

    assert (segunda.procesadas, segunda.fallidas) == (1, 0)
    filas = await _filas(entorno)
    assert [(f.mp_document_id, f.removed_at is not None) for f in filas] == [
        (1, False),
        (2, True),
    ]


async def test_un_detalle_sin_documentos_no_toca_la_lista(entorno):
    await _servicio(entorno, ClienteFalso([BASES, ANEXO])).process_unprocessed_tenders()

    await _servicio(entorno, ClienteFalso(None)).reencolar(["A"])
    segunda = await _servicio(
        entorno, ClienteFalso(None, fecha_cierre="2026-12-15 10:00")
    ).process_unprocessed_tenders()

    assert (segunda.procesadas, segunda.fallidas) == (1, 0)
    filas = await _filas(entorno)
    assert [f.mp_document_id for f in filas] == [1, 2]
    assert all(f.removed_at is None for f in filas)
