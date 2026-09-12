from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
    UserWorkspaceSummary,
)
from app.infrastructure.repositories.supplier_member_model import (
    SupplierMemberModel,
)
from app.infrastructure.repositories.supplier_model import SupplierModel


def _to_entity(model: SupplierMemberModel) -> SupplierMember:
    return SupplierMember(
        id=model.id,
        user_id=model.user_id,
        supplier_id=model.supplier_id,
        role=MemberRole(model.role),
        status=MemberStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_model(entity: SupplierMember) -> SupplierMemberModel:
    return SupplierMemberModel(
        id=entity.id,
        user_id=entity.user_id,
        supplier_id=entity.supplier_id,
        role=entity.role.value if isinstance(entity.role, MemberRole) else str(entity.role),
        status=entity.status.value if isinstance(entity.status, MemberStatus) else str(entity.status),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class SqlSupplierMemberRepository(ISupplierMemberRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, member_id: UUID) -> SupplierMember | None:
        statement = select(SupplierMemberModel).where(SupplierMemberModel.id == member_id)
        result = await self.session.exec(statement)
        model = result.first()
        return _to_entity(model) if model else None

    async def get_by_user_and_supplier(
        self, user_id: UUID, supplier_id: UUID
    ) -> SupplierMember | None:
        statement = select(SupplierMemberModel).where(
            SupplierMemberModel.user_id == user_id,
            SupplierMemberModel.supplier_id == supplier_id,
        )
        result = await self.session.exec(statement)
        model = result.first()
        return _to_entity(model) if model else None

    async def list_by_user_id(
        self, user_id: UUID, status: MemberStatus | None = None
    ) -> list[SupplierMember]:
        statement = select(SupplierMemberModel).where(
            SupplierMemberModel.user_id == user_id
        )
        if status is not None:
            statement = statement.where(
                SupplierMemberModel.status == (status.value if isinstance(status, MemberStatus) else str(status))
            )
        result = await self.session.exec(statement)
        return [_to_entity(m) for m in result.all()]

    async def list_by_supplier_id(
        self, supplier_id: UUID, status: MemberStatus | None = None
    ) -> list[SupplierMember]:
        statement = select(SupplierMemberModel).where(
            SupplierMemberModel.supplier_id == supplier_id
        )
        if status is not None:
            statement = statement.where(
                SupplierMemberModel.status == (status.value if isinstance(status, MemberStatus) else str(status))
            )
        result = await self.session.exec(statement)
        return [_to_entity(m) for m in result.all()]

    async def save(self, member: SupplierMember) -> SupplierMember:
        model = _to_model(member)
        self.session.add(model)
        await self.session.flush()
        return _to_entity(model)

    async def update(self, member: SupplierMember) -> SupplierMember:
        statement = select(SupplierMemberModel).where(SupplierMemberModel.id == member.id)
        result = await self.session.exec(statement)
        model = result.first()
        if not model:
            return await self.save(member)

        model.role = member.role.value if isinstance(member.role, MemberRole) else str(member.role)
        model.status = member.status.value if isinstance(member.status, MemberStatus) else str(member.status)
        model.updated_at = member.updated_at
        self.session.add(model)
        await self.session.flush()
        return _to_entity(model)

    async def delete(self, member_id: UUID) -> bool:
        statement = select(SupplierMemberModel).where(SupplierMemberModel.id == member_id)
        result = await self.session.exec(statement)
        model = result.first()
        if not model:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def list_user_workspaces(
        self, user_id: UUID
    ) -> list[UserWorkspaceSummary]:
        statement = (
            select(SupplierMemberModel, SupplierModel)
            .join(SupplierModel, SupplierMemberModel.supplier_id == SupplierModel.id)
            .where(
                SupplierMemberModel.user_id == user_id,
                SupplierMemberModel.status == MemberStatus.ACTIVE.value,
            )
        )
        result = await self.session.exec(statement)
        workspaces: list[UserWorkspaceSummary] = []
        for member_model, supplier_model in result.all():
            workspaces.append(
                UserWorkspaceSummary(
                    supplier_id=supplier_model.id,
                    legal_name=supplier_model.legal_name,
                    trade_name=supplier_model.trade_name,
                    rut=supplier_model.rut,
                    role=MemberRole(member_model.role),
                    status=MemberStatus(member_model.status),
                    is_active_context=False,
                )
            )
        return workspaces
