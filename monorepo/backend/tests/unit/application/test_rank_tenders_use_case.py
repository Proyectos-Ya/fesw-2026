import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from typing import Optional

from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.repositories.tender_repository import ITenderRepository, TenderFilters
from app.application.repositories.tender_vector_repository import ITenderVectorRepository
from app.application.repositories.matching_result_repository import IMatchingResultRepository
from app.application.services.reranker_service import IRerankerService
from app.application.services.weighting_service import IWeightingService
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.domain.entities.matching_result import MatchingResult
from app.domain.errors.supplier_errors import SupplierNotFoundForUser, SupplierVectorNotFound
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import InMemorySupplierRepository, FakeSupplierVectorRepository


# ---------------------------------------------------------------------------
# Implementaciones fake específicas para las pruebas unitarias de este caso de uso
# ---------------------------------------------------------------------------

from app.infrastructure.repositories.tender_model import TenderModel, TenderItemModel
from app.domain.entities.deep_analysis import DeepAnalysis

class InMemoryTenderRepository(ITenderRepository):
    """Fake repository en memoria para licitaciones."""
    def __init__(self) -> None:
        self.tenders: dict[UUID, Tender] = {}

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:
        results = []
        for t in self.tenders.values():
            if filters.ids and t.id not in filters.ids:
                continue
            if filters.regions:
                # En memoria asumimos que coincide para simplificar
                pass
            results.append(t)
        return results

    async def get_by_code(self, code: str) -> Optional[TenderModel]:
        return None

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:
        return rut

    async def save_complex_tender(self, tender_model: TenderModel, items: list[TenderItemModel]) -> None:
        pass

    async def get_or_create_status(self, status_id: int) -> int:
        return status_id

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(self, tender_id: UUID, supplier_id: UUID) -> Optional[DeepAnalysis]:
        return None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        return deep_analysis


class FakeTenderVectorRepository(ITenderVectorRepository):
    """Fake repository vectorial para buscar licitaciones."""
    def __init__(self) -> None:
        self.search_results: list[tuple[UUID, float]] = []
        self.searched_vectors: list[list[float]] = []
        self.deleted: list[UUID] = []

    async def ensure_collection(self) -> None:
        pass

    async def upsert(self, tender_id: UUID, embedding: list[float], payload: dict) -> None:
        pass

    async def delete(self, tender_id: UUID) -> None:
        self.deleted.append(tender_id)

    async def search_by_supplier_vector(
        self,
        supplier_vector: list[float],
        limit: int,
        filters: Optional[dict] = None,
    ) -> list[tuple[UUID, float]]:
        self.searched_vectors.append(supplier_vector)
        return self.search_results


class InMemoryMatchingResultRepository(IMatchingResultRepository):
    """Fake repository para caché de resultados de matching."""
    def __init__(self) -> None:
        self.results: dict[UUID, list[MatchingResult]] = {}

    async def save_bulk(self, results: list[MatchingResult]) -> None:
        if not results:
            return
        supplier_id = results[0].supplier_id
        if supplier_id not in self.results:
            self.results[supplier_id] = []
        self.results[supplier_id].extend(results)

    async def get_by_supplier_id(self, supplier_id: UUID) -> list[MatchingResult]:
        return self.results.get(supplier_id, [])

    async def delete_by_supplier_id(self, supplier_id: UUID) -> None:
        self.results.pop(supplier_id, None)

    async def get_by_proveedor_and_licitacion(
        self, proveedor_id: UUID, licitacion_id: UUID
    ) -> MatchingResult | None:
        for r in self.results.get(proveedor_id, []):
            if r.tender_id == licitacion_id:
                return r
        return None



class FakeRerankerService(IRerankerService):
    """Fake service para simular el re-ranker ONNX."""
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[tuple[UUID, str]], int]] = []

    async def rerank(
        self,
        query_text: str,
        candidates: list[tuple[UUID, str]],
        limit: int,
    ) -> list[tuple[UUID, float]]:
        self.calls.append((query_text, candidates, limit))
        # Retorna el mismo orden pero con un score simulado decreciente
        return [(uid, 1.0 - (i * 0.05)) for i, (uid, _) in enumerate(candidates)][:limit]


class FakeWeightingService(IWeightingService):
    """Fake service para simular ponderación manual por campos."""
    def calculate_scores(
        self, candidates: list[tuple[Tender, float]], supplier: Supplier
    ) -> list[tuple[UUID, float]]:
        # Asigna un score decreciente para cada candidato para simular el resultado de la ponderación
        return [(t.id, 0.95 - (i * 0.05)) for i, (t, _) in enumerate(candidates)]


# ---------------------------------------------------------------------------
# Helpers para creación de entidades dummy
# ---------------------------------------------------------------------------

def create_dummy_tender(
    tender_id: UUID,
    closing_in_hours: int = 24,
    status_code: str = TENDER_STATUSES["PUBLISHED"],
) -> Tender:
    """Helper para crear una licitación dummy con parámetros de prueba."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"COT-{tender_id}",
        name="Licitación de Prueba",
        description="Descripción de prueba",
        status_id=1,
        status_code=status_code,
        published_at=now - timedelta(days=1),
        closing_at=now + timedelta(hours=closing_in_hours),
        last_change_at=now,
        buyer_rut="12.345.678-9",
        buyer_name="Municipalidad de Santiago",
        buyer_unit="TI",
        items=[],
    )


# ---------------------------------------------------------------------------
# Pruebas Unitarias
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supplier_not_found_raises_exception() -> None:
    """Valida que si no se encuentra un proveedor asociado al usuario se lance la excepción correcta."""
    supplier_repo = InMemorySupplierRepository()
    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=FakeSupplierVectorRepository(),
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_repo=InMemoryTenderRepository(),
        reranker_service=FakeRerankerService(),
        weighting_service=FakeWeightingService(),
        matching_result_repo=InMemoryMatchingResultRepository(),
    )

    with pytest.raises(SupplierNotFoundForUser):
        await use_case.execute(user_id=uuid4())


@pytest.mark.asyncio
async def test_supplier_vector_not_found_raises_exception() -> None:
    """Valida que si el proveedor existe pero no tiene vector indexado en Qdrant se lance una excepción personalizada."""
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    # No agregamos el vector a vector_repo de manera intencional

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_repo=InMemoryTenderRepository(),
        reranker_service=FakeRerankerService(),
        weighting_service=FakeWeightingService(),
        matching_result_repo=InMemoryMatchingResultRepository(),
    )

    with pytest.raises(SupplierVectorNotFound):
        await use_case.execute(user_id=user_id)


@pytest.mark.asyncio
async def test_cache_hit_returns_immediately_without_pipeline() -> None:
    """Valida que si existen recomendaciones en cache y no se fuerza el refresco, se retornen de inmediato sin invocar a Qdrant ni Reranker."""
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    vector_repo.upsert(supplier.id, [0.1] * 1024)

    # Licitaciones a hidratar
    tender_id_1 = uuid4()
    tender_id_2 = uuid4()
    tender_repo = InMemoryTenderRepository()
    tender_repo.tenders[tender_id_1] = create_dummy_tender(tender_id_1)
    tender_repo.tenders[tender_id_2] = create_dummy_tender(tender_id_2)

    # Resultados cacheados
    matching_result_repo = InMemoryMatchingResultRepository()
    cached = [
        MatchingResult(
            supplier_id=supplier.id,
            tender_id=tender_id_1,
            similarity_score=0.85,
            reranker_score=0.90,
            final_score=0.92,
            model_version="bge-m3-v1",
        ),
        MatchingResult(
            supplier_id=supplier.id,
            tender_id=tender_id_2,
            similarity_score=0.80,
            reranker_score=0.88,
            final_score=0.89,
            model_version="bge-m3-v1",
        )
    ]
    await matching_result_repo.save_bulk(cached)

    tender_vector_repo = FakeTenderVectorRepository()
    reranker = FakeRerankerService()

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        reranker_service=reranker,
        weighting_service=FakeWeightingService(),
        matching_result_repo=matching_result_repo,
    )

    results = await use_case.execute(user_id=user_id, force_refresh=False)

    # Verificaciones
    assert len(results) == 2
    assert results[0].tender_id == tender_id_1
    assert results[0].tender is not None
    assert results[0].tender.id == tender_id_1
    # Asegura que el pipeline no se corrió
    assert len(tender_vector_repo.searched_vectors) == 0
    assert len(reranker.calls) == 0


@pytest.mark.asyncio
async def test_cache_miss_runs_full_pipeline_and_persists() -> None:
    """Valida que si no hay caché de recomendaciones, se ejecute la búsqueda vectorial, re-ranking y ponderaciones, persistiendo el resultado final."""
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    vector_repo.upsert(supplier.id, [0.5] * 1024)

    tender_id_1 = uuid4()
    tender_id_2 = uuid4()
    tender_repo = InMemoryTenderRepository()
    tender_repo.tenders[tender_id_1] = create_dummy_tender(tender_id_1)
    tender_repo.tenders[tender_id_2] = create_dummy_tender(tender_id_2)

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = [(tender_id_1, 0.85), (tender_id_2, 0.78)]

    matching_result_repo = InMemoryMatchingResultRepository()
    reranker = FakeRerankerService()

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        reranker_service=reranker,
        weighting_service=FakeWeightingService(),
        matching_result_repo=matching_result_repo,
    )

    results = await use_case.execute(user_id=user_id)

    # Verificaciones
    assert len(results) == 2
    assert results[0].tender_id == tender_id_1
    assert results[0].final_score == pytest.approx(0.95)
    assert results[1].final_score == pytest.approx(0.90)
    assert results[0].tender.id == tender_id_1

    # Asegura que se llamó a Qdrant y al Reranker
    assert len(tender_vector_repo.searched_vectors) == 1
    assert len(reranker.calls) == 1

    # Asegura que las recomendaciones se persistieron en el repositorio de base de datos
    saved_cache = await matching_result_repo.get_by_supplier_id(supplier.id)
    assert len(saved_cache) == 2
    assert saved_cache[0].tender_id == tender_id_1


@pytest.mark.asyncio
async def test_closed_tenders_are_filtered_out() -> None:
    """Valida que aquellas licitaciones expiradas por fecha o en estados diferentes a 'publicada' se descarten del resultado."""
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    vector_repo.upsert(supplier.id, [0.1] * 1024)

    tender_id_active = uuid4()
    tender_id_expired = uuid4()
    tender_id_closed_status = uuid4()

    tender_repo = InMemoryTenderRepository()
    # Activa
    tender_repo.tenders[tender_id_active] = create_dummy_tender(tender_id_active, closing_in_hours=10)
    # Expirada por fecha
    tender_repo.tenders[tender_id_expired] = create_dummy_tender(tender_id_expired, closing_in_hours=-2)
    # Expirada por estado 'cerrada'
    tender_repo.tenders[tender_id_closed_status] = create_dummy_tender(
        tender_id_closed_status, closing_in_hours=10, status_code=TENDER_STATUSES["CLOSED"]
    )

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = [
        (tender_id_active, 0.90),
        (tender_id_expired, 0.85),
        (tender_id_closed_status, 0.80),
    ]

    matching_result_repo = InMemoryMatchingResultRepository()

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        reranker_service=FakeRerankerService(),
        weighting_service=FakeWeightingService(),
        matching_result_repo=matching_result_repo,
    )

    results = await use_case.execute(user_id=user_id)

    # Verificaciones: Solo la activa debe ser retornada
    assert len(results) == 1
    assert results[0].tender_id == tender_id_active
    assert results[0].tender.id == tender_id_active


@pytest.mark.asyncio
async def test_orphan_vectors_are_deleted_from_vector_store() -> None:
    """Valida que los IDs retornados por Qdrant sin fila correspondiente en SQL
    (puntos huérfanos) se eliminen del almacén vectorial y no bloqueen los resultados."""
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    vector_repo.upsert(supplier.id, [0.1] * 1024)

    tender_id_valid = uuid4()
    tender_id_orphan = uuid4()  # Existe en Qdrant pero no en SQL

    tender_repo = InMemoryTenderRepository()
    tender_repo.tenders[tender_id_valid] = create_dummy_tender(tender_id_valid)

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = [
        (tender_id_valid, 0.90),
        (tender_id_orphan, 0.88),
    ]

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        reranker_service=FakeRerankerService(),
        weighting_service=FakeWeightingService(),
        matching_result_repo=InMemoryMatchingResultRepository(),
    )

    results = await use_case.execute(user_id=user_id)

    # La válida se retorna y el huérfano se limpia de Qdrant
    assert len(results) == 1
    assert results[0].tender_id == tender_id_valid
    assert tender_vector_repo.deleted == [tender_id_orphan]
