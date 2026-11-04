from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    HasIdCondition,
    MatchAny,
    PointIdsList,
    PointStruct,
    SetPayload,
    SetPayloadOperation,
    VectorParams,
)

from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.infrastructure.repositories.qdrant_tender_filters import (
    build_filter,
    ensure_payload_indexes,
)


class QdrantTenderRepository(ITenderVectorRepository):
    """
    Implementación del repositorio vectorial de licitaciones (tenders) usando Qdrant
    con soporte para vectores nombrados (named vectors).
    """

    _COLLECTION_NAME = "tenders"
    _VECTOR_NAME = "tender"

    # Ids por petición de borrado. La purga inicial puede traer cientos de
    # miles; en lotes, cada cuerpo de petición queda acotado.
    _DELETE_BATCH_SIZE = 1_000

    # Operaciones por petición en `set_payloads`. Cada una lleva su propio
    # payload, así que el cuerpo crece más rápido que en un borrado por ids.
    _SET_PAYLOAD_BATCH_SIZE = 100

    def __init__(
        self,
        client: AsyncQdrantClient,
        vector_size: int = 1024,
    ) -> None:
        self._client = client
        self._vector_size = vector_size

    async def ensure_collection(self) -> None:
        """
        Crea la colección en Qdrant si no existe, configurando un vector nombrado 'tender',
        y asegura los índices de payload de los campos por los que se filtra.
        """
        result = await self._client.get_collections()
        existing = {c.name for c in result.collections}
        if self._COLLECTION_NAME not in existing:
            await self._client.create_collection(
                collection_name=self._COLLECTION_NAME,
                vectors_config={
                    self._VECTOR_NAME: VectorParams(
                        size=self._vector_size,
                        distance=Distance.COSINE,
                    )
                },
            )

        # Fuera del `if` a propósito: la colección ya existe en todos los entornos
        # actuales, así que crear los índices solo al crearla significaría que
        # nadie los tendría nunca sin borrar y reindexar. Qdrant los trata de
        # forma idempotente.
        await ensure_payload_indexes(self._client, self._COLLECTION_NAME)

    async def upsert(
        self,
        tender_id: UUID,
        embedding: list[float],
        payload: dict,
    ) -> None:
        """
        Inserta o actualiza una licitación en Qdrant utilizando el vector nombrado.
        """
        point = PointStruct(
            id=str(tender_id),
            vector={self._VECTOR_NAME: embedding},
            payload=payload,
        )
        await self._client.upsert(
            collection_name=self._COLLECTION_NAME,
            points=[point],
        )

    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        """
        Actualiza campos del payload de una licitación sin tocar su vector.

        `set_payload` y no `upsert`: el upsert exige el vector completo, así que
        para cambiar un estado habría que recalcular el embedding o leer el
        punto entero primero. Qdrant hace la fusión de claves de su lado.
        """
        await self._client.set_payload(
            collection_name=self._COLLECTION_NAME,
            payload=payload,
            points=[str(tender_id)],
        )

    async def set_payloads(self, payloads: dict[UUID, dict]) -> None:
        """Un `batch_update_points` por lote, en vez de un viaje por punto.

        Cada punto recibe su propio payload (el cierre es distinto en cada
        licitación), así que no sirve un único `set_payload` con varios ids.

        Cada operación apunta por **filtro de id** y no por id. Por id, un punto
        inexistente hace que Qdrant responda 404 y corte el lote a la mitad
        (verificado contra 1.17.1); una licitación activa sin punto —una
        escritura a medias— botaría la corrida entera. Por filtro, simplemente
        no calza, y no se crea un punto sin vector.
        """
        items = list(payloads.items())
        for i in range(0, len(items), self._SET_PAYLOAD_BATCH_SIZE):
            lote = items[i : i + self._SET_PAYLOAD_BATCH_SIZE]
            await self._client.batch_update_points(
                collection_name=self._COLLECTION_NAME,
                update_operations=[
                    SetPayloadOperation(
                        set_payload=SetPayload(
                            payload=payload,
                            filter=Filter(
                                must=[HasIdCondition(has_id=[str(tender_id)])]
                            ),
                        )
                    )
                    for tender_id, payload in lote
                ],
            )

    async def delete(self, tender_id: UUID) -> None:
        """
        Elimina el punto correspondiente a la licitación en Qdrant.
        """
        await self._client.delete(
            collection_name=self._COLLECTION_NAME,
            points_selector=PointIdsList(points=[str(tender_id)]),
        )

    async def delete_many(self, tender_ids: list[UUID]) -> None:
        """Elimina los puntos en lotes de `_DELETE_BATCH_SIZE`."""
        for i in range(0, len(tender_ids), self._DELETE_BATCH_SIZE):
            lote = tender_ids[i : i + self._DELETE_BATCH_SIZE]
            await self._client.delete(
                collection_name=self._COLLECTION_NAME,
                points_selector=PointIdsList(points=[str(t) for t in lote]),
            )

    async def delete_by_status_not_in(self, status_codes: set[str]) -> None:
        """Borra por filtro en el servidor: todo lo que no tenga esos estados."""
        await self._client.delete(
            collection_name=self._COLLECTION_NAME,
            points_selector=FilterSelector(
                filter=Filter(
                    must_not=[
                        FieldCondition(
                            key="status_code",
                            match=MatchAny(any=sorted(status_codes)),
                        )
                    ]
                )
            ),
        )

    async def search_by_vector(
        self,
        vector: list[float],
        limit: int,
        offset: int = 0,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        """
        Busca las licitaciones más afines al vector, con los criterios aplicados
        como pre-filtro durante el recorrido del grafo.
        """
        # qdrant-client >= 1.15 eliminó `search`; `query_points` es la API vigente
        response = await self._client.query_points(
            collection_name=self._COLLECTION_NAME,
            query=vector,
            using=self._VECTOR_NAME,
            query_filter=build_filter(criteria),
            limit=limit,
            offset=offset,
        )

        # Los puntos se insertan siempre con `str(uuid)`; un id entero indicaría
        # datos escritos por otra ruta y no es representable como UUID.
        results: list[tuple[UUID, float]] = []
        for result in response.points:
            if not isinstance(result.id, str):
                raise ValueError(
                    f"ID de punto inesperado en Qdrant: {result.id!r}. "
                    f"Se esperaba un UUID en formato string."
                )
            results.append((UUID(result.id), result.score))
        return results

    async def count(self, criteria: TenderFilterCriteria | None = None) -> int:
        """Total de licitaciones que pasan los criterios, sin mirar similitud."""
        # `exact=True` porque este número se le muestra al usuario como "N
        # coincidencias"; la estimación aproximada de Qdrant serviría para
        # planificar una consulta, no para informar.
        response = await self._client.count(
            collection_name=self._COLLECTION_NAME,
            count_filter=build_filter(criteria),
            exact=True,
        )
        return response.count
