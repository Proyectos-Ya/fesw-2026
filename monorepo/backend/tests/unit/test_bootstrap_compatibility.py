"""El cableado de la fórmula de compatibilidad en el composition root.

Tres cosas que el resto de los tests no ven porque construyen el scorer a mano:

- la fórmula sale de `settings`, no de coeficientes copiados en otro lado;
- el `model_version` que se le pasa al scorer y a `RankTendersUseCase` es el
  mismo y **identifica la fórmula**: es lo que vence la caché de
  recomendaciones al desplegar una calibración nueva;
- el escaneo de alertas (que corre fuera del ciclo de petición) usa el mismo
  scorer que los endpoints, y no una copia armada con la mitad de las piezas.
"""

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from app import bootstrap
from app.application.services.compatibility_formula import (
    CalibrationCoefficients,
    CompatibilityFormula,
)
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.config import settings
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from tests.unit.application.fakes import (
    FORMULA_DE_PRUEBA,
    FakeEmbeddingService,
    FakeRerankerService,
    InMemoryTenderItemVectorRepository,
)


def test_la_formula_sale_de_la_configuracion(monkeypatch) -> None:
    """Cada coeficiente viene de su propio setting, ninguno cruzado."""
    valores = {
        "compatibility_relevant_intercept": -1.0,
        "compatibility_relevant_reranker": 2.0,
        "compatibility_relevant_best_match": 3.0,
        "compatibility_relevant_coverage": 4.0,
        "compatibility_exact_intercept": -5.0,
        "compatibility_exact_reranker": 6.0,
        "compatibility_exact_best_match": 7.0,
        "compatibility_exact_coverage": 8.0,
    }
    for nombre, valor in valores.items():
        monkeypatch.setattr(settings, nombre, valor)

    formula = bootstrap.build_compatibility_formula()

    assert formula == CompatibilityFormula(
        relevant=CalibrationCoefficients(
            intercept=-1.0, reranker=2.0, best_match=3.0, coverage=4.0
        ),
        exact=CalibrationCoefficients(
            intercept=-5.0, reranker=6.0, best_match=7.0, coverage=8.0
        ),
    )


def test_la_version_del_modelo_identifica_la_formula(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-m3")

    assert bootstrap.compatibility_model_version() == "BAAI/bge-m3+compat-calib-v1"


def test_la_version_sigue_al_modelo_de_embeddings(monkeypatch) -> None:
    """Cambiar de modelo de embeddings también tiene que vencer la caché."""
    monkeypatch.setattr(settings, "embedding_model", "otro/modelo")

    assert bootstrap.compatibility_model_version().startswith("otro/modelo+")


def test_get_compatibility_scorer_arma_el_scorer_con_todas_sus_piezas() -> None:
    reranker = FakeRerankerService()
    embedding = FakeEmbeddingService()
    item_repo = InMemoryTenderItemVectorRepository()

    scorer = bootstrap.get_compatibility_scorer(
        session=MagicMock(),
        reranker_service=reranker,
        embedding_service=embedding,
        item_vector_repo=item_repo,
        formula=FORMULA_DE_PRUEBA,
    )

    assert isinstance(scorer, CompatibilityScorer)
    assert scorer.reranker_service is reranker
    assert scorer.embedding_service is embedding
    assert scorer.item_vector_repo is item_repo
    assert scorer.formula is FORMULA_DE_PRUEBA
    assert scorer.model_version == bootstrap.compatibility_model_version()


def test_el_ranking_y_el_scorer_comparten_la_version_del_modelo() -> None:
    """Si difirieran, el ranking guardaría filas que él mismo daría por vencidas
    en la siguiente petición y recalcularía en cada visita."""
    scorer = bootstrap.get_compatibility_scorer(
        session=MagicMock(),
        reranker_service=FakeRerankerService(),
        embedding_service=FakeEmbeddingService(),
        item_vector_repo=InMemoryTenderItemVectorRepository(),
        formula=FORMULA_DE_PRUEBA,
    )

    use_case = bootstrap.get_rank_tenders_use_case(
        session=MagicMock(),
        supplier_vector_repo=MagicMock(),
        tender_vector_repo=MagicMock(),
        scorer=scorer,
        embedding_service=FakeEmbeddingService(),
        item_vector_repo=InMemoryTenderItemVectorRepository(),
    )

    assert use_case.model_version == scorer.model_version
    assert use_case.scorer is scorer


def test_el_ranking_recibe_el_repo_de_partidas_y_el_embedding_de_la_busqueda_por_keywords() -> None:
    """Sin ambos, `RankTendersUseCase` no tiene segundo canal de candidatas y el
    ranking se queda solo con la búsqueda por perfil."""
    embedding = FakeEmbeddingService()
    item_repo = InMemoryTenderItemVectorRepository()

    use_case = bootstrap.get_rank_tenders_use_case(
        session=MagicMock(),
        supplier_vector_repo=MagicMock(),
        tender_vector_repo=MagicMock(),
        scorer=MagicMock(),
        embedding_service=embedding,
        item_vector_repo=item_repo,
    )

    assert use_case.item_vector_repo is item_repo
    assert use_case.embedding_service is embedding


def test_get_tender_item_vector_repo_usa_el_cliente_de_la_aplicacion() -> None:
    qdrant = MagicMock()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(qdrant_async_client=qdrant))
    )

    repo = bootstrap.get_tender_item_vector_repo(request)  # type: ignore[arg-type]

    assert isinstance(repo, QdrantTenderItemVectorRepository)
    assert repo._client is qdrant
    assert repo._vector_size == settings.embedding_vector_size


def test_get_compatibility_formula_devuelve_la_de_app_state() -> None:
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(compatibility_formula=FORMULA_DE_PRUEBA)
        )
    )

    assert bootstrap.get_compatibility_formula(request) is FORMULA_DE_PRUEBA  # type: ignore[arg-type]


def test_bootstrap_registra_la_formula_y_ya_no_la_ponderacion(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "build_embedding_service", FakeEmbeddingService)
    monkeypatch.setattr(bootstrap, "build_reranker_service", FakeRerankerService)
    app = FastAPI()

    bootstrap.bootstrap(app)

    assert app.state.compatibility_formula == bootstrap.build_compatibility_formula()
    assert not hasattr(app.state, "weighting_service")


@pytest.mark.asyncio
async def test_el_escaneo_de_alertas_usa_el_mismo_scorer_que_los_endpoints(
    monkeypatch,
) -> None:
    """`build_notification_runners` corre en el lifespan, con Qdrant ya conectado,
    y arma su propio `RankTendersUseCase`: tiene que llevar la fórmula, los
    vectores de partidas y la versión, igual que el de los endpoints."""
    app = FastAPI()
    qdrant = MagicMock()
    embedding = FakeEmbeddingService()
    reranker = FakeRerankerService()
    app.state.qdrant_async_client = qdrant
    app.state.embedding_service = embedding
    app.state.reranker_service = reranker
    app.state.compatibility_formula = FORMULA_DE_PRUEBA
    app.state.email_service = MagicMock()

    armados: list = []

    class EscaneoEspia:
        def __init__(self, rank_tenders_use_case, **_kwargs) -> None:
            armados.append(rank_tenders_use_case)

        async def execute(self, _user_id):
            return []

    class ProveedoresFalsos:
        def __init__(self, _session) -> None: ...

        async def list_user_ids_with_profile(self):
            return [uuid.uuid4()]

    @asynccontextmanager
    async def sesion_falsa():
        yield MagicMock()

    async def sin_pausa(_segundos) -> None: ...

    monkeypatch.setattr(bootstrap, "ScanSupplierForAlertsUseCase", EscaneoEspia)
    monkeypatch.setattr(bootstrap, "SupplierRepository", ProveedoresFalsos)
    monkeypatch.setattr(bootstrap, "async_session_maker", sesion_falsa)
    monkeypatch.setattr(bootstrap.asyncio, "sleep", sin_pausa)

    scan_all, *_ = bootstrap.build_notification_runners(app)
    await scan_all()

    [rank_tenders] = armados
    scorer = rank_tenders.scorer
    assert isinstance(scorer, CompatibilityScorer)
    assert scorer.reranker_service is reranker
    assert scorer.embedding_service is embedding
    assert scorer.formula is FORMULA_DE_PRUEBA
    assert isinstance(scorer.item_vector_repo, QdrantTenderItemVectorRepository)
    assert scorer.item_vector_repo._client is qdrant
    assert scorer.model_version == bootstrap.compatibility_model_version()
    assert rank_tenders.model_version == scorer.model_version
    # Y el mismo segundo canal de candidatas (keywords contra partidas): el
    # escaneo reescribe el ranking que ve el usuario, así que si buscara con
    # menos piezas que el endpoint, cada escaneo le cambiaría la lista.
    assert rank_tenders.embedding_service is embedding
    assert isinstance(rank_tenders.item_vector_repo, QdrantTenderItemVectorRepository)
    assert rank_tenders.item_vector_repo._client is qdrant
