from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.application.services.vector_store_service import FiltrosVectoriales
from app.infrastructure.services.qdrant_vector_store import QdrantVectorStore

COLLECTION = "licitaciones"
VECTOR_SIZE = 1024


def _make_vector() -> list[float]:
    return [0.1] * VECTOR_SIZE


def _make_scored_point(licitacion_id: UUID, score: float) -> MagicMock:
    point = MagicMock()
    point.payload = {"licitacion_id": str(licitacion_id)}
    point.score = score
    return point


def _collections_response(*names: str) -> MagicMock:
    # MagicMock(name=...) sets the mock's internal label, NOT the .name attribute.
    # We must assign .name explicitly after creation.
    resp = MagicMock()
    mocks = []
    for n in names:
        m = MagicMock()
        m.name = n
        mocks.append(m)
    resp.collections = mocks
    return resp


@pytest.fixture
def client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def store(client: AsyncMock) -> QdrantVectorStore:
    return QdrantVectorStore(
        client=client, collection_name=COLLECTION, vector_size=VECTOR_SIZE
    )


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------


async def test_ensure_collection_crea_si_no_existe(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response()

    await store.ensure_collection()

    client.create_collection.assert_called_once()
    call_kwargs = client.create_collection.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION


async def test_ensure_collection_no_crea_si_ya_existe(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response(COLLECTION)

    await store.ensure_collection()

    client.create_collection.assert_not_called()


async def test_ensure_collection_usa_cosine_y_vector_size(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response()

    _svc = "app.infrastructure.services.qdrant_vector_store"
    with patch(f"{_svc}.VectorParams") as mock_vp:
        await store.ensure_collection()

    assert mock_vp.call_args.kwargs["size"] == VECTOR_SIZE


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------


async def test_upsert_llama_client_upsert(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    await store.upsert(uuid4(), _make_vector(), {})

    client.upsert.assert_called_once()


async def test_upsert_usa_collection_correcta(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    await store.upsert(uuid4(), _make_vector(), {})

    assert client.upsert.call_args.kwargs["collection_name"] == COLLECTION


async def test_upsert_convierte_uuid_a_string(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    vector_id = uuid4()
    _svc = "app.infrastructure.services.qdrant_vector_store"
    with patch(f"{_svc}.PointStruct") as mock_ps:
        mock_ps.return_value = MagicMock()
        await store.upsert(vector_id, _make_vector(), {})

    assert mock_ps.call_args.kwargs["id"] == str(vector_id)


async def test_upsert_pasa_payload(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    payload = {"licitacion_id": str(uuid4()), "estado": "activa"}
    _svc = "app.infrastructure.services.qdrant_vector_store"
    with patch(f"{_svc}.PointStruct") as mock_ps:
        mock_ps.return_value = MagicMock()
        await store.upsert(uuid4(), _make_vector(), payload)

    assert mock_ps.call_args.kwargs["payload"] == payload


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


async def test_search_retorna_vector_search_results(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    lid1, lid2 = uuid4(), uuid4()
    client.search.return_value = [
        _make_scored_point(lid1, 0.95),
        _make_scored_point(lid2, 0.80),
    ]

    results = await store.search(_make_vector(), top_k=2)

    assert len(results) == 2
    assert results[0].licitacion_id == lid1
    assert results[0].score == 0.95
    assert results[1].licitacion_id == lid2


async def test_search_sin_resultados_retorna_lista_vacia(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.search.return_value = []

    results = await store.search(_make_vector(), top_k=10)

    assert results == []


async def test_search_pasa_top_k_como_limit(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.search.return_value = []

    await store.search(_make_vector(), top_k=7)

    assert client.search.call_args.kwargs["limit"] == 7


async def test_search_sin_filtros_pasa_query_filter_none(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.search.return_value = []

    await store.search(_make_vector(), top_k=5, filtros=None)

    assert client.search.call_args.kwargs["query_filter"] is None


async def test_search_con_filtros_vacios_pasa_query_filter_none(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.search.return_value = []

    await store.search(_make_vector(), top_k=5, filtros=FiltrosVectoriales())

    assert client.search.call_args.kwargs["query_filter"] is None


async def test_search_con_region_query_filter_no_es_none(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.search.return_value = []

    await store.search(
        _make_vector(), top_k=5, filtros=FiltrosVectoriales(region="Metropolitana")
    )

    assert client.search.call_args.kwargs["query_filter"] is not None


async def test_search_con_monto_min_query_filter_no_es_none(
    store: QdrantVectorStore, client: AsyncMock
) -> None:
    client.search.return_value = []

    await store.search(
        _make_vector(), top_k=5, filtros=FiltrosVectoriales(monto_min=500_000.0)
    )

    assert client.search.call_args.kwargs["query_filter"] is not None
