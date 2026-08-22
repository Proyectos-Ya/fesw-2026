from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)

COLLECTION = "tenders"
VECTOR_NAME = "tender"
VECTOR_SIZE = 1024


# Función helper para generar vectores fake
def _make_vector() -> list[float]:
    return [0.1] * VECTOR_SIZE


# Función helper para simular respuestas del listado de colecciones de Qdrant
def _collections_response(*names: str) -> MagicMock:
    resp = MagicMock()
    mocks = []
    for n in names:
        m = MagicMock()
        m.name = n
        mocks.append(m)
    resp.collections = mocks
    return resp


# Función helper para simular puntos con score devueltos por la búsqueda vectorial
def _make_scored_point(tender_id: UUID, score: float) -> MagicMock:
    point = MagicMock()
    point.id = str(tender_id)
    point.score = score
    return point


# Fixture del cliente asíncrono mockeado
@pytest.fixture
def client() -> AsyncMock:
    return AsyncMock()


# Fixture del repositorio vectorial bajo prueba
@pytest.fixture
def repository(client: AsyncMock) -> QdrantTenderRepository:
    return QdrantTenderRepository(client=client, vector_size=VECTOR_SIZE)


@pytest.mark.anyio
async def test_ensure_collection_crea_con_vector_nombrado_si_no_existe(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    # Verifica que la colección sea creada con la configuración del vector nombrado 'tender'
    # si esta no existe previamente en Qdrant.
    client.get_collections.return_value = _collections_response()

    _svc = "app.infrastructure.repositories.qdrant_tender_repository"
    with patch(f"{_svc}.VectorParams") as mock_vp:
        await repository.ensure_collection()

    client.create_collection.assert_called_once()
    call_kwargs = client.create_collection.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    assert VECTOR_NAME in call_kwargs["vectors_config"]
    # Valida que la dimensión del vector sea 1024
    mock_vp.assert_called_once_with(
        size=VECTOR_SIZE, distance=mock_vp.call_args.kwargs["distance"]
    )


@pytest.mark.anyio
async def test_ensure_collection_no_crea_si_ya_existe(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    # Verifica que no se intente recrear la colección si esta ya existe en Qdrant.
    client.get_collections.return_value = _collections_response(COLLECTION)

    await repository.ensure_collection()

    client.create_collection.assert_not_called()


@pytest.mark.anyio
async def test_ensure_collection_crea_los_indices_de_payload(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """Sin índice de payload, Qdrant no puede estimar la cardinalidad del filtro.

    Esa estimación es la que decide entre recorrer el grafo HNSW enmascarando o
    hacer fuerza bruta sobre los puntos que pasan el filtro. Sin ella elige mal y
    el rendimiento se degrada en silencio, sin que ninguna consulta falle.
    """
    client.get_collections.return_value = _collections_response()

    await repository.ensure_collection()

    indexados = {
        call.kwargs["field_name"] for call in client.create_payload_index.call_args_list
    }
    assert indexados == {
        "status_code",
        "region_id",
        "available_amount_clp",
        "closing_at",
        "published_at",
    }


@pytest.mark.anyio
async def test_los_indices_se_crean_aunque_la_coleccion_ya_exista(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """La colección ya existe en todos los entornos actuales.

    Si los índices se crearan solo al crearla, nadie los tendría nunca sin borrar
    y reindexar. Crearlos siempre es idempotente en Qdrant.
    """
    client.get_collections.return_value = _collections_response(COLLECTION)

    await repository.ensure_collection()

    client.create_collection.assert_not_called()
    assert client.create_payload_index.call_count == 5


@pytest.mark.anyio
async def test_cada_indice_declara_su_tipo(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """Un rango sobre un campo indexado como `keyword` no compara como número."""
    client.get_collections.return_value = _collections_response(COLLECTION)

    await repository.ensure_collection()

    esquemas = {
        call.kwargs["field_name"]: call.kwargs["field_schema"]
        for call in client.create_payload_index.call_args_list
    }
    assert esquemas["status_code"] == "keyword"
    assert esquemas["region_id"] == "integer"
    assert esquemas["closing_at"] == "integer"
    assert esquemas["published_at"] == "integer"
    assert esquemas["available_amount_clp"] == "float"


@pytest.mark.anyio
async def test_upsert_con_vector_nombrado(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    # Verifica que upsert asigne correctamente el vector nombrado {"tender": vector}
    # y pase el payload de metadatos de forma íntegra.
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

    # Valida la estructura del punto indexado en Qdrant
    mock_ps.assert_called_once_with(
        id=str(tender_id), vector={VECTOR_NAME: vector}, payload=payload
    )


@pytest.mark.anyio
async def test_delete_con_point_ids_list(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    # Verifica que delete llame a Qdrant indicando el ID del punto de la licitación a eliminar.
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
    # Verifica la búsqueda por similitud usando el vector del perfil del proveedor,
    # validando que consulte el vector nombrado 'tender' y devuelva los IDs con sus scores.
    supplier_vector = _make_vector()
    t1, t2 = uuid4(), uuid4()
    response = MagicMock()
    response.points = [
        _make_scored_point(t1, 0.95),
        _make_scored_point(t2, 0.85),
    ]
    client.query_points.return_value = response

    results = await repository.search_by_supplier_vector(supplier_vector, limit=5)

    client.query_points.assert_called_once()
    call_kwargs = client.query_points.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    # Valida que se consulte el vector nombrado 'tender' con el embedding del proveedor
    assert call_kwargs["query"] == supplier_vector
    assert call_kwargs["using"] == VECTOR_NAME
    assert call_kwargs["limit"] == 5
    assert call_kwargs["query_filter"] is None

    # Valida el mapeo final a una lista de tuplas (UUID, score)
    assert results == [(t1, 0.95), (t2, 0.85)]


@pytest.mark.anyio
async def test_search_by_supplier_vector_con_filtros(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    # Verifica que la búsqueda por similitud aplique correctamente los filtros de metadatos en Qdrant.
    supplier_vector = _make_vector()
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response
    filters = {
        "code": "XYZ",
        "region_id": 16,
        "available_amount_clp": 1500000.0,
        "status_code": "publicada",
    }

    await repository.search_by_supplier_vector(
        supplier_vector, limit=5, filters=filters
    )

    client.query_points.assert_called_once()
    call_kwargs = client.query_points.call_args.kwargs
    # Valida que se haya construido y pasado un objeto de filtro de búsqueda
    assert call_kwargs["query_filter"] is not None
