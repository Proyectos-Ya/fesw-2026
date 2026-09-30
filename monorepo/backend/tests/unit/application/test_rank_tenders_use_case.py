from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.supplier_errors import (
    SupplierNotFoundForUser,
    SupplierVectorNotFound,
)
from app.infrastructure.repositories.tender_model import (
    TenderItemModel,
    TenderModel,
)
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    FORMULA_DE_PRUEBA,
    FakeEmbeddingPorTexto,
    FakeEmbeddingService,
    FakeRerankerService,
    FakeSupplierVectorRepository,
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    armar_scorer,
)


class InMemoryTenderRepository(ITenderRepository):
    """Fake repository en memoria para licitaciones."""

    def __init__(self) -> None:
        self.items_reemplazados: list = []
        self.actualizadas: list = []
        self.cerradas: list[UUID] = []
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

    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,
        limit: int,
        offset: int = 0,
        q: str | None = None,
    ) -> tuple[list[Tender], int]:  # noqa: ARG002
        return ([], 0)

    async def get_items_by_tender_id(self, tender_id: UUID) -> list:
        return []

    async def replace_tender_items(self, tender_id: UUID, items: list) -> None:
        self.items_reemplazados = list(items)

    async def update_tender(self, tender) -> None:
        self.actualizadas.append(tender)

    async def get_expired_published_ids(self) -> list[UUID]:
        return []

    async def mark_as_closed(self, tender_ids: list[UUID]) -> None:
        self.cerradas.extend(tender_ids)

    async def get_by_code(self, code: str) -> TenderModel | None:
        return None

    async def get_or_create_buyer(
        self,
        rut: str,
        name: str,
        region_id: int,
        comuna_id: int | None = None,
        comuna_resolution_source: str | None = None,
    ) -> str:
        return rut

    async def get_comuna_id_by_name(self, name: str) -> int | None:
        return None

    async def get_provincia_id_by_comuna_id(self, comuna_id: int) -> int | None:
        return None

    async def save_complex_tender(
        self, tender_model: TenderModel, items: list[TenderItemModel]
    ) -> None:
        pass

    async def get_or_create_status(self, status_id: int, code: str) -> int:
        return status_id

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(
        self, tender_id: UUID, supplier_id: UUID
    ) -> DeepAnalysis | None:
        return None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        return deep_analysis

    async def get_latest_tender_created_at(self) -> datetime | None:
        if not self.tenders:
            return None
        return max(
            (t.created_at for t in self.tenders.values() if t.created_at is not None),
            default=None,
        )


class FakeTenderVectorRepository(ITenderVectorRepository):
    """Fake repository vectorial para buscar licitaciones."""

    def __init__(self) -> None:
        self.payloads: dict[UUID, dict] = {}
        self.search_results: list[tuple[UUID, float]] = []
        self.searched_vectors: list[list[float]] = []
        self.search_criteria: list[TenderFilterCriteria | None] = []
        self.deleted: list[UUID] = []

    async def ensure_collection(self) -> None:
        pass

    async def upsert(
        self, tender_id: UUID, embedding: list[float], payload: dict
    ) -> None:
        pass

    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        self.payloads[tender_id] = {**self.payloads.get(tender_id, {}), **payload}

    async def delete(self, tender_id: UUID) -> None:
        self.deleted.append(tender_id)

    async def search_by_vector(
        self,
        vector: list[float],
        limit: int,
        offset: int = 0,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        self.searched_vectors.append(vector)
        self.search_criteria.append(criteria)
        return self.search_results

    async def count(self, criteria: TenderFilterCriteria | None = None) -> int:  # noqa: ARG002
        return len(self.search_results)


class FakeTenderItemVectorSearch(ITenderItemVectorRepository):
    """Repositorio de vectores de partidas para probar la búsqueda por keywords.

    Implementa la interfaz completa acá mismo, sin depender de `fakes.py`: lo que
    interesa es qué le pide el ranking (vectores, límite y criterio) y qué ids
    manda a borrar como huérfanos.
    """

    def __init__(self) -> None:
        self.search_results: list[tuple[UUID, float]] = []
        self.searches: list[dict] = []
        self.deleted: list[UUID] = []

    async def upsert(
        self,
        tender_id: UUID,
        item_vectors: list[list[float]],
        payload: dict | None = None,
    ) -> None:
        pass

    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        pass

    async def get_many(self, tender_ids: list[UUID]) -> dict[UUID, list[list[float]]]:
        return {}

    async def delete(self, tender_id: UUID) -> None:
        self.deleted.append(tender_id)

    async def search_by_keywords(
        self,
        keyword_vectors: list[list[float]],
        limit: int,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        self.searches.append(
            {"vectors": keyword_vectors, "limit": limit, "criteria": criteria}
        )
        return self.search_results


# ---------------------------------------------------------------------------
# Helpers para creación de entidades dummy
# ---------------------------------------------------------------------------


def crear_scorer(
    reranker: FakeRerankerService | None = None,
    matching_result_repo: InMemoryMatchingResultRepository | None = None,
) -> CompatibilityScorer:
    """Arma el servicio real de puntaje sobre los dobles de reranker y embeddings."""
    return armar_scorer(reranker=reranker, matching_result_repo=matching_result_repo)


def create_dummy_tender(
    tender_id: UUID,
    closing_in_hours: int = 24,
    status_code: str = TENDER_STATUSES["PUBLISHED"],
) -> Tender:
    """Helper para crear una licitación dummy con parámetros de prueba."""
    now = datetime.now(UTC).replace(tzinfo=None)
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
        scorer=crear_scorer(),
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
        scorer=crear_scorer(),
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
    await vector_repo.upsert(supplier.id, [0.1] * 1024)

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
        ),
    ]
    await matching_result_repo.save_bulk(cached)

    tender_vector_repo = FakeTenderVectorRepository()
    reranker = FakeRerankerService()

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=crear_scorer(reranker, matching_result_repo),
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
    await vector_repo.upsert(supplier.id, [0.5] * 1024)

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
        scorer=crear_scorer(reranker, matching_result_repo),
        matching_result_repo=matching_result_repo,
    )

    results = await use_case.execute(user_id=user_id)

    # Verificaciones
    assert len(results) == 2
    assert results[0].tender_id == tender_id_1
    # Con vectores idénticos B y C valen 1: el puntaje sale de la fórmula con
    # el R que dio el reranker (1,00 y 0,95 en el doble).
    assert results[0].reranker_score == pytest.approx(1.0)
    assert results[0].final_score == pytest.approx(FORMULA_DE_PRUEBA.score(1.0, 1.0, 1.0))
    assert results[1].final_score == pytest.approx(FORMULA_DE_PRUEBA.score(0.95, 1.0, 1.0))
    assert results[0].tender is not None
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
    await vector_repo.upsert(supplier.id, [0.1] * 1024)

    tender_id_active = uuid4()
    tender_id_expired = uuid4()
    tender_id_closed_status = uuid4()

    tender_repo = InMemoryTenderRepository()
    # Activa
    tender_repo.tenders[tender_id_active] = create_dummy_tender(
        tender_id_active, closing_in_hours=10
    )
    # Expirada por fecha
    tender_repo.tenders[tender_id_expired] = create_dummy_tender(
        tender_id_expired, closing_in_hours=-2
    )
    # Expirada por estado 'cerrada'
    tender_repo.tenders[tender_id_closed_status] = create_dummy_tender(
        tender_id_closed_status,
        closing_in_hours=10,
        status_code=TENDER_STATUSES["CLOSED"],
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
        scorer=crear_scorer(),
        matching_result_repo=matching_result_repo,
    )

    results = await use_case.execute(user_id=user_id)

    # Verificaciones: Solo la activa debe ser retornada
    assert len(results) == 1
    assert results[0].tender_id == tender_id_active
    assert results[0].tender is not None
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
    await vector_repo.upsert(supplier.id, [0.1] * 1024)

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
        scorer=crear_scorer(),
        matching_result_repo=InMemoryMatchingResultRepository(),
    )

    results = await use_case.execute(user_id=user_id)

    # La válida se retorna y el huérfano se limpia de Qdrant
    assert len(results) == 1
    assert results[0].tender_id == tender_id_valid
    assert tender_vector_repo.deleted == [tender_id_orphan]


@pytest.mark.asyncio
async def test_el_pipeline_sigue_filtrando_por_estado_publicada() -> None:
    """Fija el criterio con que el dashboard consulta Qdrant.

    Al unificar `search_by_supplier_vector` en `search_by_vector`, el filtro pasó
    de un dict suelto a un criterio tipado. Si esa traducción se perdiera, el
    motor recomendaría licitaciones ya cerradas y el síntoma aparecería recién en
    el dashboard del usuario.
    """
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    await vector_repo.upsert(supplier.id, [0.5] * 1024)

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = []

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=InMemoryTenderRepository(),
        scorer=crear_scorer(),
        matching_result_repo=InMemoryMatchingResultRepository(),
    )

    await use_case.execute(user_id=user_id)

    criterio = tender_vector_repo.search_criteria[0]
    assert criterio is not None
    assert criterio.status_codes == [TENDER_STATUSES["PUBLISHED"]]
    # Este proveedor no declaró regiones, así que no se acota por región; y el
    # dashboard nunca acota por fecha: eso es del buscador manual.
    assert criterio.region_ids is None
    assert criterio.closing_from is None


@pytest.mark.asyncio
async def test_el_pipeline_busca_con_el_vector_del_proveedor() -> None:
    """El vector que se manda es el del perfil, no uno cualquiera.

    Es lo que distingue este uso de `search_by_vector` del que hará el buscador
    con el vector de la consulta del usuario.
    """
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_del_proveedor = [0.42] * 1024
    vector_repo = FakeSupplierVectorRepository()
    await vector_repo.upsert(supplier.id, vector_del_proveedor)

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = []

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=InMemoryTenderRepository(),
        scorer=crear_scorer(),
        matching_result_repo=InMemoryMatchingResultRepository(),
    )

    await use_case.execute(user_id=user_id)

    assert tender_vector_repo.searched_vectors == [vector_del_proveedor]


@pytest.mark.asyncio
async def test_los_calculos_a_pedido_no_son_recomendaciones() -> None:
    """Una licitación que el usuario se calculó a mano no entra al dashboard.

    El sistema nunca la propuso: la encontró el usuario buscando. Tratarla como
    recomendación además dispararía alertas de la HdU 08 por algo que nadie
    recomendó.
    """
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    await vector_repo.upsert(supplier.id, [0.5] * 1024)

    recomendada = uuid4()
    a_pedido = uuid4()
    tender_repo = InMemoryTenderRepository()
    tender_repo.tenders[recomendada] = create_dummy_tender(recomendada)
    tender_repo.tenders[a_pedido] = create_dummy_tender(a_pedido)

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = [(recomendada, 0.85)]

    matching_result_repo = InMemoryMatchingResultRepository()
    await matching_result_repo.save_on_demand(
        MatchingResult(
            supplier_id=supplier.id,
            tender_id=a_pedido,
            similarity_score=None,
            final_score=0.42,
            model_version="bge-m3-v1",
            source="on_demand",
        )
    )

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=crear_scorer(matching_result_repo=matching_result_repo),
        matching_result_repo=matching_result_repo,
    )

    results = await use_case.execute(user_id=user_id)

    assert [r.tender_id for r in results] == [recomendada]
    # Y el recálculo no se llevó por delante lo que el usuario había pedido.
    guardado = await matching_result_repo.get_by_proveedor_and_licitacion(
        supplier.id, a_pedido
    )
    assert guardado is not None
    assert guardado.final_score == pytest.approx(0.42)


@pytest.mark.asyncio
async def test_si_la_licitacion_a_pedido_entra_al_top_reemplaza_su_fila() -> None:
    """Hay una restricción única por par: la fila vieja tiene que salir primero."""
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    await vector_repo.upsert(supplier.id, [0.5] * 1024)

    tender_id = uuid4()
    tender_repo = InMemoryTenderRepository()
    tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = [(tender_id, 0.85)]

    matching_result_repo = InMemoryMatchingResultRepository()
    await matching_result_repo.save_on_demand(
        MatchingResult(
            supplier_id=supplier.id,
            tender_id=tender_id,
            similarity_score=None,
            final_score=0.42,
            model_version="bge-m3-v1",
            source="on_demand",
        )
    )

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=crear_scorer(matching_result_repo=matching_result_repo),
        matching_result_repo=matching_result_repo,
    )

    await use_case.execute(user_id=user_id)

    filas = await matching_result_repo.get_by_supplier_id(supplier.id)
    assert len(filas) == 1
    assert filas[0].source == "ranking"


# ---------------------------------------------------------------------------
# Versión del modelo y de la fórmula: invalida la caché de recomendaciones
# ---------------------------------------------------------------------------

VERSION_ANTERIOR = "BAAI/bge-m3"
VERSION_ACTUAL = "BAAI/bge-m3+compat-calib-v1"


async def _armar_caso_con_cache(
    versiones_cacheadas: list[str], version_actual: str = VERSION_ACTUAL
) -> tuple[
    RankTendersUseCase,
    UUID,
    list[UUID],
    FakeRerankerService,
    InMemoryMatchingResultRepository,
]:
    """Un proveedor con una fila cacheada por cada versión indicada.

    La caché es válida en todo lo demás (recién calculada, sin licitaciones ni
    cambios de perfil posteriores): lo único que puede vencerla es la versión.
    """
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    await vector_repo.upsert(supplier.id, [0.5] * 1024)

    tender_ids = [uuid4() for _ in versiones_cacheadas]
    tender_repo = InMemoryTenderRepository()
    for tender_id in tender_ids:
        tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)

    matching_result_repo = InMemoryMatchingResultRepository()
    await matching_result_repo.save_bulk(
        [
            MatchingResult(
                supplier_id=supplier.id,
                tender_id=tender_id,
                similarity_score=0.85,
                reranker_score=0.90,
                final_score=0.42,
                model_version=version,
            )
            for tender_id, version in zip(tender_ids, versiones_cacheadas, strict=True)
        ]
    )

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = [(tid, 0.8) for tid in tender_ids]
    reranker = FakeRerankerService()

    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=armar_scorer(
            reranker=reranker,
            matching_result_repo=matching_result_repo,
            model_version=version_actual,
        ),
        matching_result_repo=matching_result_repo,
        model_version=version_actual,
    )
    return use_case, user_id, tender_ids, reranker, matching_result_repo


@pytest.mark.asyncio
async def test_cache_de_otra_version_del_modelo_se_recalcula() -> None:
    """Tras desplegar una fórmula nueva, la caché vigente todavía trae los
    porcentajes de la anterior. Sin esto el usuario los seguiría viendo hasta que
    llegara una licitación nueva o cambiara su perfil."""
    use_case, user_id, tender_ids, reranker, repo = await _armar_caso_con_cache(
        [VERSION_ANTERIOR, VERSION_ANTERIOR]
    )

    results = await use_case.execute(user_id=user_id)

    assert len(reranker.calls) == 1
    assert {r.tender_id for r in results} == set(tender_ids)
    assert all(r.model_version == VERSION_ACTUAL for r in results)
    assert all(r.final_score != pytest.approx(0.42) for r in results)
    # Y lo persistido es lo recalculado, no lo viejo.
    guardadas = await repo.get_ranking_by_supplier_id(results[0].supplier_id)
    assert {m.model_version for m in guardadas} == {VERSION_ACTUAL}


@pytest.mark.asyncio
async def test_basta_una_fila_de_otra_version_para_recalcular() -> None:
    use_case, user_id, _, reranker, _ = await _armar_caso_con_cache(
        [VERSION_ACTUAL, VERSION_ANTERIOR, VERSION_ACTUAL]
    )

    await use_case.execute(user_id=user_id)

    assert len(reranker.calls) == 1


@pytest.mark.asyncio
async def test_cache_de_la_version_actual_no_se_recalcula() -> None:
    use_case, user_id, tender_ids, reranker, _ = await _armar_caso_con_cache(
        [VERSION_ACTUAL, VERSION_ACTUAL]
    )

    results = await use_case.execute(user_id=user_id)

    assert reranker.calls == []
    assert {r.tender_id for r in results} == set(tender_ids)
    assert all(r.final_score == pytest.approx(0.42) for r in results)


@pytest.mark.asyncio
async def test_force_refresh_recalcula_aunque_la_version_coincida() -> None:
    use_case, user_id, _, reranker, _ = await _armar_caso_con_cache([VERSION_ACTUAL])

    await use_case.execute(user_id=user_id, force_refresh=True)

    assert len(reranker.calls) == 1


# ---------------------------------------------------------------------------
# Región dentro de la búsqueda vectorial
# ---------------------------------------------------------------------------
#
# Antes la búsqueda traía el top-50 de todo el país y la región se descartaba
# después, en Python: un proveedor del Biobío recibía 6 candidatas de 50 habiendo
# 134 en su región. Ahora la región viaja en el criterio y filtra Qdrant.


@dataclass
class CasoRanking:
    """Un `RankTendersUseCase` armado sobre dobles, con lo que hay que inspeccionar."""

    use_case: RankTendersUseCase
    user_id: UUID
    supplier: Supplier
    tender_vector_repo: FakeTenderVectorRepository
    item_repo: FakeTenderItemVectorSearch | None
    reranker: FakeRerankerService
    matching_result_repo: InMemoryMatchingResultRepository
    embedding: FakeEmbeddingService | FakeEmbeddingPorTexto


async def _armar_caso(
    *,
    regions: list[str] | None = None,
    keywords: list[str] | None = None,
    por_perfil: list[tuple[UUID, float]] | None = None,
    por_keywords: list[tuple[UUID, float]] | None = None,
    tenders: list[Tender] | None = None,
    con_item_repo: bool = True,
    con_embedding: bool = True,
    item_search_limit: int | None = None,
    embedding: FakeEmbeddingService | FakeEmbeddingPorTexto | None = None,
) -> CasoRanking:
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier = Supplier(
        rut="76086428-5",
        legal_name="Empresa SpA",
        user_id=user_id,
        regions=regions,
        keywords=["cemento", "fierro"] if keywords is None else keywords,
    )
    await supplier_repo.save(supplier)

    vector_repo = FakeSupplierVectorRepository()
    await vector_repo.upsert(supplier.id, [0.5] * 1024)

    tender_repo = InMemoryTenderRepository()
    for tender in tenders or []:
        tender_repo.tenders[tender.id] = tender

    tender_vector_repo = FakeTenderVectorRepository()
    tender_vector_repo.search_results = por_perfil or []
    item_repo = FakeTenderItemVectorSearch() if con_item_repo else None
    if item_repo is not None:
        item_repo.search_results = por_keywords or []

    embedding = embedding or FakeEmbeddingService()
    matching_result_repo = InMemoryMatchingResultRepository()
    reranker = FakeRerankerService()

    opciones: dict = {}
    if item_search_limit is not None:
        opciones["item_search_limit"] = item_search_limit
    use_case = RankTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=tender_repo,
        scorer=armar_scorer(
            reranker=reranker,
            matching_result_repo=matching_result_repo,
            embedding=embedding,
        ),
        matching_result_repo=matching_result_repo,
        embedding_service=embedding if con_embedding else None,
        item_vector_repo=item_repo,
        **opciones,
    )
    return CasoRanking(
        use_case=use_case,
        user_id=user_id,
        supplier=supplier,
        tender_vector_repo=tender_vector_repo,
        item_repo=item_repo,
        reranker=reranker,
        matching_result_repo=matching_result_repo,
        embedding=embedding,
    )


def _ids_puntuados(reranker: FakeRerankerService) -> list[UUID]:
    """Ids de las candidatas que llegaron al scorer (al reranker), en orden."""
    return [uid for uid, _ in reranker.calls[0][1]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("regiones", "esperado"),
    [
        (["Biobío"], [8]),
        (["Región del Biobío", "Región de Ñuble"], [8, 16]),
        (["Metropolitana"], [13]),
        (["Región Metropolitana de Santiago"], [13]),
        (["Metropolitana de Santiago", "Región Metropolitana"], [13]),
        (["Valparaíso", "Narnia"], [5]),
    ],
)
async def test_el_criterio_de_la_busqueda_lleva_los_ids_de_las_regiones_del_proveedor(
    regiones: list[str], esperado: list[int]
) -> None:
    """Los nombres (con o sin "Región de", canónicos o del wizard) se resuelven a
    ids con `normalize_region_name`, sin repetir y sin los que no se reconocen."""
    caso = await _armar_caso(regions=regiones)

    await caso.use_case.execute(user_id=caso.user_id)

    criterio = caso.tender_vector_repo.search_criteria[0]
    assert criterio is not None
    assert criterio.region_ids == esperado
    assert criterio.status_codes == [TENDER_STATUSES["PUBLISHED"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("regiones", [None, [], ["Narnia", "Atlántida"]])
async def test_sin_regiones_reconocibles_la_busqueda_no_filtra_por_region(
    regiones: list[str] | None,
) -> None:
    """Sin regiones —o ninguna reconocible— no hay a qué acotar: igual que antes."""
    caso = await _armar_caso(regions=regiones)

    await caso.use_case.execute(user_id=caso.user_id)

    criterio = caso.tender_vector_repo.search_criteria[0]
    assert criterio is not None
    assert criterio.region_ids is None
    assert criterio.status_codes == [TENDER_STATUSES["PUBLISHED"]]


@pytest.mark.asyncio
async def test_la_region_en_sql_sigue_descartando_lo_que_el_payload_dejo_pasar() -> None:
    """Red de seguridad: el payload `region_id` de Qdrant puede estar desactualizado
    (p. ej. se corrigió la región en SQL y no se re-sincronizó), así que el filtro
    estricto posterior sigue rigiendo, venga la candidata del canal que venga."""
    en_su_region = uuid4()
    por_perfil_fuera = uuid4()
    por_keywords_fuera = uuid4()
    tenders = [
        create_dummy_tender(en_su_region),
        create_dummy_tender(por_perfil_fuera),
        create_dummy_tender(por_keywords_fuera),
    ]
    tenders[0].region = "Región del Biobío"
    tenders[1].region = "Región Metropolitana de Santiago"
    tenders[2].region = "Región Metropolitana de Santiago"
    caso = await _armar_caso(
        regions=["Biobío"],
        tenders=tenders,
        por_perfil=[(en_su_region, 0.9), (por_perfil_fuera, 0.8)],
        por_keywords=[(por_keywords_fuera, 0.7)],
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    assert [r.tender_id for r in results] == [en_su_region]
    assert _ids_puntuados(caso.reranker) == [en_su_region]


# ---------------------------------------------------------------------------
# Segundo canal: keywords del proveedor contra los vectores de partidas
# ---------------------------------------------------------------------------
#
# La búsqueda por el vector del perfil completo pierde licitaciones cuyas partidas
# calzan con una keyword puntual. Buscar cada keyword contra las partidas (MaxSim)
# las recupera, y las candidatas de ambos canales se unen antes de puntuar.


@pytest.mark.asyncio
async def test_una_licitacion_que_solo_aparece_por_keywords_llega_al_scorer() -> None:
    por_perfil, solo_keywords = uuid4(), uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(por_perfil), create_dummy_tender(solo_keywords)],
        por_perfil=[(por_perfil, 0.85)],
        por_keywords=[(solo_keywords, 0.91)],
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    assert set(_ids_puntuados(caso.reranker)) == {por_perfil, solo_keywords}
    assert {r.tender_id for r in results} == {por_perfil, solo_keywords}
    persistidas = await caso.matching_result_repo.get_ranking_by_supplier_id(
        caso.supplier.id
    )
    assert {m.tender_id for m in persistidas} == {por_perfil, solo_keywords}


@pytest.mark.asyncio
async def test_lo_que_solo_vino_por_keywords_no_tiene_similitud_de_perfil() -> None:
    """El puntaje MaxSim no está en la escala de la similitud del perfil, y un 0.0
    afirmaría "sin parecido alguno" de algo que calzó: queda nulo, "no se midió"."""
    por_perfil, solo_keywords = uuid4(), uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(por_perfil), create_dummy_tender(solo_keywords)],
        por_perfil=[(por_perfil, 0.85)],
        por_keywords=[(solo_keywords, 0.91)],
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    similitud = {r.tender_id: r.similarity_score for r in results}
    assert similitud[por_perfil] == pytest.approx(0.85)
    assert similitud[solo_keywords] is None


@pytest.mark.asyncio
async def test_la_union_de_los_canales_no_repite_candidatas() -> None:
    """Una licitación que trajeron los dos canales se puntúa una sola vez y
    conserva la similitud de perfil."""
    a, b, c = uuid4(), uuid4(), uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(t) for t in (a, b, c)],
        por_perfil=[(a, 0.9), (b, 0.8)],
        por_keywords=[(b, 0.95), (c, 0.7)],
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    assert _ids_puntuados(caso.reranker) == [a, b, c]
    assert sorted(r.tender_id for r in results) == sorted([a, b, c])
    similitud = {r.tender_id: r.similarity_score for r in results}
    assert similitud[b] == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_la_busqueda_por_keywords_recibe_los_vectores_el_limite_y_el_criterio() -> None:
    """Va con un vector por keyword, con `item_search_limit` y con el mismo criterio
    que la búsqueda por perfil (estado publicada y las regiones del proveedor)."""
    embedding = FakeEmbeddingPorTexto(
        {"cemento": [1.0, 0.0, 0.0], "fierro": [0.0, 1.0, 0.0]}
    )
    caso = await _armar_caso(
        regions=["Región del Biobío"],
        keywords=["cemento", "  ", "fierro"],
        embedding=embedding,
        item_search_limit=7,
    )

    await caso.use_case.execute(user_id=caso.user_id)

    assert caso.item_repo is not None
    [busqueda] = caso.item_repo.searches
    assert busqueda["vectors"] == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert busqueda["limit"] == 7
    assert busqueda["criteria"] == caso.tender_vector_repo.search_criteria[0]
    assert busqueda["criteria"].region_ids == [8]
    assert busqueda["criteria"].status_codes == [TENDER_STATUSES["PUBLISHED"]]


@pytest.mark.asyncio
async def test_el_limite_por_defecto_de_la_busqueda_por_keywords_es_30() -> None:
    caso = await _armar_caso()

    await caso.use_case.execute(user_id=caso.user_id)

    assert caso.item_repo is not None
    assert caso.item_repo.searches[0]["limit"] == 30


@pytest.mark.asyncio
async def test_sin_keywords_la_busqueda_usa_la_descripcion_como_el_scorer() -> None:
    """Los textos salen de `TextBuilder.build_keyword_texts`, los mismos con que el
    scorer puntúa: sin keywords, la descripción del proveedor."""
    embedding = FakeEmbeddingPorTexto({"Venta de materiales": [1.0, 0.0, 0.0]})
    caso = await _armar_caso(keywords=[], embedding=embedding)
    caso.supplier.description = "Venta de materiales"

    await caso.use_case.execute(user_id=caso.user_id)

    assert caso.item_repo is not None
    assert caso.item_repo.searches[0]["vectors"] == [[1.0, 0.0, 0.0]]


@pytest.mark.asyncio
async def test_si_el_perfil_no_trae_nada_las_keywords_pueden_sostener_el_ranking() -> None:
    solo_keywords = uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(solo_keywords)],
        por_perfil=[],
        por_keywords=[(solo_keywords, 0.9)],
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    assert [r.tender_id for r in results] == [solo_keywords]


@pytest.mark.asyncio
async def test_si_ningun_canal_trae_nada_se_limpia_el_ranking_anterior() -> None:
    caso = await _armar_caso()
    await caso.matching_result_repo.save_bulk(
        [
            MatchingResult(
                supplier_id=caso.supplier.id,
                tender_id=uuid4(),
                similarity_score=0.8,
                final_score=0.5,
                model_version="bge-m3-v1",
            )
        ]
    )

    results = await caso.use_case.execute(user_id=caso.user_id, force_refresh=True)

    assert results == []
    assert (
        await caso.matching_result_repo.get_ranking_by_supplier_id(caso.supplier.id)
        == []
    )


@pytest.mark.asyncio
async def test_un_huerfano_del_canal_de_keywords_se_borra_del_repo_de_partidas() -> None:
    """Un id que Qdrant devuelve por sus partidas pero que ya no existe en SQL
    ocuparía un cupo de cada búsqueda: se borra del almacén de donde vino."""
    valida, huerfano = uuid4(), uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(valida)],
        por_perfil=[(valida, 0.9)],
        por_keywords=[(huerfano, 0.9)],
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    assert [r.tender_id for r in results] == [valida]
    assert caso.item_repo is not None
    assert caso.item_repo.deleted == [huerfano]
    assert caso.tender_vector_repo.deleted == []


@pytest.mark.asyncio
async def test_un_huerfano_del_canal_de_perfil_no_toca_el_repo_de_partidas() -> None:
    valida, huerfano = uuid4(), uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(valida)],
        por_perfil=[(valida, 0.9), (huerfano, 0.8)],
    )

    await caso.use_case.execute(user_id=caso.user_id)

    assert caso.item_repo is not None
    assert caso.item_repo.deleted == []
    assert caso.tender_vector_repo.deleted == [huerfano]


@pytest.mark.asyncio
async def test_un_huerfano_que_trajeron_los_dos_canales_se_borra_de_ambos_almacenes() -> None:
    valida, huerfano = uuid4(), uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(valida)],
        por_perfil=[(valida, 0.9), (huerfano, 0.8)],
        por_keywords=[(huerfano, 0.9)],
    )

    await caso.use_case.execute(user_id=caso.user_id)

    assert caso.item_repo is not None
    assert caso.item_repo.deleted == [huerfano]
    assert caso.tender_vector_repo.deleted == [huerfano]


@pytest.mark.asyncio
async def test_sin_repo_de_partidas_el_ranking_es_el_de_antes() -> None:
    """Sin `item_vector_repo` no hay segundo canal: mismas candidatas y mismas
    similitudes, y el caso de uso no embebe nada (el vector del perfil ya estaba)."""
    a, b = uuid4(), uuid4()
    embedding_del_caso_de_uso = FakeEmbeddingService()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(a), create_dummy_tender(b)],
        por_perfil=[(a, 0.85), (b, 0.78)],
        con_item_repo=False,
        embedding=embedding_del_caso_de_uso,
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    assert [r.tender_id for r in results] == [a, b]
    assert [r.similarity_score for r in results] == [
        pytest.approx(0.85),
        pytest.approx(0.78),
    ]
    # El doble de embeddings es el mismo que usa el scorer, así que aparecen sus
    # llamadas (keywords y partidas), pero la búsqueda por keywords no hizo la
    # suya: las keywords se embebieron una sola vez, en el scorer.
    assert embedding_del_caso_de_uso.calls.count(["cemento", "fierro"]) == 1


@pytest.mark.asyncio
async def test_sin_servicio_de_embeddings_no_se_busca_por_keywords() -> None:
    """Sin cómo convertir las keywords en vectores no hay segundo canal, aunque
    exista el repo de partidas: el ranking sigue con lo que trae el perfil."""
    a = uuid4()
    caso = await _armar_caso(
        tenders=[create_dummy_tender(a)],
        por_perfil=[(a, 0.85)],
        con_embedding=False,
    )

    results = await caso.use_case.execute(user_id=caso.user_id)

    assert [r.tender_id for r in results] == [a]
    assert caso.item_repo is not None
    assert caso.item_repo.searches == []
