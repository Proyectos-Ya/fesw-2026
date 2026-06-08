from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from app.application.services.vector_store_service import (
    FiltrosVectoriales,
    IVectorStoreService,
    VectorSearchResult,
)


class QdrantVectorStore(IVectorStoreService):

    def __init__(
        self,
        client: AsyncQdrantClient,
        collection_name: str,
        vector_size: int = 1024,
    ) -> None:
        self._client = client
        self._collection_name = collection_name
        self._vector_size = vector_size

    async def ensure_collection(self) -> None:
        result = await self._client.get_collections()
        existing = {c.name for c in result.collections}
        if self._collection_name not in existing:
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert(
        self,
        vector_id: UUID,
        vector: list[float],
        payload: dict[str, str | float | None],
    ) -> None:
        await self._client.upsert(
            collection_name=self._collection_name,
            points=[
                PointStruct(id=str(vector_id), vector=vector, payload=payload)
            ],
        )

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        filtros: FiltrosVectoriales | None = None,
    ) -> list[VectorSearchResult]:
        results = await self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=self._build_filter(filtros),
        )
        return [
            VectorSearchResult(
                licitacion_id=UUID(result.payload["licitacion_id"]),
                score=result.score,
            )
            for result in results
        ]

    def _build_filter(self, filtros: FiltrosVectoriales | None) -> Filter | None:
        if filtros is None:
            return None
        conditions = []
        if filtros.region is not None:
            conditions.append(
                FieldCondition(key="region", match=MatchValue(value=filtros.region))
            )
        if filtros.monto_min is not None:
            conditions.append(
                FieldCondition(
                    key="monto_estimado", range=Range(gte=filtros.monto_min)
                )
            )
        return Filter(must=conditions) if conditions else None
