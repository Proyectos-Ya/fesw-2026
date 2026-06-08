from sqlmodel import select
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

    async def save(self, supplier: Supplier) -> Supplier:
        # Persiste el proveedor en la base de datos
        model = self._to_model(supplier)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)