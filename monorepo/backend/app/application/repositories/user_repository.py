from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.user import User


class IUserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_auth_provider_id(self, subject: str) -> User | None:
        """Busca el perfil enlazado a una identidad del proveedor externo.

        `subject` es el `sub` del token, no el id del perfil: es lo único que
        se conoce de quien llama antes de tener el perfil delante.
        """
        ...

    @abstractmethod
    async def save(self, user: User) -> User: ...
