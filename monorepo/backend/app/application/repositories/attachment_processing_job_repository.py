"""Puerto para la cola de procesamiento de anexos (plan 233, decisión 4)."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.domain.entities.attachment_processing import (
    AttachmentProcessingJob,
    ProcessingJobKind,
)


class IAttachmentProcessingJobRepository(ABC):
    @abstractmethod
    async def enqueue_extract(
        self,
        *,
        attachment_file_id: UUID,
        tender_id: UUID,
        priority: int,
        now: datetime,
    ) -> bool:
        """False si ya había uno pendiente para ese archivo (ON CONFLICT DO NOTHING)."""
        ...

    @abstractmethod
    async def enqueue_digest(
        self,
        *,
        tender_id: UUID,
        workspace_id: UUID | None,
        priority: int,
        now: datetime,
    ) -> bool:
        """False si ya había uno pendiente para esa licitación y alcance."""
        ...

    @abstractmethod
    async def claim_next(
        self, *, now: datetime, kinds: Sequence[ProcessingJobKind]
    ) -> AttachmentProcessingJob | None:
        """Toma el siguiente trabajo elegible.

        Busca pending con not_before <= now en orden de prioridad DESC,
        not_before ASC, created_at ASC. Lo pasa a running, attempts + 1 y
        locked_at = now.
        """
        ...

    @abstractmethod
    async def complete(self, job_id: UUID, *, now: datetime) -> None:
        ...

    @abstractmethod
    async def retry(
        self, job_id: UUID, *, not_before: datetime, error: str, now: datetime
    ) -> None:
        ...

    @abstractmethod
    async def defer(
        self, job_id: UUID, *, not_before: datetime, reason: str, now: datetime
    ) -> None:
        """Difiere el trabajo devolviendo el intento gastado al reclamarlo."""
        ...

    @abstractmethod
    async def fail(self, job_id: UUID, *, error: str, now: datetime) -> None:
        ...

    @abstractmethod
    async def recover_stale(self, *, locked_before: datetime, now: datetime) -> int:
        ...

    @abstractmethod
    async def files_missing_extraction(
        self, *, prompt_version: str, limit: int
    ) -> list[tuple[UUID, UUID]]:
        """Archivos `stored` sin extracción para la versión dada ni trabajo pendiente/en curso."""
        ...

    @abstractmethod
    async def purge_finished(self, *, before: datetime) -> int:
        ...
