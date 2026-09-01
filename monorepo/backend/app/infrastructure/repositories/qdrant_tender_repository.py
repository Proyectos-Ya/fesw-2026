from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Condition,
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointIdsList,
    PointStruct,
    Range,
    VectorParams,
)

from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.shared.datetime_utils import to_utc_epoch


class QdrantTenderRepository(ITenderVectorRepository):
    """
    Implementación del repositorio vectorial de licitaciones (tenders) usando Qdrant
    con soporte para vectores nombrados (named vectors).
    """

    _COLLECTION_NAME = "tenders"
    _VECTOR_NAME = "tender"

    # Campos del payload por los que se pre-filtra, con el tipo que Qdrant usa
    # para indexarlos. El tipo importa: un rango sobre un campo indexado como
    # `keyword` no compara como número.
    _PAYLOAD_INDEXES: dict[str, str] = {
        "status_code": "keyword",
        "region_id": "integer",
        "provincia_id": "integer",
        "comuna_id": "integer",
        "available_amount_clp": "float",
        "closing_at": "integer",
        "published_at": "integer",
    }

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
        for field_name, field_schema in self._PAYLOAD_INDEXES.items():
            await self._client.create_payload_index(
                collection_name=self._COLLECTION_NAME,
                field_name=field_name,
                field_schema=field_schema,  # type: ignore[arg-type]
            )

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

    async def delete(self, tender_id: UUID) -> None:
        """
        Elimina el punto correspondiente a la licitación en Qdrant.
        """
        await self._client.delete(
            collection_name=self._COLLECTION_NAME,
            points_selector=PointIdsList(points=[str(tender_id)]),
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
            query_filter=self._build_filter(criteria),
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
            count_filter=self._build_filter(criteria),
            exact=True,
        )
        return response.count

    def _build_filter(self, criteria: TenderFilterCriteria | None) -> Filter | None:
        """Traduce el criterio de la capa de aplicación al `Filter` de Qdrant.

        Es el único punto donde el vocabulario de negocio se convierte en tipos
        de Qdrant, y donde las fechas pasan a epoch.
        """
        if criteria is None:
            return None

        # `Condition` y no `FieldCondition`: `Filter.must` es invariante en el
        # tipo del elemento y no acepta la lista del subtipo.
        conditions: list[Condition] = []

        # Listas -> MatchAny. `MatchValue` compara contra un único valor, así que
        # no sirve para "estado publicada o cerrada".
        if criteria.status_codes:
            conditions.append(
                FieldCondition(
                    key="status_code", match=MatchAny(any=list(criteria.status_codes))
                )
            )
        if criteria.region_ids:
            conditions.append(
                FieldCondition(
                    key="region_id", match=MatchAny(any=list(criteria.region_ids))
                )
            )
        # `MatchValue`, no `MatchAny`: a diferencia de región, provincia/comuna
        # son un solo valor (el frontend las selecciona de a una, en cascada).
        if criteria.province_id is not None:
            conditions.append(
                FieldCondition(
                    key="provincia_id", match=MatchValue(value=criteria.province_id)
                )
            )
        if criteria.commune_id is not None:
            conditions.append(
                FieldCondition(
                    key="comuna_id", match=MatchValue(value=criteria.commune_id)
                )
            )

        # Rangos. `gte`/`lte` mantienen ambos extremos inclusivos, igual que el
        # filtro de presupuesto del frontend.
        rangos = (
            ("closing_at", criteria.closing_from, criteria.closing_to),
            ("published_at", criteria.published_from, criteria.published_to),
        )
        for key, desde, hasta in rangos:
            if desde is None and hasta is None:
                continue
            conditions.append(
                FieldCondition(
                    key=key,
                    range=Range(
                        gte=to_utc_epoch(desde) if desde else None,
                        lte=to_utc_epoch(hasta) if hasta else None,
                    ),
                )
            )

        if criteria.min_amount is not None or criteria.max_amount is not None:
            conditions.append(
                FieldCondition(
                    key="available_amount_clp",
                    range=Range(gte=criteria.min_amount, lte=criteria.max_amount),
                )
            )

        # `Filter(must=[])` en Qdrant no equivale a "sin filtro": devolver None
        # es lo que deja la búsqueda sin restricciones.
        return Filter(must=conditions) if conditions else None
