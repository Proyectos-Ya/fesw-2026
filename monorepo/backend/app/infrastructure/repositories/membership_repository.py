from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.membership_repository import IMembershipRepository
from app.domain.entities.membership import MembershipStatus, SupplierMembership
from app.infrastructure.repositories.membership_model import MembershipModel


class MembershipRepository(IMembershipRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: MembershipModel) -> SupplierMembership:
        return SupplierMembership(**model.model_dump())

    def _to_model(self, entity: SupplierMembership) -> MembershipModel:
        data = entity.model_dump()
        # Los enums se persisten como su valor string
        data["role"] = entity.role.value
        data["status"] = entity.status.value
        return MembershipModel(**data)

    async def save(self, membership: SupplierMembership) -> SupplierMembership:
        # merge soporta tanto inserción como actualización (aprobar solicitud)
        model = await self.session.merge(self._to_model(membership))
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, membership_id: UUID) -> SupplierMembership | None:
        model = await self.session.get(MembershipModel, membership_id)
        return self._to_entity(model) if model else None

    async def get_by_user(self, user_id: UUID) -> SupplierMembership | None:
        result = await self.session.exec(
            select(MembershipModel).where(MembershipModel.user_id == user_id)
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def list_by_supplier(
        self, supplier_id: UUID, status: MembershipStatus | None = None
    ) -> list[SupplierMembership]:
        statement = select(MembershipModel).where(
            MembershipModel.supplier_id == supplier_id
        )
        if status is not None:
            statement = statement.where(MembershipModel.status == status.value)
        result = await self.session.exec(statement)
        return [self._to_entity(m) for m in result.all()]

    async def delete(self, membership_id: UUID) -> None:
        model = await self.session.get(MembershipModel, membership_id)
        if model is not None:
            await self.session.delete(model)
            await self.session.commit()
