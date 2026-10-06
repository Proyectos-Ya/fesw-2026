from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class IMilestoneDocumentRepository(ABC):
    """Qué bases ya pasaron por la extracción de hitos (HU-16, criterio 1).

    Cada documento se lee una sola vez: volver a enviarlo a la IA daba títulos o
    fechas un poco distintos y la tabla terminaba con hitos duplicados o
    perdidos. Al borrar el documento, su registro se va con él.
    """

    @abstractmethod
    async def list_processed(self, user_id: UUID, tender_id: UUID) -> set[UUID]:
        """Ids de los documentos del usuario ya procesados para la licitación."""

    @abstractmethod
    async def mark_processed(
        self,
        user_id: UUID,
        tender_id: UUID,
        document_id: UUID,
        milestones_found: int,
        now: datetime,
    ) -> None: ...
