"""Implementación de ILexicalTenderRepository usando Qdrant con vectores dispersos (Plan 256, Fase 1)."""

from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Modifier,
    PointIdsList,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
)

from app.application.repositories.lexical_tender_repository import (
    ILexicalTenderRepository,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.lexical_tokenizer import SparseTermVector
from app.infrastructure.repositories.qdrant_tender_filters import (
    build_filter,
    ensure_payload_indexes,
)


class QdrantLexicalTenderRepository(ILexicalTenderRepository):
    """Repositorio de vectores léxicos dispersos (BM25) en Qdrant.

    Almacena vectores dispersos con cálculo de IDF en el servidor (Modifier.IDF).
    Vive en su propia colección 'tender_lexical' con los mismos índices de payload
    que 'tenders' (estado, región) para aislamiento y pre-filtrado estricto.
    """

    _COLLECTION_NAME = "tender_lexical"
    _VECTOR_NAME = "lexical"

    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def ensure_collection(self) -> None:
        """Crea la colección si no existe con sparse_vectors_config e índices de payload."""
        result = await self._client.get_collections()
        existing = {c.name for c in result.collections}
        if self._COLLECTION_NAME not in existing:
            await self._client.create_collection(
                collection_name=self._COLLECTION_NAME,
                vectors_config={},
                sparse_vectors_config={
                    self._VECTOR_NAME: SparseVectorParams(
                        modifier=Modifier.IDF,
                        index=SparseIndexParams(on_disk=False),
                    )
                },
            )

        await ensure_payload_indexes(self._client, self._COLLECTION_NAME)

    async def upsert(
        self,
        tender_id: UUID,
        sparse_vector: SparseTermVector,
        payload: dict | None = None,
    ) -> None:
        """Inserta o reemplaza el vector léxico disperso de una licitación."""
        if not sparse_vector.indices:
            await self.delete(tender_id)
            return

        point = PointStruct(
            id=str(tender_id),
            vector={
                self._VECTOR_NAME: SparseVector(
                    indices=sparse_vector.indices,
                    values=sparse_vector.values,
                )
            },
            payload=payload,
        )
        await self._client.upsert(
            collection_name=self._COLLECTION_NAME,
            points=[point],
        )

    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        """Actualiza campos del payload sin tocar el vector disperso."""
        existentes = await self._client.retrieve(
            collection_name=self._COLLECTION_NAME,
            ids=[str(tender_id)],
            with_vectors=False,
            with_payload=False,
        )
        if not existentes:
            return

        await self._client.set_payload(
            collection_name=self._COLLECTION_NAME,
            payload=payload,
            points=[str(tender_id)],
        )

    async def delete(self, tender_id: UUID) -> None:
        """Elimina el punto correspondiente a la licitación en Qdrant."""
        await self._client.delete(
            collection_name=self._COLLECTION_NAME,
            points_selector=PointIdsList(points=[str(tender_id)]),
        )

    async def search_lexical(
        self,
        query_vector: SparseTermVector,
        limit: int,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        """Busca licitaciones por coincidencia léxica sparse."""
        if not query_vector.indices:
            return []

        response = await self._client.query_points(
            collection_name=self._COLLECTION_NAME,
            query=SparseVector(
                indices=query_vector.indices,
                values=query_vector.values,
            ),
            using=self._VECTOR_NAME,
            query_filter=build_filter(criteria),
            limit=limit,
            with_payload=False,
        )
        return [
            (self._as_uuid(point.id), point.score) for point in response.points
        ]

    @staticmethod
    def _as_uuid(point_id: object) -> UUID:
        if not isinstance(point_id, str):
            raise ValueError(f"ID de punto inesperado: {point_id!r}")
        return UUID(point_id)
