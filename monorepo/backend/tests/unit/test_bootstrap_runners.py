"""Los runners arman sus casos de uso igual que la API.

El escaneo de alertas reutiliza `RankTendersUseCase`. Si su copia diverge de la
que arma la API, el scheduler se comporta distinto sin que ningún test lo note:
pasó con el servicio de embeddings, que la API recibía y el escaneo no, y una
empresa sin vector en Qdrant dejaba de recibir alertas en silencio.
"""

from unittest.mock import AsyncMock

from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.datastructures import State

from app.bootstrap.runners import build_scan_rank_tenders_use_case
from tests.unit.application.fakes import FakeEmbeddingService


def _estado_de_la_app() -> State:
    state = State()
    state.qdrant_async_client = object()
    state.reranker_service = object()
    state.weighting_service = object()
    state.embedding_service = FakeEmbeddingService()
    return state


def test_el_escaneo_puede_regenerar_el_vector_de_la_empresa():
    state = _estado_de_la_app()

    use_case = build_scan_rank_tenders_use_case(state, AsyncMock(spec=AsyncSession))

    # Sin él, RankTendersUseCase lanza SupplierVectorNotFound en vez de generar
    # el vector que falta, y el escaneo salta a esa empresa.
    assert use_case.embedding_service is state.embedding_service
