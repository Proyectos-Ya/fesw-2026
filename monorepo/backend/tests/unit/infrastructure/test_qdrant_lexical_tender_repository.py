"""Pruebas unitarias para QdrantLexicalTenderRepository (Plan 256, Fase 1)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from qdrant_client.http.models import Modifier, PointStruct, SparseVector

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.lexical_tokenizer import SparseTermVector
from app.infrastructure.repositories.qdrant_lexical_tender_repository import (
    QdrantLexicalTenderRepository,
)

COLLECTION = "tender_lexical"
VECTOR_NAME = "lexical"


def _collections_response(*names: str) -> MagicMock:
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
def repository(client: AsyncMock) -> QdrantLexicalTenderRepository:
    return QdrantLexicalTenderRepository(client=client)


@pytest.mark.anyio
async def test_ensure_collection_crea_con_sparse_vectors_idf_si_no_existe(
    repository: QdrantLexicalTenderRepository, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response("tenders", "tender_items")

    await repository.ensure_collection()

    client.create_collection.assert_called_once()
    kwargs = client.create_collection.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["vectors_config"] == {}
    assert VECTOR_NAME in kwargs["sparse_vectors_config"]
    sparse_params = kwargs["sparse_vectors_config"][VECTOR_NAME]
    assert sparse_params.modifier == Modifier.IDF


@pytest.mark.anyio
async def test_ensure_collection_no_recrea_si_ya_existe(
    repository: QdrantLexicalTenderRepository, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response(COLLECTION)

    await repository.ensure_collection()

    client.create_collection.assert_not_called()


@pytest.mark.anyio
async def test_upsert_guarda_punto_con_sparse_vector(
    repository: QdrantLexicalTenderRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    sparse = SparseTermVector(indices=[10, 25, 100], values=[1.0, 2.0, 1.0])
    payload = {"status_code": 2, "region_id": 13}

    await repository.upsert(tender_id, sparse, payload=payload)

    client.upsert.assert_called_once()
    kwargs = client.upsert.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    points = kwargs["points"]
    assert len(points) == 1
    point = points[0]
    assert isinstance(point, PointStruct)
    assert point.id == str(tender_id)
    assert VECTOR_NAME in point.vector
    assert isinstance(point.vector[VECTOR_NAME], SparseVector)
    assert point.vector[VECTOR_NAME].indices == [10, 25, 100]
    assert point.vector[VECTOR_NAME].values == [1.0, 2.0, 1.0]
    assert point.payload == payload


@pytest.mark.anyio
async def test_upsert_con_vector_vacio_elimina_el_punto(
    repository: QdrantLexicalTenderRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    sparse_vacio = SparseTermVector(indices=[], values=[])

    await repository.upsert(tender_id, sparse_vacio)

    client.upsert.assert_not_called()
    client.delete.assert_called_once()


@pytest.mark.anyio
async def test_search_lexical_ejecuta_query_points_con_sparse_vector(
    repository: QdrantLexicalTenderRepository, client: AsyncMock
) -> None:
    query = SparseTermVector(indices=[10, 20], values=[1.0, 1.0])
    tender_id = uuid4()

    point_mock = MagicMock()
    point_mock.id = str(tender_id)
    point_mock.score = 3.45

    response_mock = MagicMock()
    response_mock.points = [point_mock]
    client.query_points.return_value = response_mock

    results = await repository.search_lexical(
        query_vector=query,
        limit=15,
        criteria=TenderFilterCriteria(region_ids=[13]),
    )

    client.query_points.assert_called_once()
    kwargs = client.query_points.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["using"] == VECTOR_NAME
    assert kwargs["limit"] == 15
    assert isinstance(kwargs["query"], SparseVector)
    assert kwargs["query"].indices == [10, 20]

    assert len(results) == 1
    assert results[0] == (tender_id, 3.45)
