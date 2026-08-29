from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.infrastructure.repositories.supplier_model import SupplierModel


class SupplierRepository(ISupplierRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: SupplierModel) -> Supplier:
        # Convierte el modelo de BD a entidad de dominio
        return Supplier(**model.model_dump())

    def _to_model(self, entity: Supplier) -> SupplierModel:
        # Convierte la entidad de dominio a modelo de BD
        return SupplierModel(**entity.model_dump())

    async def get_by_rut(self, rut: str) -> Supplier | None:
        # Busca un proveedor por RUT para verificar duplicados
        result = await self.session.exec(
            select(SupplierModel).where(SupplierModel.rut == rut)
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def get_by_id(self, supplier_id: UUID) -> Supplier | None:
        # Busca un proveedor por su id interno
        model = await self.session.get(SupplierModel, supplier_id)
        return self._to_entity(model) if model else None

    async def get_by_user_id(self, user_id: UUID) -> Supplier | None:
        # Busca un proveedor por el id del usuario propietario
        result = await self.session.exec(
            select(SupplierModel).where(SupplierModel.user_id == user_id)
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def list_user_ids_with_profile(self) -> list[UUID]:
        # Usuarios que ya tienen un perfil de empresa. Lo usa el escaneo de
        # alertas: sin perfil no hay vector y el matching no tiene qué comparar.
        result = await self.session.exec(
            select(SupplierModel.user_id).where(col(SupplierModel.user_id).is_not(None))
        )
        return [user_id for user_id in result.all() if user_id is not None]

    async def save(self, supplier: Supplier) -> Supplier:
        # Persiste el proveedor en la base de datos
        model = self._to_model(supplier)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update(self, supplier: Supplier) -> Supplier:
        # Actualiza un proveedor existente (merge por primary key)
        model = await self.session.merge(self._to_model(supplier))
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)
