"""Tests del caso de uso de búsqueda manual de licitaciones (HdU 07).

El caso de uso elige de dónde sale el vector que ordena los resultados y arma la
respuesta; los filtros ya los traduce el adaptador (ver
test_qdrant_tender_repository).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.use_cases.tender.search_tenders import SearchTendersUseCase
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemorySupplierRepository,
)

# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


def _make_tender(tender_id: UUID, name: str = "Licitación") -> Tender:
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"COT-{tender_id}",
        name=name,
        description="Descripción",
        status_id=1,
        status_code="publicada",
        published_at=now - timedelta(days=1),
        closing_at=now + timedelta(days=5),
        last_change_at=now,
        buyer_rut="12.345.678-9",
        buyer_unit="Obras",
        items=[],
    )


class FakeTenderVectorRepo(ITenderVectorRepository):
    def __init__(self) -> None:
        self.search_results: list[tuple[UUID, float]] = []
        self.total = 0
        self.searched_vectors: list[list[float]] = []
        self.search_criteria: list[TenderFilterCriteria | None] = []
        self.search_limits: list[int] = []
        self.search_offsets: list[int] = []

    async def ensure_collection(self) -> None:
        pass

    async def upsert(self, tender_id: UUID, embedding: list[float], p: dict) -> None:
        pass

    async def delete(self, tender_id: UUID) -> None:
        pass

    async def search_by_vector(
        self,
        vector: list[float],
        limit: int,
        offset: int = 0,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        self.searched_vectors.append(vector)
        self.search_criteria.append(criteria)
        self.search_limits.append(limit)
        self.search_offsets.append(offset)
        return self.search_results

    async def count(self, criteria: TenderFilterCriteria | None = None) -> int:  # noqa: ARG002
        return self.total


class FakeTenderRepo(ITenderRepository):
    def __init__(self) -> None:
        self.tenders: dict[UUID, Tender] = {}
        self.sql_search_calls: list[tuple[TenderFilterCriteria, int, int]] = []
        self.sql_results: tuple[list[Tender], int] = ([], 0)

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:
        # Devuelve en orden arbitrario a propósito: el caso de uso es responsable
        # de restaurar el orden del ranking.
        encontrados = [
            self.tenders[i] for i in (filters.ids or []) if i in self.tenders
        ]
        return list(reversed(encontrados))

    async def search_tenders(
        self, criteria: TenderFilterCriteria, limit: int, offset: int = 0
    ) -> tuple[list[Tender], int]:
        self.sql_search_calls.append((criteria, limit, offset))
        return self.sql_results

    async def get_by_code(self, code: str) -> TenderModel | None:
        return None

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:
        return rut

    async def get_or_create_status(self, status_id: int) -> int:
        return status_id

    async def save_complex_tender(
        self, tender_model: TenderModel, items: list[TenderItemModel]
    ) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(
        self, tender_id: UUID, supplier_id: UUID
    ) -> DeepAnalysis | None:
        return None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        return deep_analysis


async def _build(
    *,
    con_perfil: bool = True,
    con_vector: bool = True,
    vector_proveedor: list[float] | None = None,
    result_limit: int = 500,
):
    user_id = uuid4()
    supplier_repo = InMemorySupplierRepository()
    supplier_vector_repo = FakeSupplierVectorRepository()

    if con_perfil:
        supplier = Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
        await supplier_repo.save(supplier)
        if con_vector:
            supplier_vector_repo.upsert(supplier.id, vector_proveedor or [0.7] * 1024)

    vector_repo = FakeTenderVectorRepo()
    tender_repo = FakeTenderRepo()
    embedding = FakeEmbeddingService([0.3] * 1024)

    use_case = SearchTendersUseCase(
        supplier_repo=supplier_repo,
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=vector_repo,
        tender_repo=tender_repo,
        embedding_service=embedding,
        result_limit=result_limit,
    )
    return use_case, user_id, vector_repo, tender_repo, embedding


# ---------------------------------------------------------------------------
# De dónde sale el vector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_con_texto_busca_con_el_vector_de_la_consulta() -> None:
    use_case, user_id, vector_repo, _, embedding = await _build()

    await use_case.execute(user_id=user_id, q="construcción de techumbre")

    assert embedding.calls == [["construcción de techumbre"]]
    assert vector_repo.searched_vectors == [[0.3] * 1024]


@pytest.mark.asyncio
async def test_sin_texto_busca_con_el_vector_del_proveedor() -> None:
    """Con filtros pero sin texto, el orden lo da la afinidad con la empresa."""
    vector_proveedor = [0.9] * 1024
    use_case, user_id, vector_repo, _, embedding = await _build(
        vector_proveedor=vector_proveedor
    )

    await use_case.execute(user_id=user_id, q=None)

    assert embedding.calls == [], "no hay texto que embeber"
    assert vector_repo.searched_vectors == [vector_proveedor]


@pytest.mark.asyncio
async def test_el_texto_en_blanco_equivale_a_no_haber_texto() -> None:
    vector_proveedor = [0.9] * 1024
    use_case, user_id, vector_repo, _, embedding = await _build(
        vector_proveedor=vector_proveedor
    )

    await use_case.execute(user_id=user_id, q="   ")

    assert embedding.calls == []
    assert vector_repo.searched_vectors == [vector_proveedor]


@pytest.mark.asyncio
async def test_el_texto_se_recorta_antes_de_embeber() -> None:
    use_case, user_id, _, _, embedding = await _build()

    await use_case.execute(user_id=user_id, q="  cables  ")

    assert embedding.calls == [["cables"]]


# ---------------------------------------------------------------------------
# Respaldo SQL: proveedor sin perfil vectorizado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sin_texto_y_sin_vector_cae_al_camino_sql() -> None:
    """Un proveedor recién registrado no tiene vector todavía.

    Sin este respaldo, el buscador fallaría justo a quien acaba de llegar.
    """
    use_case, user_id, vector_repo, tender_repo, _ = await _build(con_vector=False)
    t1 = uuid4()
    tender_repo.sql_results = ([_make_tender(t1)], 1)

    resultado = await use_case.execute(user_id=user_id, q=None)

    assert vector_repo.searched_vectors == [], "no debe consultar Qdrant sin vector"
    assert len(tender_repo.sql_search_calls) == 1
    assert [t.id for t in resultado.items] == [t1]
    assert resultado.total == 1


@pytest.mark.asyncio
async def test_sin_perfil_de_proveedor_tambien_cae_al_camino_sql() -> None:
    use_case, user_id, vector_repo, tender_repo, _ = await _build(con_perfil=False)
    tender_repo.sql_results = ([], 0)

    resultado = await use_case.execute(user_id=user_id, q=None)

    assert vector_repo.searched_vectors == []
    assert len(tender_repo.sql_search_calls) == 1
    assert resultado.items == []


@pytest.mark.asyncio
async def test_con_texto_no_necesita_vector_del_proveedor() -> None:
    """El texto se embebe solo; no hace falta perfil para buscar."""
    use_case, user_id, vector_repo, tender_repo, embedding = await _build(
        con_vector=False
    )

    await use_case.execute(user_id=user_id, q="cables")

    assert embedding.calls == [["cables"]]
    assert vector_repo.searched_vectors == [[0.3] * 1024]
    assert tender_repo.sql_search_calls == []


# ---------------------------------------------------------------------------
# Filtros, total y truncado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_los_filtros_llegan_intactos_al_repositorio_vectorial() -> None:
    use_case, user_id, vector_repo, _, _ = await _build()
    criterio = TenderFilterCriteria(region_ids=[13], min_amount=100_000)

    await use_case.execute(user_id=user_id, q="cables", criteria=criterio)

    assert vector_repo.search_criteria == [criterio]


@pytest.mark.asyncio
async def test_el_total_sale_de_count_y_no_del_largo_de_la_pagina() -> None:
    """El total son las coincidencias del filtro, no lo que cupo en la respuesta."""
    use_case, user_id, vector_repo, tender_repo, _ = await _build(result_limit=2)
    ids = [uuid4(), uuid4()]
    for i in ids:
        tender_repo.tenders[i] = _make_tender(i)
    vector_repo.search_results = [(ids[0], 0.9), (ids[1], 0.8)]
    vector_repo.total = 137

    resultado = await use_case.execute(user_id=user_id, q="cables")

    assert len(resultado.items) == 2
    assert resultado.total == 137


@pytest.mark.asyncio
async def test_marca_truncado_cuando_quedan_resultados_fuera() -> None:
    use_case, user_id, vector_repo, tender_repo, _ = await _build(result_limit=2)
    ids = [uuid4(), uuid4()]
    for i in ids:
        tender_repo.tenders[i] = _make_tender(i)
    vector_repo.search_results = [(ids[0], 0.9), (ids[1], 0.8)]
    vector_repo.total = 137

    resultado = await use_case.execute(user_id=user_id, q="cables")

    assert resultado.is_truncated is True


@pytest.mark.asyncio
async def test_no_marca_truncado_cuando_llego_todo() -> None:
    use_case, user_id, vector_repo, tender_repo, _ = await _build(result_limit=500)
    t1 = uuid4()
    tender_repo.tenders[t1] = _make_tender(t1)
    vector_repo.search_results = [(t1, 0.9)]
    vector_repo.total = 1

    resultado = await use_case.execute(user_id=user_id, q="cables")

    assert resultado.is_truncated is False


@pytest.mark.asyncio
async def test_el_tope_se_pasa_como_limite_a_qdrant() -> None:
    use_case, user_id, vector_repo, _, _ = await _build(result_limit=500)

    await use_case.execute(user_id=user_id, q="cables")

    assert vector_repo.search_limits == [500]


@pytest.mark.asyncio
async def test_el_offset_se_propaga_para_pedir_el_bloque_siguiente() -> None:
    use_case, user_id, vector_repo, _, _ = await _build(result_limit=500)

    await use_case.execute(user_id=user_id, q="cables", offset=500)

    assert vector_repo.search_offsets == [500]


@pytest.mark.asyncio
async def test_el_truncado_considera_el_offset() -> None:
    """En el segundo bloque, truncado significa que aún queda un tercero."""
    use_case, user_id, vector_repo, tender_repo, _ = await _build(result_limit=2)
    ids = [uuid4(), uuid4()]
    for i in ids:
        tender_repo.tenders[i] = _make_tender(i)
    vector_repo.search_results = [(ids[0], 0.9), (ids[1], 0.8)]
    vector_repo.total = 4

    resultado = await use_case.execute(user_id=user_id, q="cables", offset=2)

    # offset 2 + 2 entregadas = 4, que es el total: no queda nada más.
    assert resultado.is_truncated is False


# ---------------------------------------------------------------------------
# Hidratación
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conserva_el_orden_del_ranking_tras_hidratar() -> None:
    """SQL devuelve en orden arbitrario; el orden de relevancia lo da Qdrant.

    Si se perdiera, la lista dejaría de estar ordenada por relevancia sin que
    nada fallara — el peor tipo de error, porque es invisible.
    """
    use_case, user_id, vector_repo, tender_repo, _ = await _build()
    ids = [uuid4(), uuid4(), uuid4()]
    for i in ids:
        tender_repo.tenders[i] = _make_tender(i)
    vector_repo.search_results = [(ids[0], 0.95), (ids[1], 0.80), (ids[2], 0.60)]
    vector_repo.total = 3

    resultado = await use_case.execute(user_id=user_id, q="cables")

    assert [t.id for t in resultado.items] == ids


@pytest.mark.asyncio
async def test_descarta_los_ids_sin_fila_en_sql() -> None:
    """Qdrant puede tener puntos sin su fila en Postgres (ver rank_tenders 3.3.1).

    En una búsqueda se omiten en vez de devolver huecos.
    """
    use_case, user_id, vector_repo, tender_repo, _ = await _build()
    presente, huerfano = uuid4(), uuid4()
    tender_repo.tenders[presente] = _make_tender(presente)
    vector_repo.search_results = [(huerfano, 0.99), (presente, 0.80)]
    vector_repo.total = 2

    resultado = await use_case.execute(user_id=user_id, q="cables")

    assert [t.id for t in resultado.items] == [presente]


@pytest.mark.asyncio
async def test_sin_resultados_devuelve_lista_vacia_y_no_hidrata() -> None:
    """Cero resultados es una respuesta válida, no un error."""
    use_case, user_id, vector_repo, _, _ = await _build()
    vector_repo.search_results = []
    vector_repo.total = 0

    resultado = await use_case.execute(user_id=user_id, q="algo que no existe")

    assert resultado.items == []
    assert resultado.total == 0
    assert resultado.is_truncated is False
