from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.user_repository import IUserRepository
from app.domain.entities.user import User
from app.infrastructure.repositories.user_model import UserModel


class UserRepository(IUserRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: UserModel) -> User:
        return User(**model.model_dump())

    def _to_model(self, entity: User) -> UserModel:
        return UserModel(**entity.model_dump())

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.exec(
            select(UserModel).where(UserModel.email == email.strip().lower())
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self.session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    async def save(self, user: User) -> User:
        model = self._to_model(user)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)
