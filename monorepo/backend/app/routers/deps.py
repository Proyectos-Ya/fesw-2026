from functools import lru_cache

import httpx
from qdrant_client import AsyncQdrantClient

from app.config import settings
from app.infrastructure.services.bge_m3_embedding_service import BgeM3EmbeddingService
from app.infrastructure.services.mercado_publico_client import MercadoPublicoClient
from app.infrastructure.services.qdrant_vector_store import QdrantVectorStore


@lru_cache(maxsize=1)
def get_embedding_service() -> BgeM3EmbeddingService:
    return BgeM3EmbeddingService(model_name=settings.embedding_model)


@lru_cache(maxsize=1)
def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size,
    )


@lru_cache(maxsize=1)
def get_mercado_publico_client() -> MercadoPublicoClient:
    return MercadoPublicoClient(
        api_key=settings.mercado_publico_ticket,
        http_client=httpx.AsyncClient(),
    )
