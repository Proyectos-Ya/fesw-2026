from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class IMilestoneAttachmentRepository(ABC):
    """Qué anexos ya pasaron por la extracción de hitos de cada usuario (plan 233).

    Igual que con las bases del asistente, cada anexo se lee una sola vez por
    usuario: volver a enviarlo a la IA daba títulos o fechas un poco distintos.
    Al borrar el archivo, su registro se va con él.
    """

    @abstractmethod
    async def list_processed(self, user_id: UUID, tender_id: UUID) -> set[UUID]:
        """Ids de los archivos de anexo ya leídos para el usuario en la licitación."""

    @abstractmethod
    async def mark_processed(
        self,
        user_id: UUID,
        tender_id: UUID,
        attachment_file_id: UUID,
        milestones_found: int,
        now: datetime,
    ) -> None: ...
