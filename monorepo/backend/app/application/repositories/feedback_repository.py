from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.feedback import (
    AppFeedback,
    AssistantMessageFeedback,
    MatchReport,
    MatchReportKind,
)


class IMatchReportRepository(ABC):
    """Persistencia de los reportes de match y de análisis."""

    @abstractmethod
    async def upsert(self, report: MatchReport) -> MatchReport:
        """Guarda el reporte; si la empresa ya reportó esa licitación con ese tipo, reemplaza el motivo."""

    @abstractmethod
    async def list_reported_tender_ids(
        self, supplier_id: UUID, kind: MatchReportKind
    ) -> set[UUID]:
        """Licitaciones que esa empresa reportó con ese tipo."""


class IAssistantFeedbackRepository(ABC):
    """Persistencia de los dislikes a mensajes del asistente."""

    @abstractmethod
    async def upsert(
        self, feedback: AssistantMessageFeedback
    ) -> AssistantMessageFeedback:
        """Guarda el dislike; si el usuario ya lo dio a ese mensaje, reemplaza el motivo."""

    @abstractmethod
    async def get_by_message(
        self, message_id: UUID, user_id: UUID
    ) -> AssistantMessageFeedback | None:
        """Dislike de un usuario a un mensaje, si existe."""


class IAppFeedbackRepository(ABC):
    """Persistencia de comentarios, quejas y reseñas sobre el sistema."""

    @abstractmethod
    async def add(self, feedback: AppFeedback) -> AppFeedback:
        """Guarda un comentario o reseña."""
