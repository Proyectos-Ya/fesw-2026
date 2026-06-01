from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.proveedor_repository import IProveedorRepository
from app.domain.entities.proveedor import Proveedor
from app.domain.errors.proveedor_errors import ProveedorNoEncontrado
from app.infrastructure.repositories.proveedor_model import ProveedorModel


class ProveedorRepository(IProveedorRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: ProveedorModel) -> Proveedor:
        return Proveedor(**model.model_dump())

    def _to_model(self, entity: Proveedor) -> ProveedorModel:
        return ProveedorModel(**entity.model_dump())

    async def get_by_id(self, proveedor_id: UUID) -> Proveedor | None:
        model = await self.session.get(ProveedorModel, proveedor_id)
        return self._to_entity(model) if model else None

    async def get_by_rut(self, rut: str) -> Proveedor | None:
        result = await self.session.exec(
            select(ProveedorModel).where(ProveedorModel.rut == rut)
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def save(self, proveedor: Proveedor) -> Proveedor:
        model = self._to_model(proveedor)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update(self, proveedor: Proveedor) -> Proveedor:
        model = await self.session.get(ProveedorModel, proveedor.id)
        if model is None:
            raise ProveedorNoEncontrado(str(proveedor.id))
        for key, value in proveedor.model_dump(exclude={"id"}).items():
            setattr(model, key, value)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def delete(self, proveedor_id: UUID) -> None:
        model = await self.session.get(ProveedorModel, proveedor_id)
        await self.session.delete(model)
        await self.session.commit()