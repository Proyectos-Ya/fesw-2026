import asyncio

from sentence_transformers import SentenceTransformer

from app.application.services.embedding_service import IEmbeddingService


class BgeM3EmbeddingService(IEmbeddingService):
    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model = SentenceTransformer(model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(
            None,
            lambda: self._model.encode(texts, normalize_embeddings=True),
        )
        return vectors.tolist()
