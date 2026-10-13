"""Puerto de la promoción de anexos compartidos (plan 233, decisión 6)."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.attachment_file import AttachmentFile
from app.domain.entities.tender_attachment import OfficialAttachment


@dataclass(frozen=True)
class TrustSnapshot:
    """Lo que hace falta para decidir qué se comparte de un anexo, ya bloqueado."""

    attachment: OfficialAttachment  # incluye `removed_at`
    files: list[AttachmentFile]  # filas no purgadas del anexo: aportes y canónicas
    people: dict[UUID, frozenset[UUID]]  # empresa -> dueño legado y membresías (cualquier estado)


class IAttachmentTrustRepository(ABC):
    """Lo que la promoción necesita de Postgres: leer un anexo bloqueado y escribir el resultado.

    Contrato transaccional: `lock_for_promotion` abre la transacción y toma el
    candado; la cierra `save_promotion` (commit) o `release` (rollback). No hay
    commits entre medio: el candado es lo que serializa dos promociones del mismo
    anexo.
    """

    @abstractmethod
    async def lock_for_promotion(self, tender_attachment_id: UUID) -> TrustSnapshot | None:
        """Bloquea el anexo y lee sus archivos y las personas de cada empresa.

        `None` si el anexo no existe. Deja la transacción abierta en ambos casos.
        """
        ...

    @abstractmethod
    async def save_promotion(
        self, *, updated: Sequence[AttachmentFile], created: Sequence[AttachmentFile]
    ) -> None:
        """De `updated` escribe solo `trust` y `visibility`. Inserta `created`. Hace commit."""
        ...

    @abstractmethod
    async def release(self) -> None:
        """Rollback: suelta el candado sin cambios."""
        ...
