from abc import ABC, abstractmethod


class IEmbeddingService(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
