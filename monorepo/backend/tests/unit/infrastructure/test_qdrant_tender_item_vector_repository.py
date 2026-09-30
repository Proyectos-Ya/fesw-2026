from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from qdrant_client.http.models import (
    Distance,
    MultiVectorComparator,
    PointIdsList,
    PointStruct,
)

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.infrastructure.repositories.qdrant_tender_filters import PAYLOAD_INDEXES
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.shared.datetime_utils import to_utc_epoch

COLLECTION = "tender_items"
VECTOR_NAME = "items"
VECTOR_SIZE = 4


# Función helper para generar los vectores de las partidas de una licitación
def _make_item_vectors(n: int = 2) -> list[list[float]]:
    return [[0.1 * (i + 1)] * VECTOR_SIZE for i in range(n)]


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


# Función helper para simular un punto devuelto por `retrieve` con multivector
def _make_record(tender_id: UUID, item_vectors: list[list[float]]) -> MagicMock:
    record = MagicMock()
    record.id = str(tender_id)
    record.vector = {VECTOR_NAME: item_vectors}
    return record


# Fixture del cliente asíncrono mockeado
@pytest.fixture
def client() -> AsyncMock:
    return AsyncMock()


# Fixture del repositorio de vectores de partidas bajo prueba
@pytest.fixture
def repository(client: AsyncMock) -> QdrantTenderItemVectorRepository:
    return QdrantTenderItemVectorRepository(client=client, vector_size=VECTOR_SIZE)


@pytest.mark.anyio
async def test_ensure_collection_crea_con_multivector_max_sim_si_no_existe(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    # La colección debe crearse con un vector nombrado 'items' de tipo multivector
    # y comparador MAX_SIM: es lo que permite puntuar un vector de consulta contra
    # el mejor calce entre todas las partidas de la licitación.
    client.get_collections.return_value = _collections_response("tenders")

    await repository.ensure_collection()

    client.create_collection.assert_called_once()
    kwargs = client.create_collection.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    params = kwargs["vectors_config"][VECTOR_NAME]
    assert params.size == VECTOR_SIZE
    assert params.distance == Distance.COSINE
    assert params.multivector_config is not None
    assert params.multivector_config.comparator == MultiVectorComparator.MAX_SIM


@pytest.mark.anyio
async def test_ensure_collection_no_crea_si_ya_existe(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response(COLLECTION)

    await repository.ensure_collection()

    client.create_collection.assert_not_called()


@pytest.mark.anyio
async def test_ensure_collection_no_toca_la_coleccion_tenders(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    # Que "tenders" exista no debe impedir crear "tender_items", y la colección
    # de licitaciones no se modifica nunca desde este repositorio.
    client.get_collections.return_value = _collections_response("tenders")

    await repository.ensure_collection()

    nombres = {
        call.kwargs["collection_name"]
        for call in client.create_collection.call_args_list
    }
    assert nombres == {COLLECTION}
    client.delete_collection.assert_not_called()


@pytest.mark.anyio
async def test_upsert_guarda_un_punto_por_licitacion_con_todos_los_vectores(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    vectors = _make_item_vectors(3)

    await repository.upsert(tender_id, vectors)

    client.upsert.assert_called_once()
    kwargs = client.upsert.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    points = kwargs["points"]
    assert len(points) == 1
    point = points[0]
    assert isinstance(point, PointStruct)
    assert point.id == str(tender_id)
    assert point.vector == {VECTOR_NAME: vectors}
    client.delete.assert_not_called()


@pytest.mark.anyio
async def test_upsert_con_lista_vacia_borra_el_punto(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    # Una licitación sin partidas no tiene vectores: Qdrant rechaza un multivector
    # vacío, y de todos modos un punto viejo no debe sobrevivir a un reemplazo.
    tender_id = uuid4()

    await repository.upsert(tender_id, [])

    client.upsert.assert_not_called()
    client.delete.assert_called_once()
    kwargs = client.delete.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["points_selector"] == PointIdsList(points=[str(tender_id)])


@pytest.mark.anyio
async def test_delete_elimina_el_punto_de_la_licitacion(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()

    await repository.delete(tender_id)

    client.delete.assert_called_once()
    kwargs = client.delete.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["points_selector"] == PointIdsList(points=[str(tender_id)])


@pytest.mark.anyio
async def test_get_many_devuelve_los_vectores_por_id_convertido_a_uuid(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    id_a, id_b = uuid4(), uuid4()
    vectors_a = _make_item_vectors(2)
    vectors_b = _make_item_vectors(1)
    client.retrieve.return_value = [
        _make_record(id_a, vectors_a),
        _make_record(id_b, vectors_b),
    ]

    result = await repository.get_many([id_a, id_b])

    assert result == {id_a: vectors_a, id_b: vectors_b}
    assert all(isinstance(k, UUID) for k in result)
    client.retrieve.assert_called_once()
    kwargs = client.retrieve.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["ids"] == [str(id_a), str(id_b)]
    assert kwargs["with_vectors"] == [VECTOR_NAME]
    assert kwargs["with_payload"] is False


@pytest.mark.anyio
async def test_get_many_omite_las_licitaciones_sin_vectores(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    # Qdrant simplemente no devuelve los ids que no existen: no deben aparecer en
    # el dict ni fallar.
    presente, ausente = uuid4(), uuid4()
    vectors = _make_item_vectors(2)
    client.retrieve.return_value = [_make_record(presente, vectors)]

    result = await repository.get_many([presente, ausente])

    assert result == {presente: vectors}
    assert ausente not in result


@pytest.mark.anyio
async def test_get_many_ignora_puntos_sin_el_vector_items(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    con_vectores, sin_vectores = uuid4(), uuid4()
    vectors = _make_item_vectors(2)
    vacio = MagicMock()
    vacio.id = str(sin_vectores)
    vacio.vector = {}
    client.retrieve.return_value = [_make_record(con_vectores, vectors), vacio]

    result = await repository.get_many([con_vectores, sin_vectores])

    assert result == {con_vectores: vectors}


@pytest.mark.anyio
async def test_get_many_sin_ids_no_consulta_qdrant(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    result = await repository.get_many([])

    assert result == {}
    client.retrieve.assert_not_called()


@pytest.mark.anyio
async def test_get_many_consulta_en_lotes_de_256(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    # 600 ids -> 3 lotes (256 + 256 + 88). Cada lote es una llamada a `retrieve` y
    # los resultados de todos se combinan en un solo dict.
    ids = [uuid4() for _ in range(600)]
    vectors = _make_item_vectors(1)

    async def _retrieve(**kwargs):
        return [_make_record(UUID(i), vectors) for i in kwargs["ids"]]

    client.retrieve.side_effect = _retrieve

    result = await repository.get_many(ids)

    assert client.retrieve.call_count == 3
    tamanos = [len(c.kwargs["ids"]) for c in client.retrieve.call_args_list]
    assert tamanos == [256, 256, 88]
    assert set(result) == set(ids)


@pytest.mark.anyio
async def test_get_many_no_repite_ids_duplicados(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    vectors = _make_item_vectors(1)
    client.retrieve.return_value = [_make_record(tender_id, vectors)]

    result = await repository.get_many([tender_id, tender_id])

    assert result == {tender_id: vectors}
    assert client.retrieve.call_args.kwargs["ids"] == [str(tender_id)]


# ---------------------------------------------------------------------------
# Payload: las partidas se filtran con los mismos campos que "tenders"
#
# Sin payload no se puede pre-filtrar por estado o región dentro de la búsqueda, y
# filtrar después del top-K está prohibido (ver `TenderFilterCriteria`).
# ---------------------------------------------------------------------------

_PAYLOAD = {
    "status_code": "publicada",
    "region_id": 13,
    "provincia_id": 51,
    "comuna_id": 295,
    "available_amount_clp": 50_000_000.0,
    "closing_at": 1_782_000_000,
    "published_at": 1_767_000_000,
}


def _record_existente(tender_id: UUID) -> MagicMock:
    record = MagicMock()
    record.id = str(tender_id)
    return record


@pytest.mark.anyio
async def test_ensure_collection_crea_los_indices_de_payload_al_crear(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    client.get_collections.return_value = _collections_response("tenders")

    await repository.ensure_collection()

    esquemas = {
        c.kwargs["field_name"]: c.kwargs["field_schema"]
        for c in client.create_payload_index.call_args_list
    }
    assert esquemas == PAYLOAD_INDEXES
    assert all(
        c.kwargs["collection_name"] == COLLECTION
        for c in client.create_payload_index.call_args_list
    )


@pytest.mark.anyio
async def test_los_indices_se_crean_aunque_la_coleccion_ya_exista(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    """"tender_items" ya existe en los entornos que corrieron el backfill de
    vectores: crear los índices solo al crearla dejaría a esos entornos sin ellos.
    Crearlos es idempotente en Qdrant."""
    client.get_collections.return_value = _collections_response(COLLECTION)

    await repository.ensure_collection()

    client.create_collection.assert_not_called()
    assert client.create_payload_index.call_count == len(PAYLOAD_INDEXES) == 7


@pytest.mark.anyio
async def test_upsert_lleva_el_payload_en_el_punto(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    vectors = _make_item_vectors(2)

    await repository.upsert(tender_id, vectors, _PAYLOAD)

    point = client.upsert.call_args.kwargs["points"][0]
    assert point.id == str(tender_id)
    assert point.vector == {VECTOR_NAME: vectors}
    assert point.payload == _PAYLOAD


@pytest.mark.anyio
async def test_upsert_sin_payload_deja_el_punto_sin_payload(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    await repository.upsert(uuid4(), _make_item_vectors(1))

    assert client.upsert.call_args.kwargs["points"][0].payload is None


@pytest.mark.anyio
async def test_upsert_con_lista_vacia_ignora_el_payload_y_borra_el_punto(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    await repository.upsert(uuid4(), [], _PAYLOAD)

    client.upsert.assert_not_called()
    client.delete.assert_called_once()


@pytest.mark.anyio
async def test_set_payload_actualiza_solo_el_payload_del_punto_existente(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    """`set_payload` y no `upsert`: el upsert exige los vectores completos, y en un
    cambio de metadatos no hay por qué releerlos ni recalcularlos."""
    tender_id = uuid4()
    client.retrieve.return_value = [_record_existente(tender_id)]

    await repository.set_payload(tender_id, {"status_code": "cerrada"})

    client.set_payload.assert_called_once()
    kwargs = client.set_payload.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["payload"] == {"status_code": "cerrada"}
    assert kwargs["points"] == [str(tender_id)]
    client.upsert.assert_not_called()


@pytest.mark.anyio
async def test_set_payload_comprueba_la_existencia_sin_traer_vectores(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    tender_id = uuid4()
    client.retrieve.return_value = [_record_existente(tender_id)]

    await repository.set_payload(tender_id, {"status_code": "cerrada"})

    kwargs = client.retrieve.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["ids"] == [str(tender_id)]
    assert kwargs["with_vectors"] is False
    assert kwargs["with_payload"] is False


@pytest.mark.anyio
async def test_set_payload_no_hace_nada_si_el_punto_no_existe(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    """Una licitación ingestada antes de existir "tender_items" y aún sin backfill
    no tiene punto de partidas: el cambio de metadatos no puede fallar por eso ni
    crear un punto sin vectores."""
    client.retrieve.return_value = []

    await repository.set_payload(uuid4(), {"status_code": "cerrada"})

    client.set_payload.assert_not_called()
    client.upsert.assert_not_called()


def _respuesta_de_busqueda(*pares: tuple[UUID, float]) -> MagicMock:
    response = MagicMock()
    puntos = []
    for tender_id, score in pares:
        punto = MagicMock()
        punto.id = str(tender_id)
        punto.score = score
        puntos.append(punto)
    response.points = puntos
    return response


@pytest.mark.anyio
async def test_search_by_keywords_consulta_con_el_multivector_de_keywords(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    """El multivector de consulta contra el multivector 'items' (MAX_SIM) da
    Σ_keywords max_partidas coseno: el calce de cada keyword con su mejor partida."""
    t1, t2 = uuid4(), uuid4()
    client.query_points.return_value = _respuesta_de_busqueda((t1, 1.8), (t2, 0.9))
    keywords = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]

    resultados = await repository.search_by_keywords(keywords, limit=50)

    client.query_points.assert_called_once()
    kwargs = client.query_points.call_args.kwargs
    assert kwargs["collection_name"] == COLLECTION
    assert kwargs["query"] == keywords
    assert kwargs["using"] == VECTOR_NAME
    assert kwargs["limit"] == 50
    assert kwargs["with_payload"] is False
    assert kwargs["query_filter"] is None
    assert resultados == [(t1, 1.8), (t2, 0.9)]
    assert all(isinstance(tid, UUID) for tid, _ in resultados)


@pytest.mark.anyio
async def test_search_by_keywords_pre_filtra_con_los_criterios(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    """El filtro viaja DENTRO de la consulta: filtrar después del top-K devolvería
    casi nada cuando el filtro es específico."""
    client.query_points.return_value = _respuesta_de_busqueda()
    desde = datetime(2026, 8, 1)

    await repository.search_by_keywords(
        [[1.0, 0.0, 0.0, 0.0]],
        limit=10,
        criteria=TenderFilterCriteria(
            status_codes=["publicada"], region_ids=[13], closing_from=desde
        ),
    )

    filtro = client.query_points.call_args.kwargs["query_filter"]
    condiciones = {c.key: c for c in filtro.must}
    assert condiciones["status_code"].match.any == ["publicada"]
    assert condiciones["region_id"].match.any == [13]
    assert condiciones["closing_at"].range.gte == to_utc_epoch(desde)


@pytest.mark.anyio
async def test_search_by_keywords_sin_keywords_no_consulta_qdrant(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    """Qdrant rechaza un multivector de consulta vacío."""
    resultados = await repository.search_by_keywords([], limit=10)

    assert resultados == []
    client.query_points.assert_not_called()


@pytest.mark.anyio
async def test_search_by_keywords_rechaza_ids_que_no_son_uuid_en_string(
    repository: QdrantTenderItemVectorRepository, client: AsyncMock
) -> None:
    punto = MagicMock()
    punto.id = 42
    punto.score = 1.0
    respuesta = MagicMock()
    respuesta.points = [punto]
    client.query_points.return_value = respuesta

    with pytest.raises(ValueError, match="ID de punto inesperado"):
        await repository.search_by_keywords([[1.0, 0.0, 0.0, 0.0]], limit=10)
