from abc import ABC, abstractmethod


class IPasswordHasher(ABC):
    """Contrato para hashear y verificar contraseñas.

    La implementación concreta (bcrypt, argon2, etc.) vive en infraestructura.
    """

    @abstractmethod
    def hash(self, plain_password: str) -> str:
        ...

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        ...
