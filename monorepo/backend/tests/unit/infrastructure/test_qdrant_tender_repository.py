from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
import pytest
from app.infrastructure.repositories.qdrant_tender_repository import QdrantTenderRepository

COLLECTION = "tenders"
VECTOR_NAME = "tender"
VECTOR_SIZE = 1024

def _make_vector() -> list[float]:
    return [0.1] * VECTOR_SIZE

def _collections_response(*names: str) -> MagicMock:
    resp = MagicMock()
    mocks = []
    for n in names:
        m = MagicMock()
        m.name = n
        mocks.append(m)
    resp.collections = mocks
    return resp

def _make_scored_point(tender_id: UUID, score: float) -> MagicMock:
    point = MagicMock()
    point.id = str(tender_id)
    point.score = score
    return point

@pytest.fixture
def client() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def repository(client: AsyncMock) -> QdrantTenderRepository:
    return QdrantTenderRepository(client=client, vector_size=VECTOR_SIZE)

@pytest.mark.anyio
async def test_ensure_collection_crea_con_vector_nombrado_si_no_existe(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response()
    
    _svc = "app.infrastructure.repositories.qdrant_tender_repository"
    with patch(f"{_svc}.VectorParams") as mock_vp:
        await repository.ensure_collection()
        
    client.create_collection.assert_called_once()
    call_kwargs = client.create_collection.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    assert VECTOR_NAME in call_kwargs["vectors_config"]
    mock_vp.assert_called_once_with(size=VECTOR_SIZE, distance=mock_vp.call_args.kwargs["distance"])

@pytest.mark.anyio
async def test_ensure_collection_no_crea_si_ya_existe(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response(COLLECTION)
    
    await repository.ensure_collection()
    
    client.create_collection.assert_not_called()

@pytest.mark.anyio
async def test_upsert_con_vector_nombrado(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    vector = _make_vector()
    payload = {"code": "123", "region_id": 1}
    
    _svc = "app.infrastructure.repositories.qdrant_tender_repository"
    with patch(f"{_svc}.PointStruct") as mock_ps:
        mock_ps.return_value = MagicMock()
        await repository.upsert(tender_id, vector, payload)
        
    client.upsert.assert_called_once()
    call_kwargs = client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    
    mock_ps.assert_called_once_with(
        id=str(tender_id),
        vector={VECTOR_NAME: vector},
        payload=payload
    )

@pytest.mark.anyio
async def test_delete_con_point_ids_list(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    
    _svc = "app.infrastructure.repositories.qdrant_tender_repository"
    with patch(f"{_svc}.PointIdsList") as mock_pil:
        mock_pil.return_value = MagicMock()
        await repository.delete(tender_id)
        
    client.delete.assert_called_once()
    call_kwargs = client.delete.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    mock_pil.assert_called_once_with(points=[str(tender_id)])

@pytest.mark.anyio
async def test_search_by_supplier_vector(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    supplier_vector = _make_vector()
    t1, t2 = uuid4(), uuid4()
    client.search.return_value = [
        _make_scored_point(t1, 0.95),
        _make_scored_point(t2, 0.85),
    ]
    
    results = await repository.search_by_supplier_vector(supplier_vector, limit=5)
    
    client.search.assert_called_once()
    call_kwargs = client.search.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    assert call_kwargs["query_vector"] == (VECTOR_NAME, supplier_vector)
    assert call_kwargs["limit"] == 5
    assert call_kwargs["query_filter"] is None
    
    assert results == [(t1, 0.95), (t2, 0.85)]

@pytest.mark.anyio
async def test_search_by_supplier_vector_con_filtros(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    supplier_vector = _make_vector()
    client.search.return_value = []
    filters = {
        "code": "XYZ",
        "region_id": 16,
        "province": "Santiago",
        "available_amount_clp": 1500000.0,
        "status_code": "publicada"
    }
    
    await repository.search_by_supplier_vector(supplier_vector, limit=5, filters=filters)
    
    client.search.assert_called_once()
    call_kwargs = client.search.call_args.kwargs
    assert call_kwargs["query_filter"] is not None
