from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)


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

    async def search_by_supplier_vector(
        self,
        supplier_vector: list[float],
        limit: int,
        filters: dict | None = None,
    ) -> list[tuple[UUID, float]]:
        """
        Busca las licitaciones más similares al vector de perfil del proveedor,
        buscando en el vector nombrado 'tender' y aplicando los filtros indicados.
        """
        query_filter = self._build_filter(filters)

        # qdrant-client >= 1.15 eliminó `search`; `query_points` es la API vigente
        response = await self._client.query_points(
            collection_name=self._COLLECTION_NAME,
            query=supplier_vector,
            using=self._VECTOR_NAME,
            query_filter=query_filter,
            limit=limit,
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

    def _build_filter(self, filters: dict | None) -> Filter | None:
        """
        Construye el objeto Filter de Qdrant a partir de un diccionario de filtros de metadatos.
        """
        if not filters:
            return None

        conditions = []

        # Atributos de filtro del payload:
        # code (str), region_id (int), available_amount_clp (float), status_code (str)
        if "code" in filters and filters["code"] is not None:
            conditions.append(
                FieldCondition(key="code", match=MatchValue(value=filters["code"]))
            )
        if "region_id" in filters and filters["region_id"] is not None:
            conditions.append(
                FieldCondition(
                    key="region_id", match=MatchValue(value=filters["region_id"])
                )
            )
        if (
            "available_amount_clp" in filters
            and filters["available_amount_clp"] is not None
        ):
            conditions.append(
                FieldCondition(
                    key="available_amount_clp",
                    match=MatchValue(value=filters["available_amount_clp"]),
                )
            )
        if "status_code" in filters and filters["status_code"] is not None:
            conditions.append(
                FieldCondition(
                    key="status_code", match=MatchValue(value=filters["status_code"])
                )
            )

        return Filter(must=conditions) if conditions else None
