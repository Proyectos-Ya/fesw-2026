from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from app.domain.entities.tender_attachment import (
    OfficialAttachment,
    OfficialAttachmentList,
)
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO


class ITenderAttachmentRepository(ABC):
    """Lo que la lista oficial de anexos necesita de Postgres, y nada más.

    Interfaz aparte de `ITenderRepository` por el mismo motivo que
    `ITenderStatusSyncRepository`: esa ya es ancha, y cada método nuevo ahí
    obliga a tocar todos sus dobles de prueba.
    """

    @abstractmethod
    async def get_tender_ids_by_codes(self, codes: list[str]) -> dict[str, UUID]:
        """Ids de las licitaciones guardadas con esos códigos; las que no existen no aparecen."""
        ...

    @abstractmethod
    async def sync_official_lists(
        self, listas: Mapping[UUID, Sequence[DocumentoOficialDTO]], *, visto_en: datetime
    ) -> int:
        """Deja la lista oficial de cada licitación como viene en `listas`.

        Inserta los nuevos, actualiza nombre y `last_seen_at` de los que siguen,
        marca `removed_at` (sin borrar) los que ya no vienen y revive los que
        reaparecen. Idempotente. Marca `tender.attachments_synced_at = visto_en`
        sin tocar `tender.updated_at`. Devuelve cuántas licitaciones sincronizó.
        """
        ...

    @abstractmethod
    async def get_official_list(self, tender_id: UUID) -> OfficialAttachmentList | None:
        """La lista vigente, o `None` si la licitación no existe."""
        ...

    @abstractmethod
    async def get_official_attachment(
        self, tender_id: UUID, attachment_id: UUID
    ) -> OfficialAttachment | None:
        """Una fila oficial vigente de esa licitación.

        `None` si no existe, si es de otra licitación o si Mercado Público la
        retiró: la subida no debe colgar archivos de algo que ya no se publica.
        """
        ...
