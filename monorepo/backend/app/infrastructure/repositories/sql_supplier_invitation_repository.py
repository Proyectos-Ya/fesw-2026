from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import MemberRole
from app.infrastructure.repositories.supplier_invitation_model import (
    SupplierInvitationModel,
)


def _to_entity(model: SupplierInvitationModel) -> SupplierInvitation:
    return SupplierInvitation(
        id=model.id,
        supplier_id=model.supplier_id,
        email=model.email,
        role=MemberRole(model.role),
        invited_by_user_id=model.invited_by_user_id,
        token=model.token,
        status=InvitationStatus(model.status),
        expires_at=model.expires_at,
        created_at=model.created_at,
        accepted_at=model.accepted_at,
    )


def _to_model(entity: SupplierInvitation) -> SupplierInvitationModel:
    return SupplierInvitationModel(
        id=entity.id,
        supplier_id=entity.supplier_id,
        email=entity.email,
        role=entity.role.value if isinstance(entity.role, MemberRole) else str(entity.role),
        invited_by_user_id=entity.invited_by_user_id,
        token=entity.token,
        status=entity.status.value if isinstance(entity.status, InvitationStatus) else str(entity.status),
        expires_at=entity.expires_at,
        created_at=entity.created_at,
        accepted_at=entity.accepted_at,
    )


class SqlSupplierInvitationRepository(ISupplierInvitationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, invitation_id: UUID) -> SupplierInvitation | None:
        statement = select(SupplierInvitationModel).where(
            SupplierInvitationModel.id == invitation_id
        )
        result = await self.session.exec(statement)
        model = result.first()
        return _to_entity(model) if model else None

    async def get_by_token(self, token: str) -> SupplierInvitation | None:
        statement = select(SupplierInvitationModel).where(
            SupplierInvitationModel.token == token
        )
        result = await self.session.exec(statement)
        model = result.first()
        return _to_entity(model) if model else None

    async def list_by_supplier_id(
        self, supplier_id: UUID, status: InvitationStatus | None = None
    ) -> list[SupplierInvitation]:
        statement = select(SupplierInvitationModel).where(
            SupplierInvitationModel.supplier_id == supplier_id
        )
        if status is not None:
            statement = statement.where(
                SupplierInvitationModel.status == (status.value if isinstance(status, InvitationStatus) else str(status))
            )
        result = await self.session.exec(statement)
        return [_to_entity(m) for m in result.all()]

    async def list_by_email(
        self, email: str, status: InvitationStatus | None = None
    ) -> list[SupplierInvitation]:
        statement = select(SupplierInvitationModel).where(
            SupplierInvitationModel.email == email.strip().lower()
        )
        if status is not None:
            statement = statement.where(
                SupplierInvitationModel.status == (status.value if isinstance(status, InvitationStatus) else str(status))
            )
        result = await self.session.exec(statement)
        return [_to_entity(m) for m in result.all()]

    async def save(self, invitation: SupplierInvitation) -> SupplierInvitation:
        model = _to_model(invitation)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return _to_entity(model)

    async def update(self, invitation: SupplierInvitation) -> SupplierInvitation:
        statement = select(SupplierInvitationModel).where(
            SupplierInvitationModel.id == invitation.id
        )
        result = await self.session.exec(statement)
        model = result.first()
        if not model:
            return await self.save(invitation)

        model.role = invitation.role.value if isinstance(invitation.role, MemberRole) else str(invitation.role)
        model.status = invitation.status.value if isinstance(invitation.status, InvitationStatus) else str(invitation.status)
        model.accepted_at = invitation.accepted_at
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return _to_entity(model)
