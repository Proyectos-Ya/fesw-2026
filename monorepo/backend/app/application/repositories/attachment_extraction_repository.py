"""Puerto para el repositorio de extracciones de anexos (plan 233, decisión 4)."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.attachment_extraction import (
    AttachmentExtraction,
    FuenteDeExtraccion,
)


class IAttachmentExtractionRepository(ABC):
    @abstractmethod
    async def get_for_file(
        self, attachment_file_id: UUID, *, prompt_version: str
    ) -> AttachmentExtraction | None:
        """Extracción para un archivo específico y versión de prompt."""
        ...

    @abstractmethod
    async def find_reusable(
        self,
        *,
        tender_attachment_id: UUID,
        sha256: str,
        prompt_version: str,
        excluding_file_id: UUID,
    ) -> AttachmentExtraction | None:
        """Busca una extracción previa para el mismo anexo oficial y mismo hash SHA-256."""
        ...

    @abstractmethod
    async def create(
        self, extraction: AttachmentExtraction
    ) -> AttachmentExtraction:
        """Inserta una extracción. Lanza ExtractionAlreadyExists si ya existe para ese archivo y prompt."""
        ...

    @abstractmethod
    async def list_sources(
        self,
        *,
        tender_id: UUID,
        workspace_id: UUID | None,
        prompt_version: str,
    ) -> list[FuenteDeExtraccion]:
        """Archivos `stored` de anexos vigentes: compartidos (trust distinto de conflict/rejected)
        y, si hay workspace, los privados de ESA empresa. Nunca los privados de otra empresa.
        """
        ...
