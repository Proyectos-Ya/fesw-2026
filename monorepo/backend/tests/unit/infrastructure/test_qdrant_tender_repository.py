from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.shared.datetime_utils import to_utc_epoch

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
        "provincia_id",
        "comuna_id",
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
    assert client.create_payload_index.call_count == 7


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
    assert esquemas["provincia_id"] == "integer"
    assert esquemas["comuna_id"] == "integer"
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


# ---------------------------------------------------------------------------
# search_by_vector: una sola operación para los tres usos
#
#   dashboard de recomendaciones -> vector del proveedor, filtro de estado
#   buscador con texto           -> vector de la consulta, filtros del usuario
#   buscador sin texto           -> vector del proveedor, filtros del usuario
#
# Lo único que cambia entre ellos es de dónde sale el vector, así que el método
# no lleva el nombre de ninguno de los tres casos.
# ---------------------------------------------------------------------------


def _conditions_by_key(query_filter) -> dict:
    """Indexa las condiciones del filtro de Qdrant por el campo del payload."""
    assert query_filter is not None, "se esperaba un filtro, llegó None"
    return {c.key: c for c in query_filter.must}


def _captured_filter(client: AsyncMock):
    return client.query_points.call_args.kwargs["query_filter"]


@pytest.mark.anyio
async def test_search_by_vector_sin_criterios_no_construye_filtro(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    vector = _make_vector()
    t1, t2 = uuid4(), uuid4()
    response = MagicMock()
    response.points = [_make_scored_point(t1, 0.95), _make_scored_point(t2, 0.85)]
    client.query_points.return_value = response

    results = await repository.search_by_vector(vector, limit=5)

    call_kwargs = client.query_points.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    assert call_kwargs["query"] == vector
    assert call_kwargs["using"] == VECTOR_NAME
    assert call_kwargs["limit"] == 5
    assert call_kwargs["query_filter"] is None
    assert results == [(t1, 0.95), (t2, 0.85)]


@pytest.mark.anyio
async def test_search_by_vector_pasa_el_offset(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """Permite pedir el siguiente bloque cuando el usuario llega al tope."""
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(_make_vector(), limit=500, offset=500)

    assert client.query_points.call_args.kwargs["offset"] == 500


@pytest.mark.anyio
async def test_las_listas_se_traducen_a_match_any(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """`MatchValue` compara contra un único valor; para listas hace falta `MatchAny`."""
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(
        _make_vector(),
        limit=5,
        criteria=TenderFilterCriteria(
            status_codes=["publicada", "cerrada"], region_ids=[13, 5]
        ),
    )

    condiciones = _conditions_by_key(_captured_filter(client))
    assert condiciones["status_code"].match.any == ["publicada", "cerrada"]
    assert condiciones["region_id"].match.any == [13, 5]


@pytest.mark.anyio
async def test_provincia_y_comuna_se_traducen_a_match_value(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """A diferencia de región, `province_id`/`commune_id` son un solo valor
    (selección única en el frontend), así que usan `MatchValue`, no `MatchAny`."""
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(
        _make_vector(),
        limit=5,
        criteria=TenderFilterCriteria(province_id=22, commune_id=333),
    )

    condiciones = _conditions_by_key(_captured_filter(client))
    assert condiciones["provincia_id"].match.value == 22
    assert condiciones["comuna_id"].match.value == 333


@pytest.mark.anyio
async def test_sin_provincia_ni_comuna_no_agrega_esas_condiciones(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(
        _make_vector(), limit=5, criteria=TenderFilterCriteria(region_ids=[13])
    )

    condiciones = _conditions_by_key(_captured_filter(client))
    assert "provincia_id" not in condiciones
    assert "comuna_id" not in condiciones


@pytest.mark.anyio
async def test_el_rango_de_monto_es_inclusivo_en_ambos_extremos(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """Misma semántica que `tenderMatchesBudget` del frontend, que ya usa límites
    inclusivos. Si divergieran, el mismo rango daría resultados distintos en el
    dashboard y en el buscador."""
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(
        _make_vector(),
        limit=5,
        criteria=TenderFilterCriteria(min_amount=100_000.0, max_amount=500_000.0),
    )

    rango = _conditions_by_key(_captured_filter(client))["available_amount_clp"].range
    assert rango.gte == 100_000.0
    assert rango.lte == 500_000.0
    assert rango.gt is None and rango.lt is None


@pytest.mark.anyio
async def test_un_solo_extremo_del_rango_deja_el_otro_abierto(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(
        _make_vector(), limit=5, criteria=TenderFilterCriteria(min_amount=100_000.0)
    )

    rango = _conditions_by_key(_captured_filter(client))["available_amount_clp"].range
    assert rango.gte == 100_000.0
    assert rango.lte is None


@pytest.mark.anyio
async def test_las_fechas_se_convierten_a_epoch_en_el_adaptador(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """El criterio habla en `datetime`; el epoch es un detalle de cómo Qdrant
    almacena, así que la conversión ocurre acá y no cruza hacia la aplicación."""
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response
    desde = datetime(2026, 8, 1, 0, 0, 0)
    hasta = datetime(2026, 8, 31, 23, 59, 0)

    await repository.search_by_vector(
        _make_vector(),
        limit=5,
        criteria=TenderFilterCriteria(closing_from=desde, closing_to=hasta),
    )

    rango = _conditions_by_key(_captured_filter(client))["closing_at"].range
    assert rango.gte == to_utc_epoch(desde)
    assert rango.lte == to_utc_epoch(hasta)


@pytest.mark.anyio
async def test_published_at_tambien_admite_rango(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response
    desde = datetime(2026, 8, 1, 0, 0, 0)

    await repository.search_by_vector(
        _make_vector(), limit=5, criteria=TenderFilterCriteria(published_from=desde)
    )

    rango = _conditions_by_key(_captured_filter(client))["published_at"].range
    assert rango.gte == to_utc_epoch(desde)


@pytest.mark.anyio
async def test_los_criterios_se_combinan_en_un_must(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """Todas las condiciones son obligatorias: el usuario que pide región y plazo
    quiere ambas, no cualquiera de las dos."""
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(
        _make_vector(),
        limit=5,
        criteria=TenderFilterCriteria(
            status_codes=["publicada"],
            region_ids=[13],
            province_id=22,
            commune_id=333,
            closing_from=datetime(2026, 8, 1),
            min_amount=1000.0,
        ),
    )

    condiciones = _conditions_by_key(_captured_filter(client))
    assert set(condiciones) == {
        "status_code",
        "region_id",
        "provincia_id",
        "comuna_id",
        "closing_at",
        "available_amount_clp",
    }


@pytest.mark.anyio
async def test_un_criterio_vacio_no_construye_filtro(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """Sin condiciones, el filtro debe ser None y no un `must` vacío, que Qdrant
    interpretaría como una restricción que nada cumple."""
    response = MagicMock()
    response.points = []
    client.query_points.return_value = response

    await repository.search_by_vector(
        _make_vector(), limit=5, criteria=TenderFilterCriteria()
    )

    assert _captured_filter(client) is None


@pytest.mark.anyio
async def test_count_devuelve_el_total_exacto(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    """El total de coincidencias no depende del vector ni del corte: sale de
    contar cuántas licitaciones pasan los filtros estructurados."""
    client.count.return_value = MagicMock(count=137)

    total = await repository.count(TenderFilterCriteria(region_ids=[13]))

    assert total == 137
    call_kwargs = client.count.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION
    assert call_kwargs["exact"] is True
    assert _conditions_by_key(call_kwargs["count_filter"])["region_id"].match.any == [
        13
    ]


@pytest.mark.anyio
async def test_count_sin_criterios_cuenta_todo(
    repository: QdrantTenderRepository, client: AsyncMock
) -> None:
    client.count.return_value = MagicMock(count=4000)

    total = await repository.count(TenderFilterCriteria())

    assert total == 4000
    assert client.count.call_args.kwargs["count_filter"] is None
