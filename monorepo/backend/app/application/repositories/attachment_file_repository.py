from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.domain.entities.attachment_file import AttachmentFile


class IAttachmentFileRepository(ABC):
    """Archivos subidos para los anexos oficiales y el cupo mensual de cada empresa.

    Interfaz aparte de `ITenderAttachmentRepository`: aquella es la lista que
    publica Mercado Público (la escribe la ingesta); esta es lo que sube cada
    empresa, con reglas de privacidad y de cupo que la otra no tiene.
    """

    @abstractmethod
    async def get(self, file_id: UUID) -> AttachmentFile | None:
        """La fila con ese id, sin filtrar por empresa: el caso de uso decide la visibilidad."""
        ...

    @abstractmethod
    async def find_for_workspace(
        self, *, tender_attachment_id: UUID, sha256: str, workspace_id: UUID
    ) -> AttachmentFile | None:
        """La fila de la empresa para ese anexo y ese contenido (la clave única)."""
        ...

    @abstractmethod
    async def find_shared_stored(
        self, *, tender_attachment_id: UUID, sha256: str
    ) -> AttachmentFile | None:
        """Un archivo compartido y guardado con ese contenido, de cualquier empresa.

        Camino de la decisión 6: hoy ningún archivo es compartido, así que nunca
        encuentra nada. Nunca devuelve uno privado: no hay forma de saber si otra
        empresa subió un contenido.
        """
        ...

    @abstractmethod
    async def find_stored_by_storage_key(self, storage_key: str) -> AttachmentFile | None:
        """Una fila `stored` o `unsupported` que ya usa ese objeto (verificado)."""
        ...

    @abstractmethod
    async def list_for_workspace_attachment(
        self, *, tender_attachment_id: UUID, workspace_id: UUID
    ) -> list[AttachmentFile]:
        """Todas las filas de la empresa para ese anexo, en cualquier estado."""
        ...

    @abstractmethod
    async def list_visible_for_tender(
        self, *, tender_id: UUID, workspace_id: UUID | None
    ) -> list[AttachmentFile]:
        """Las filas no purgadas que esta empresa puede ver: las propias y las compartidas.

        Sin empresa, solo las compartidas.
        """
        ...

    @abstractmethod
    async def create(self, file: AttachmentFile) -> AttachmentFile:
        """Inserta sin tocar el cupo. `ConcurrentUploadConflict` si choca la clave única."""
        ...

    @abstractmethod
    async def create_consuming_quota(
        self, file: AttachmentFile, *, month: date, limit: int
    ) -> AttachmentFile:
        """Inserta la fila y suma 1 al cupo del mes **en la misma transacción**.

        Atómico: dos subidas simultáneas no pueden pasarse del tope. Lanza
        `UploadQuotaExceeded` si el cupo del mes ya llegó a `limit`, y
        `ConcurrentUploadConflict` (sin cobrar) si choca la clave única.
        """
        ...

    @abstractmethod
    async def update(self, file: AttachmentFile) -> AttachmentFile: ...

    @abstractmethod
    async def delete(self, file_id: UUID) -> None: ...

    @abstractmethod
    async def count_other_references(self, *, storage_key: str, excluding_id: UUID) -> int:
        """Cuántas otras filas no purgadas usan el mismo objeto.

        Se mira antes de borrar un objeto: dos anexos de la misma empresa con el
        mismo contenido comparten la clave, y borrar uno no puede romper el otro.
        """
        ...

    @abstractmethod
    async def get_quota_used(self, *, workspace_id: UUID, month: date) -> int: ...
