from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.supplier import Supplier


class ISupplierRepository(ABC):
    @abstractmethod
    async def get_by_rut(self, rut: str) -> Supplier | None: ...

    @abstractmethod
    async def get_by_id(self, supplier_id: UUID) -> Supplier | None: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> Supplier | None: ...

    @abstractmethod
    async def list_user_ids_with_profile(self) -> list[UUID]: ...

    @abstractmethod
    async def save(self, supplier: Supplier) -> Supplier:
        """Persiste y confirma en un solo paso (`add` + `commit`)."""

    @abstractmethod
    async def update(self, supplier: Supplier) -> Supplier:
        """Actualiza y confirma en un solo paso (`stage_update` + `commit`)."""

    # --- Unidad de trabajo ---
    #
    # Para escribir en Postgres y en Qdrant como una sola operación: se deja la
    # fila pendiente, se escribe el vector, y recién entonces se confirma. Si
    # Qdrant falla, `rollback` descarta la fila y no queda una empresa sin vector.

    @abstractmethod
    async def add(self, supplier: Supplier) -> Supplier:
        """Deja el proveedor pendiente en la transacción, sin confirmarlo.

        Las restricciones de unicidad se evalúan acá, así que un duplicado se
        detecta antes de tocar el almacén vectorial.
        """

    @abstractmethod
    async def stage_update(self, supplier: Supplier) -> Supplier:
        """Deja la actualización pendiente en la transacción, sin confirmarla."""

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
