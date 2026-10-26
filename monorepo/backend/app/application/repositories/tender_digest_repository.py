"""Puerto para el repositorio de resúmenes consolidados de licitaciones (plan 233, decisión 4)."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.tender_digest import TenderDigest


class ITenderDigestRepository(ABC):
    @abstractmethod
    async def get_current(
        self, tender_id: UUID, workspace_id: UUID | None
    ) -> TenderDigest | None:
        """El resumen vigente para la licitación y alcance (`None` = compartido)."""
        ...

    @abstractmethod
    async def replace_current(
        self, digest: TenderDigest, *, previous_id: UUID | None
    ) -> TenderDigest:
        """Reemplaza el resumen vigente en una transacción atómica.

        El anterior pasa a `is_current = False` y se inserta el nuevo con `is_current = True`.
        Si choca el índice único parcial por concurrencia, devuelve el vigente que ganó.
        """
        ...

    @abstractmethod
    async def retire_current(self, tender_id: UUID, workspace_id: UUID) -> None:
        """Pone `is_current = False` en el resumen privado vigente de esa empresa."""
        ...

    @abstractmethod
    async def workspaces_with_current(self, tender_id: UUID) -> list[UUID]:
        """Empresas que tienen un resumen privado vigente para esta licitación."""
        ...
