"""Puerto de lectura de estados de procesamiento de anexos (plan 233, decisión 4)."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.domain.entities.attachment_processing import EstadoDeExtraccion


class IAttachmentProcessingStatusReader(ABC):
    @abstractmethod
    async def extraction_states(
        self, file_ids: Sequence[UUID], *, prompt_version: str
    ) -> dict[UUID, EstadoDeExtraccion]:
        """Estado de extracción para un lote de archivos subidos."""
        ...

    @abstractmethod
    async def pending_count(
        self, *, tender_id: UUID, workspace_id: UUID | None, prompt_version: str
    ) -> int:
        """Cantidad de trabajos de extracción o resumen pendientes/en curso para esa licitación."""
        ...
