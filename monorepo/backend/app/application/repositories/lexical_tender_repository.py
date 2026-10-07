"""Repositorio de vectores dispersos (sparse BM25) para licitaciones (Plan 256, Fase 1)."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.lexical_tokenizer import SparseTermVector


class ILexicalTenderRepository(ABC):
    """Interfaz abstracta para el repositorio de vectores léxicos dispersos (BM25).

    Guarda, por licitación, un vector disperso nombrado 'lexical' sobre el texto de la licitación
    (título + descripción + partidas). Permite recuperar candidatos por coincidencia exacta
    de términos técnicos, modelos o marcas (tercer canal de recuperación).

    Cada punto lleva el mismo payload que 'tenders' (estado, región, etc.) para aplicar
    pre-filtrado estricto dentro del motor.
    """

    @abstractmethod
    async def upsert(
        self,
        tender_id: UUID,
        sparse_vector: SparseTermVector,
        payload: dict | None = None,
    ) -> None:
        """Inserta o reemplaza el vector léxico disperso de una licitación y su payload."""
        ...

    @abstractmethod
    async def set_payload(self, tender_id: UUID, payload: dict) -> None:
        """Actualiza campos del payload sin tocar el vector disperso."""
        ...

    @abstractmethod
    async def delete(self, tender_id: UUID) -> None:
        """Elimina el vector léxico disperso de una licitación."""
        ...

    @abstractmethod
    async def search_lexical(
        self,
        query_vector: SparseTermVector,
        limit: int,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:
        """Busca licitaciones por coincidencia léxica sparse (BM25 con IDF del lado servidor).

        Devuelve tuplas (tender_id, puntaje) ordenadas por puntaje descendente.
        """
        ...
