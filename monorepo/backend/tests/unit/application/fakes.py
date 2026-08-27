"""Dobles en memoria para probar casos de uso sin BD ni servicios externos."""

from uuid import UUID

from app.application.repositories.saved_tender_repository import ISavedTenderRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.repositories.user_repository import IUserRepository
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.password_hasher import IPasswordHasher
from app.application.services.token_service import ITokenService
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.saved_tender import SavedTender
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.entities.user import User
from app.domain.errors.auth_errors import InvalidToken
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel


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

    async def upsert(
        self, tender_id: UUID, embedding: list[float], payload: dict
    ) -> None:
        self.upserts.append((tender_id, embedding, payload))

    async def delete(self, tender_id: UUID) -> None:
        self.upserts = [
            (tid, emb, p) for tid, emb, p in self.upserts if tid != tender_id
        ]

    async def search_by_vector(
        self,
        vector: list[float],
        limit: int,
        offset: int = 0,
        criteria: TenderFilterCriteria | None = None,
    ) -> list[tuple[UUID, float]]:  # noqa: ARG002
        return []

    async def count(self, criteria: TenderFilterCriteria | None = None) -> int:  # noqa: ARG002
        return 0


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


from app.domain.entities.tender_chat import TenderChatSession


class InMemoryTenderChatRepository:
    def __init__(self) -> None:
        self.messages: list = []
        self.documents: dict[UUID, tuple] = {}  # doc_id: (doc_entity, file_bytes)
        self.sessions: dict[UUID, TenderChatSession] = {}

    async def create_session(
        self, user_id: UUID, tender_id: UUID, title: str | None = None
    ) -> TenderChatSession:
        from uuid import uuid4

        for s in self.sessions.values():
            if s.user_id == user_id and s.tender_id == tender_id:
                s.is_active = False

        new_session = TenderChatSession(
            id=uuid4(),
            tender_id=tender_id,
            user_id=user_id,
            title=title,
            is_active=True,
        )
        self.sessions[new_session.id] = new_session
        return new_session

    async def get_or_create_active_session(
        self, user_id: UUID, tender_id: UUID
    ) -> TenderChatSession:
        active = [
            s
            for s in self.sessions.values()
            if s.user_id == user_id and s.tender_id == tender_id and s.is_active
        ]
        if active:
            return active[-1]
        return await self.create_session(user_id=user_id, tender_id=tender_id)

    async def get_session_by_id(
        self, session_id: UUID, user_id: UUID
    ) -> TenderChatSession | None:
        s = self.sessions.get(session_id)
        if s and s.user_id == user_id:
            return s
        return None

    async def get_session_history(
        self, session_id: UUID, user_id: UUID, limit: int = 50
    ):
        matched = [
            m
            for m in self.messages
            if m.session_id == session_id and m.user_id == user_id
        ]
        return matched[-limit:]

    async def archive_session(self, session_id: UUID, user_id: UUID) -> bool:
        s = self.sessions.get(session_id)
        if s and s.user_id == user_id:
            s.is_active = False
            return True
        return False

    async def save_message(self, message):
        if message.session_id is None:
            active = await self.get_or_create_active_session(
                user_id=message.user_id, tender_id=message.tender_id
            )
            message.session_id = active.id
        self.messages.append(message)
        return message

    async def get_history(self, user_id: UUID, tender_id: UUID, limit: int = 50):
        active = [
            s
            for s in self.sessions.values()
            if s.user_id == user_id and s.tender_id == tender_id and s.is_active
        ]
        if active:
            return await self.get_session_history(
                session_id=active[-1].id, user_id=user_id, limit=limit
            )

        matched = [
            m
            for m in self.messages
            if m.user_id == user_id and m.tender_id == tender_id
        ]
        return matched[-limit:]

    async def save_document(self, doc, file_bytes: bytes):
        self.documents[doc.id] = (doc, file_bytes)
        return doc

    async def get_documents_by_chat(self, user_id: UUID, tender_id: UUID):
        return [
            doc
            for doc, _ in self.documents.values()
            if doc.user_id == user_id and doc.tender_id == tender_id
        ]

    async def get_document_bytes(self, document_id: UUID, user_id: UUID):
        if document_id in self.documents:
            doc, data = self.documents[document_id]
            if doc.user_id == user_id:
                return data
        return None

    async def delete_document(self, document_id: UUID, user_id: UUID) -> bool:
        if document_id in self.documents:
            doc, _ = self.documents[document_id]
            if doc.user_id == user_id:
                del self.documents[document_id]
                return True
        return False



class InMemoryTenderRepository(ITenderRepository):
    """Fake repository en memoria para licitaciones."""

    def __init__(self) -> None:
        self.tenders: dict[UUID, Tender] = {}
        # Registro de llamadas: permite verificar que un caso de uso NO consulte
        # la base cuando no tiene ids que buscar.
        self.get_tenders_calls: list[TenderFilters] = []

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:
        self.get_tenders_calls.append(filters)
        results = []
        for t in self.tenders.values():
            if filters.ids and t.id not in filters.ids:
                continue
            if filters.regions:
                # En memoria asumimos que coincide para simplificar
                pass
            results.append(t)
        return results

    async def get_by_code(self, code: str) -> TenderModel | None:
        return None

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:
        return rut

    async def save_complex_tender(
        self, tender_model: TenderModel, items: list[TenderItemModel]
    ) -> None:
        pass

    async def get_or_create_status(self, status_id: int) -> int:
        return status_id

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(
        self, tender_id: UUID, supplier_id: UUID
    ) -> DeepAnalysis | None:
        return None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        return deep_analysis

    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Tender], int]:
        return ([], 0)

    async def get_latest_tender_created_at(self):
        return None



class InMemorySavedTenderRepository(ISavedTenderRepository):
    """Fake repository en memoria para las licitaciones guardadas por un usuario."""

    def __init__(self) -> None:
        # La clave replica la constraint única (user_id, tender_id) de la tabla.
        self.saved: dict[tuple[UUID, UUID], SavedTender] = {}

    async def get_by_user_id(self, user_id: UUID) -> list[SavedTender]:
        return [s for (uid, _), s in self.saved.items() if uid == user_id]

    async def get(self, user_id: UUID, tender_id: UUID) -> SavedTender | None:
        return self.saved.get((user_id, tender_id))

    async def save(self, saved_tender: SavedTender) -> SavedTender:
        self.saved[(saved_tender.user_id, saved_tender.tender_id)] = saved_tender
        return saved_tender

    async def delete(self, user_id: UUID, tender_id: UUID) -> bool:
        return self.saved.pop((user_id, tender_id), None) is not None

