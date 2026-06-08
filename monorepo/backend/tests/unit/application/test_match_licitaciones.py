from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.repositories.proveedor_repository import IProveedorRepository
from app.application.repositories.resultado_matching_repository import (
    IResultadoMatchingRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.text_builder import TextBuilder
from app.application.services.vector_store_service import (
    FiltrosVectoriales,
    IVectorStoreService,
    VectorSearchResult,
)
from app.application.useCases.match_licitaciones import MatchLicitacionesUseCase
from app.domain.entities.proveedor import Proveedor
from app.domain.errors.proveedor_errors import ProveedorNoEncontrado
from app.domain.models.matching_schema import MatchRequest

PROVEEDOR_ID = uuid4()
LICITACION_ID_1 = uuid4()
LICITACION_ID_2 = uuid4()


def _make_proveedor() -> Proveedor:
    return Proveedor(
        id=PROVEEDOR_ID,
        rut="12345678-9",
        razon_social="Empresa Test SpA",
        rubros=["Tecnología", "Software"],
        descripcion_libre="Desarrollo de software a medida",
        palabras_clave=["Python", "FastAPI"],
    )


def _make_vector() -> list[float]:
    return [0.1] * 1024


@pytest.fixture
def deps() -> dict:
    return {
        "proveedor_repo": AsyncMock(spec=IProveedorRepository),
        "embedding_service": AsyncMock(spec=IEmbeddingService),
        "vector_store": AsyncMock(spec=IVectorStoreService),
        "resultado_matching_repo": AsyncMock(spec=IResultadoMatchingRepository),
        "text_builder": TextBuilder(),
        "version_modelo": "bge-m3-v1",
    }


@pytest.fixture
def use_case(deps: dict) -> MatchLicitacionesUseCase:
    return MatchLicitacionesUseCase(**deps)


@pytest.fixture
def request_default() -> MatchRequest:
    return MatchRequest(proveedor_id=PROVEEDOR_ID)


# ---------------------------------------------------------------------------
# Proveedor no encontrado
# ---------------------------------------------------------------------------


async def test_proveedor_no_encontrado_lanza_excepcion(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    deps["proveedor_repo"].get_by_id.return_value = None

    with pytest.raises(ProveedorNoEncontrado):
        await use_case.execute(request_default)


async def test_proveedor_no_encontrado_no_llama_embed(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    deps["proveedor_repo"].get_by_id.return_value = None

    with pytest.raises(ProveedorNoEncontrado):
        await use_case.execute(request_default)

    deps["embedding_service"].embed.assert_not_called()


# ---------------------------------------------------------------------------
# Sin resultados de búsqueda
# ---------------------------------------------------------------------------


async def test_sin_resultados_retorna_lista_vacia(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = []

    resultado = await use_case.execute(request_default)

    assert resultado.resultados == []


async def test_sin_resultados_no_llama_save_bulk(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = []

    await use_case.execute(request_default)

    deps["resultado_matching_repo"].save_bulk.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_resultados_correctos_happy_path(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    search_results = [
        VectorSearchResult(licitacion_id=LICITACION_ID_1, score=0.95),
        VectorSearchResult(licitacion_id=LICITACION_ID_2, score=0.80),
    ]
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = search_results

    resultado = await use_case.execute(request_default)

    assert len(resultado.resultados) == 2
    assert resultado.resultados[0].licitacion_id == LICITACION_ID_1
    assert resultado.resultados[1].licitacion_id == LICITACION_ID_2


async def test_score_final_igual_a_score_similitud(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    search_results = [VectorSearchResult(licitacion_id=LICITACION_ID_1, score=0.87)]
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = search_results

    resultado = await use_case.execute(request_default)

    assert resultado.resultados[0].score_similitud == 0.87
    assert resultado.resultados[0].score_final == 0.87
    assert resultado.resultados[0].score_reranker is None


async def test_save_bulk_llamado_con_resultados(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    search_results = [
        VectorSearchResult(licitacion_id=LICITACION_ID_1, score=0.95),
        VectorSearchResult(licitacion_id=LICITACION_ID_2, score=0.80),
    ]
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = search_results

    await use_case.execute(request_default)

    deps["resultado_matching_repo"].save_bulk.assert_called_once()
    saved = deps["resultado_matching_repo"].save_bulk.call_args[0][0]
    assert len(saved) == 2


# ---------------------------------------------------------------------------
# Filtros, parámetros y propagación de metadatos
# ---------------------------------------------------------------------------


async def test_filtros_se_pasan_a_vector_store(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
) -> None:
    request = MatchRequest(
        proveedor_id=PROVEEDOR_ID,
        region="Metropolitana",
        monto_min=1_000_000.0,
        top_k=5,
    )
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = []

    await use_case.execute(request)

    call_kwargs = deps["vector_store"].search.call_args.kwargs
    assert call_kwargs["top_k"] == 5
    assert call_kwargs["filtros"] == FiltrosVectoriales(
        region="Metropolitana", monto_min=1_000_000.0
    )


async def test_version_modelo_en_resultado(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = []

    resultado = await use_case.execute(request_default)

    assert resultado.version_modelo == "bge-m3-v1"


async def test_embed_llamado_con_texto_proveedor(
    use_case: MatchLicitacionesUseCase,
    deps: dict,
    request_default: MatchRequest,
) -> None:
    deps["proveedor_repo"].get_by_id.return_value = _make_proveedor()
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["vector_store"].search.return_value = []

    await use_case.execute(request_default)

    deps["embedding_service"].embed.assert_called_once()
    textos = deps["embedding_service"].embed.call_args[0][0]
    assert len(textos) == 1
    assert isinstance(textos[0], str)
    assert len(textos[0]) > 0
