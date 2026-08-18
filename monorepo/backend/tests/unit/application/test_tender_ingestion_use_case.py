"""
Tests unitarios de TenderIngestionUseCase.
Verifican que tras guardar cada licitación en SQL se genera su embedding
y se indexa en el repositorio vectorial (Qdrant).
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.application.repositories.tender_repository import ITenderRepository, TenderFilters
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.domain.entities.tender import Tender
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.models.tender_ingestion_dto import TenderIngestaDTO
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel
from tests.unit.application.fakes import FakeEmbeddingService, FakeTenderVectorRepository


# ---------------------------------------------------------------------------
# Fakes locales
# ---------------------------------------------------------------------------


class FakeTenderRepository(ITenderRepository):
    """Repositorio SQL en memoria que deja pasar todas las operaciones."""

    def __init__(self) -> None:
        self.saved: list = []

    async def get_tenders(self, filters: TenderFilters) -> List[Tender]:  # noqa: ARG002
        return []

    async def get_by_code(self, code: str) -> Optional[TenderModel]:  # noqa: ARG002
        return None

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:  # noqa: ARG002
        return rut

    async def get_or_create_status(self, status_id: int) -> int:
        return status_id

    async def save_complex_tender(self, tender_model: TenderModel, items: List[TenderItemModel]) -> None:
        self.saved.append((tender_model, items))

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(self, tender_id: UUID, supplier_id: UUID) -> Optional[DeepAnalysis]:
        return None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        return deep_analysis

    async def get_latest_tender_created_at(self) -> Optional[datetime]:
        return None


def _make_dto(code: str = "LIC-001", status_code: int = 1) -> TenderIngestaDTO:
    return TenderIngestaDTO.model_validate({
        "CodigoExterno": code,
        "Nombre": "Construcción de sede comunal",
        "Descripcion": "Se requiere construir edificio de 2 pisos",
        "CodigoEstado": status_code,
        "FechaPublicacion": "2026-01-01T00:00:00",
        "FechaCierre": "2026-06-30T23:59:00",
        "RutComprador": "12.345.678-9",
        "NombreOrganismo": "Municipalidad de Santiago",
        "UnidadCompra": "Depto. Obras",
        "RegionUnidad": "Región Metropolitana de Santiago",
        "MontoEstimado": 50_000_000.0,
        "items": [
            {"nombre_producto": "Mano de obra", "cantidad": 10, "unidad_medida": "hh"},
        ],
    })


# ---------------------------------------------------------------------------
# Tests de indexación vectorial
# ---------------------------------------------------------------------------


async def test_ingesta_indexa_licitacion_en_qdrant() -> None:
    """Cada licitación procesada genera exactamente un upsert en Qdrant."""
    vector_repo = FakeTenderVectorRepository()
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto())

    assert len(vector_repo.upserts) == 1


async def test_ingesta_dos_licitaciones_genera_dos_upserts() -> None:
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto("LIC-001"))
    await use_case.execute(_make_dto("LIC-002"))

    assert len(vector_repo.upserts) == 2


async def test_vector_almacenado_proviene_del_embedding_service() -> None:
    """El vector en Qdrant es el que devuelve el EmbeddingService, no uno hardcodeado."""
    fake_vector = [0.7] * 1024
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(fake_vector),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto())

    _, stored_vector, _ = vector_repo.upserts[0]
    assert stored_vector == fake_vector


async def test_embedding_service_llamado_una_vez_por_licitacion() -> None:
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(_make_dto())

    assert len(embedding_service.calls) == 1


async def test_texto_enviado_al_embedding_incluye_nombre_licitacion() -> None:
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(_make_dto())

    assert any("Construcción de sede comunal" in text for text in embedding_service.calls[0])


async def test_payload_qdrant_contiene_status_code_publicada() -> None:
    """El payload del punto en Qdrant tiene status_code='publicada' para licitaciones activas."""
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto(status_code=1))

    _, _, payload = vector_repo.upserts[0]
    assert payload["status_code"] == "publicada"


async def test_licitacion_duplicada_no_genera_upsert_en_qdrant() -> None:
    """Si el código ya existe en SQL no se llama a Qdrant."""
    class RepoConDuplicado(FakeTenderRepository):
        async def get_by_code(self, code: str) -> TenderModel:  # noqa: ARG002
            return TenderModel.__new__(TenderModel)  # simula que ya existe

    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=RepoConDuplicado(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto())

    assert len(vector_repo.upserts) == 0
