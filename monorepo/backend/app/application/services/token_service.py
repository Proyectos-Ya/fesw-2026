from abc import ABC, abstractmethod
from uuid import UUID


class ITokenService(ABC):
    """Contrato para emitir y validar tokens de acceso (JWT u otro)."""

    @abstractmethod
    def create_access_token(self, user_id: UUID) -> str: ...

    @abstractmethod
    def decode_token(self, token: str) -> UUID:
        """Devuelve el id de usuario (subject) del token.

        Lanza InvalidToken si el token es inválido o expiró.
        """
        ...
