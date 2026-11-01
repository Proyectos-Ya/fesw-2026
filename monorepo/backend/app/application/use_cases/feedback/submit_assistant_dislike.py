from uuid import UUID

from app.application.repositories.feedback_repository import (
    IAssistantFeedbackRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_chat_repository import (
    ITenderChatRepository,
)
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.feedback import AssistantMessageFeedback
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_chat_errors import MessageNotFoundError


class SubmitAssistantDislikeUseCase:
    """Registra la retroalimentación negativa (dislike) sobre una respuesta del asistente virtual (HU-24)."""

    def __init__(
        self,
        assistant_feedback_repo: IAssistantFeedbackRepository,
        chat_repo: ITenderChatRepository,
        supplier_repo: ISupplierRepository,
    ) -> None:
        self.assistant_feedback_repo = assistant_feedback_repo
        self.chat_repo = chat_repo
        self.supplier_repo = supplier_repo

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        message_id: UUID,
        reason: str,
    ) -> AssistantMessageFeedback:
        supplier = await resolver_empresa(self.supplier_repo, user_id, supplier_id)
        if supplier is None:
            raise SupplierNotFoundForUser(user_id)

        msg = await self.chat_repo.get_message_by_id(message_id)
        if msg is None or msg.tender_id != tender_id or msg.role != "assistant":
            raise MessageNotFoundError()

        feedback = AssistantMessageFeedback(
            message_id=message_id,
            user_id=user_id,
            supplier_id=supplier.id,
            tender_id=tender_id,
            reason=reason,
        )
        return await self.assistant_feedback_repo.upsert(feedback)
