"""Pruebas del servicio que calcula la compatibilidad proveedor/licitación.

Es la fórmula que antes vivía dentro de `RankTendersUseCase`: la comparten el
ranking (muchas candidatas) y el cálculo a pedido (una sola).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.compatibility_scorer import CompatibilityScorer
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.matching_errors import ScoreCalculationError
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    FakeRerankerService,
    FakeWeightingService,
    InMemoryMatchingResultRepository,
)


def crear_licitacion(tender_id: UUID) -> Tender:
    ahora = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"COT-{tender_id}",
        name="Servicio de aseo",
        description="Aseo de oficinas",
        status_id=1,
        status_code=TENDER_STATUSES["PUBLISHED"],
        published_at=ahora - timedelta(days=1),
        closing_at=ahora + timedelta(days=2),
        last_change_at=ahora,
        buyer_rut="12.345.678-9",
        buyer_name="Municipalidad de Santiago",
        buyer_unit="TI",
        items=[],
    )


def crear_proveedor() -> Supplier:
    return Supplier(rut="76086428-5", legal_name="Empresa SpA", user_id=uuid4())


def crear_scorer(
    reranker: FakeRerankerService | None = None,
    repo: InMemoryMatchingResultRepository | None = None,
) -> tuple[CompatibilityScorer, InMemoryMatchingResultRepository]:
    repo = repo or InMemoryMatchingResultRepository()
    scorer = CompatibilityScorer(
        reranker_service=reranker or FakeRerankerService(),
        weighting_service=FakeWeightingService(),
        matching_result_repo=repo,
        model_version="bge-m3-v1",
    )
    return scorer, repo


class RerankerVacio(FakeRerankerService):
    """Simula un reranker que no devuelve la candidata que se le mandó."""

    async def rerank(self, query_text, candidates, limit):  # noqa: ANN001, ARG002
        return []


@pytest.mark.asyncio
async def test_score_many_puntua_todas_las_candidatas() -> None:
    scorer, _ = crear_scorer()
    licitaciones = [crear_licitacion(uuid4()) for _ in range(3)]

    resultados = await scorer.score_many(crear_proveedor(), licitaciones, limit=3)

    assert [r.tender_id for r in resultados] == [t.id for t in licitaciones]
    assert all(r.reranker_score is not None for r in resultados)
    assert resultados[0].final_score > resultados[1].final_score


@pytest.mark.asyncio
async def test_score_many_respeta_el_limite_del_reranker() -> None:
    scorer, _ = crear_scorer()
    licitaciones = [crear_licitacion(uuid4()) for _ in range(5)]

    resultados = await scorer.score_many(crear_proveedor(), licitaciones, limit=2)

    assert len(resultados) == 2


@pytest.mark.asyncio
async def test_score_many_sin_candidatas_no_llama_al_reranker() -> None:
    reranker = FakeRerankerService()
    scorer, _ = crear_scorer(reranker=reranker)

    assert await scorer.score_many(crear_proveedor(), [], limit=5) == []
    assert reranker.calls == []


@pytest.mark.asyncio
async def test_score_and_persist_guarda_la_fila_a_pedido() -> None:
    scorer, repo = crear_scorer()
    proveedor = crear_proveedor()
    licitacion = crear_licitacion(uuid4())

    resultado = await scorer.score_and_persist(proveedor, licitacion)

    assert resultado.source == "on_demand"
    # No pasó por Qdrant: "no se midió" no es lo mismo que un parecido de cero.
    assert resultado.similarity_score is None
    guardado = await repo.get_by_proveedor_and_licitacion(proveedor.id, licitacion.id)
    assert guardado is not None
    assert guardado.final_score == resultado.final_score


@pytest.mark.asyncio
async def test_score_and_persist_reemplaza_el_calculo_anterior() -> None:
    scorer, repo = crear_scorer()
    proveedor = crear_proveedor()
    licitacion = crear_licitacion(uuid4())

    await scorer.score_and_persist(proveedor, licitacion)
    await scorer.score_and_persist(proveedor, licitacion)

    filas = await repo.get_by_supplier_id(proveedor.id)
    assert len(filas) == 1


@pytest.mark.asyncio
async def test_score_and_persist_falla_si_el_reranker_no_responde() -> None:
    scorer, repo = crear_scorer(reranker=RerankerVacio())
    proveedor = crear_proveedor()
    licitacion = crear_licitacion(uuid4())

    with pytest.raises(ScoreCalculationError):
        await scorer.score_and_persist(proveedor, licitacion)

    assert await repo.get_by_supplier_id(proveedor.id) == []
