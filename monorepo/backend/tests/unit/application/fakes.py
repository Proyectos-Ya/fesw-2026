"""Dobles en memoria para probar casos de uso sin BD ni servicios externos."""
from uuid import UUID

from app.application.repositories.membership_repository import IMembershipRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import ISupplierVectorRepository
from app.application.repositories.user_repository import IUserRepository
from app.application.services.password_hasher import IPasswordHasher
from app.application.services.token_service import ITokenService
from app.domain.entities.membership import MembershipStatus, SupplierMembership
from app.domain.entities.supplier import Supplier
from app.domain.entities.user import User
from app.domain.errors.auth_errors import InvalidToken


class InMemoryUserRepository(IUserRepository):
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        for user in self.users.values():
            if user.email == email.strip().lower():
                return user
        return None

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def save(self, user: User) -> User:
        self.users[user.id] = user
        return user


class InMemoryMembershipRepository(IMembershipRepository):
    def __init__(self) -> None:
        self.memberships: dict[UUID, SupplierMembership] = {}

    async def save(self, membership: SupplierMembership) -> SupplierMembership:
        self.memberships[membership.id] = membership
        return membership

    async def get_by_id(self, membership_id: UUID) -> SupplierMembership | None:
        return self.memberships.get(membership_id)

    async def get_by_user(self, user_id: UUID) -> SupplierMembership | None:
        for m in self.memberships.values():
            if m.user_id == user_id:
                return m
        return None

    async def list_by_supplier(
        self, supplier_id: UUID, status: MembershipStatus | None = None
    ) -> list[SupplierMembership]:
        return [
            m
            for m in self.memberships.values()
            if m.supplier_id == supplier_id and (status is None or m.status == status)
        ]

    async def delete(self, membership_id: UUID) -> None:
        self.memberships.pop(membership_id, None)


class InMemorySupplierRepository(ISupplierRepository):
    def __init__(self) -> None:
        self.suppliers: dict[str, Supplier] = {}

    async def get_by_rut(self, rut: str) -> Supplier | None:
        return self.suppliers.get(rut)

    async def get_by_id(self, supplier_id: UUID) -> Supplier | None:
        for supplier in self.suppliers.values():
            if supplier.id == supplier_id:
                return supplier
        return None

    async def save(self, supplier: Supplier) -> Supplier:
        self.suppliers[supplier.rut] = supplier
        return supplier


class FakeSupplierVectorRepository(ISupplierVectorRepository):
    def __init__(self) -> None:
        self.upserts: list[UUID] = []

    def upsert(self, supplier_id: UUID, embedding: list[float]) -> None:
        self.upserts.append(supplier_id)

    def delete(self, supplier_id: UUID) -> None:
        pass


class FakePasswordHasher(IPasswordHasher):
    """Hash reversible y trivial — solo para pruebas, jamás producción."""

    def hash(self, plain_password: str) -> str:
        return f"hashed::{plain_password}"

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return hashed_password == f"hashed::{plain_password}"


class FakeTokenService(ITokenService):
    def create_access_token(self, user_id: UUID) -> str:
        return f"token::{user_id}"

    def decode_token(self, token: str) -> UUID:
        if not token.startswith("token::"):
            raise InvalidToken()
        try:
            return UUID(token.removeprefix("token::"))
        except ValueError as exc:
            raise InvalidToken() from exc
