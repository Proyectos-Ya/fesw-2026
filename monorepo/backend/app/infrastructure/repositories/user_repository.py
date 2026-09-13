from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.user_repository import IUserRepository
from app.domain.entities.user import User
from app.domain.errors.auth_errors import UserAlreadyExists
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

    async def get_by_auth_provider_id(self, subject: str) -> User | None:
        result = await self.session.exec(
            select(UserModel).where(UserModel.auth_provider_id == subject)
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def save(self, user: User) -> User:
        """Inserta o actualiza, según exista ya la fila.

        `merge` y no `add`: `_to_model` arma un `UserModel` nuevo, y si la fila
        ya está en el identity map de la sesión —lo que garantiza cualquier
        `get_*` previo— `add` lanza `InvalidRequestError` por tener dos
        instancias con la misma clave. Mientras nada actualizaba usuarios el
        problema no se veía; con la sincronización del perfil en cada petición
        se dispararía siempre.
        """
        model = await self.session.merge(self._to_model(user))
        try:
            await self.session.commit()
        except IntegrityError as e:
            # Dos primeras peticiones simultáneas de la misma identidad
            # insertan las dos; el índice único de `auth_provider_id` deja
            # pasar una. Se traduce al error de dominio para que quien llama
            # no tenga que conocer SQLAlchemy, y pueda releer la fila ganadora.
            await self.session.rollback()
            raise UserAlreadyExists(user.email) from e
        await self.session.refresh(model)
        return self._to_entity(model)
