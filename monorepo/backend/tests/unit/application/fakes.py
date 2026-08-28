"""Dobles en memoria para probar casos de uso sin BD ni servicios externos."""

from datetime import datetime
from uuid import UUID

from app.application.repositories.notification_repository import (
    INotificationDeliveryRepository,
    INotificationPreferenceRepository,
    INotificationRepository,
)
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
from app.application.services.email_service import EmailMessage, IEmailService
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.password_hasher import IPasswordHasher
from app.application.services.token_service import ITokenService
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
)
from app.domain.entities.saved_tender import SavedTender
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.entities.user import User
from app.domain.errors.auth_errors import InvalidToken
from app.domain.errors.notification_errors import (
    PermanentEmailError,
    TransientEmailError,
)
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

    async def list_user_ids_with_profile(self) -> list[UUID]:
        return [s.user_id for s in self.suppliers.values() if s.user_id is not None]

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


class InMemoryTenderChatRepository:
    def __init__(self) -> None:
        self.messages: list = []
        self.documents: dict[UUID, tuple] = {}  # doc_id: (doc_entity, file_bytes)

    async def save_message(self, message):
        self.messages.append(message)
        return message

    async def get_history(self, user_id: UUID, tender_id: UUID, limit: int = 50):
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

    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,  # noqa: ARG002
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Tender], int]:
        # Sin filtrar: los casos de uso que se prueban acá no dependen de los
        # criterios, solo de que el método exista y respete el paginado.
        todas = list(self.tenders.values())
        return todas[offset : offset + limit], len(todas)

    async def get_latest_tender_created_at(self) -> datetime | None:
        if not self.tenders:
            return None
        return max(t.created_at for t in self.tenders.values())

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(
        self, tender_id: UUID, supplier_id: UUID
    ) -> DeepAnalysis | None:
        return None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        return deep_analysis


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


class InMemoryNotificationPreferenceRepository(INotificationPreferenceRepository):
    def __init__(self) -> None:
        self.preferences: dict[UUID, NotificationPreference] = {}

    async def get_by_user_id(self, user_id: UUID) -> NotificationPreference | None:
        return self.preferences.get(user_id)

    async def list_by_delivery_mode(
        self, delivery_mode: str
    ) -> list[NotificationPreference]:
        return [
            p
            for p in self.preferences.values()
            if p.delivery_mode == delivery_mode and p.enabled
        ]

    async def save(self, preference: NotificationPreference) -> NotificationPreference:
        self.preferences[preference.user_id] = preference
        return preference


class InMemoryNotificationRepository(INotificationRepository):
    def __init__(self) -> None:
        self.notifications: dict[UUID, Notification] = {}

    async def get(self, notification_id: UUID) -> Notification | None:
        return self.notifications.get(notification_id)

    async def list_by_user(
        self, user_id: UUID, only_unread: bool = False, limit: int = 50
    ) -> list[Notification]:
        avisos = [n for n in self.notifications.values() if n.user_id == user_id]
        if only_unread:
            avisos = [n for n in avisos if n.read_at is None]
        avisos.sort(key=lambda n: n.created_at, reverse=True)
        return avisos[:limit]

    async def list_by_ids(self, notification_ids: list[UUID]) -> list[Notification]:
        return [
            self.notifications[i] for i in notification_ids if i in self.notifications
        ]

    async def count_unread(self, user_id: UUID) -> int:
        return len(
            [
                n
                for n in self.notifications.values()
                if n.user_id == user_id and n.read_at is None
            ]
        )

    async def get_notified_tender_ids(self, user_id: UUID) -> set[UUID]:
        return {
            n.tender_id for n in self.notifications.values() if n.user_id == user_id
        }

    async def save_bulk(self, notifications: list[Notification]) -> list[Notification]:
        for n in notifications:
            self.notifications[n.id] = n
        return notifications

    async def save(self, notification: Notification) -> Notification:
        self.notifications[notification.id] = notification
        return notification

    async def mark_all_read(self, user_id: UUID) -> int:
        from app.shared.datetime_utils import utc_now_naive

        cambiados = 0
        for n in self.notifications.values():
            if n.user_id == user_id and n.read_at is None:
                n.read_at = utc_now_naive()
                cambiados += 1
        return cambiados


class InMemoryNotificationDeliveryRepository(INotificationDeliveryRepository):
    def __init__(self) -> None:
        self.deliveries: dict[UUID, NotificationDelivery] = {}

    async def save(self, delivery: NotificationDelivery) -> NotificationDelivery:
        self.deliveries[delivery.id] = delivery
        return delivery

    async def list_due(self, now, limit: int = 20) -> list[NotificationDelivery]:
        vencidas = [d for d in self.deliveries.values() if d.is_due(now)]
        vencidas.sort(key=lambda d: d.next_attempt_at)
        return vencidas[:limit]

    async def list_by_user(
        self, user_id: UUID, limit: int = 50
    ) -> list[NotificationDelivery]:
        entregas = [d for d in self.deliveries.values() if d.user_id == user_id]
        entregas.sort(key=lambda d: d.created_at, reverse=True)
        return entregas[:limit]

    async def list_pending_notification_ids(self, user_id: UUID) -> set[UUID]:
        ids: set[UUID] = set()
        for d in self.deliveries.values():
            if d.user_id == user_id:
                ids.update(d.notification_ids)
        return ids


class FakeEmailService(IEmailService):
    """Servicio de correo que registra los envíos y puede simular fallos.

    `fail_with` permite reproducir los dos escenarios que la HdU distingue:
    servicio caído (transitorio) y dirección inexistente (permanente).
    """

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.sent: list[EmailMessage] = []
        self.fail_with = fail_with

    async def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)

    def simular_caida(self, motivo: str = "conexión rechazada") -> None:
        self.fail_with = TransientEmailError(motivo)

    def simular_destinatario_invalido(
        self, motivo: str = "la dirección no existe"
    ) -> None:
        self.fail_with = PermanentEmailError(motivo)

    def restablecer(self) -> None:
        self.fail_with = None
