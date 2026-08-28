"""Dobles en memoria para probar casos de uso sin BD ni servicios externos."""
from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import ISupplierVectorRepository
from app.application.repositories.tender_vector_repository import ITenderVectorRepository
from app.application.repositories.user_repository import IUserRepository
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.password_hasher import IPasswordHasher
from app.application.services.token_service import ITokenService
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

    async def get_by_user_id(self, user_id: UUID) -> Supplier | None:
        for supplier in self.suppliers.values():
            if supplier.user_id == user_id:
                return supplier
        return None

    async def save(self, supplier: Supplier) -> Supplier:
        self.suppliers[supplier.rut] = supplier
        return supplier

    async def update(self, supplier: Supplier) -> Supplier:
        self.suppliers[supplier.rut] = supplier
        return supplier


class FakeSupplierVectorRepository(ISupplierVectorRepository):
    def __init__(self) -> None:
        self.upserts: list[UUID] = []
        self.vectors: dict[UUID, list[float]] = {}

    def upsert(self, supplier_id: UUID, embedding: list[float]) -> None:
        self.upserts.append(supplier_id)
        self.vectors[supplier_id] = embedding

    def delete(self, supplier_id: UUID) -> None:
        self.vectors.pop(supplier_id, None)

    def get_vector(self, supplier_id: UUID) -> list[float] | None:
        return self.vectors.get(supplier_id)



class FakeTenderVectorRepository(ITenderVectorRepository):
    """Repositorio vectorial de licitaciones en memoria para pruebas."""

    def __init__(self) -> None:
        self.upserts: list[tuple[UUID, list[float], dict]] = []

    async def ensure_collection(self) -> None:
        pass

    async def upsert(self, tender_id: UUID, embedding: list[float], payload: dict) -> None:
        self.upserts.append((tender_id, embedding, payload))

    async def delete(self, tender_id: UUID) -> None:
        self.upserts = [(tid, emb, p) for tid, emb, p in self.upserts if tid != tender_id]

    async def search_by_supplier_vector(self, supplier_vector: list[float], limit: int, filters: dict | None = None) -> list[tuple[UUID, float]]:  # noqa: ARG002
        return []


class FakeEmbeddingService(IEmbeddingService):
    """Devuelve siempre el mismo vector configurable — evita cargar el modelo real."""

    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = vector if vector is not None else [0.5] * 1024
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vector] * len(texts)


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
