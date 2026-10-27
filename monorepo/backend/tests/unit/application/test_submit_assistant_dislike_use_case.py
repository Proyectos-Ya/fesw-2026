from uuid import uuid4
import pytest
from app.application.use_cases.feedback.submit_assistant_dislike import SubmitAssistantDislikeUseCase
from app.domain.entities.tender_chat import TenderChatMessage
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_chat_errors import MessageNotFoundError
from tests.unit.application.fakes import InMemorySupplierRepository, InMemoryTenderChatRepository
from tests.unit.application.feedback_fakes import InMemoryAssistantFeedbackRepository


async def _setup():
    user_id = uuid4()
    tender_id = uuid4()
    supplier = Supplier(id=uuid4(), rut="76086428-5", legal_name="Empresa SpA", user_id=user_id)
    supplier_repo = InMemorySupplierRepository()
    await supplier_repo.save(supplier)

    chat_repo = InMemoryTenderChatRepository()
    msg = TenderChatMessage(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        role="assistant",
        content="El plazo de entrega es 10 días",
    )
    await chat_repo.save_message(msg)

    feedback_repo = InMemoryAssistantFeedbackRepository()
    use_case = SubmitAssistantDislikeUseCase(
        assistant_feedback_repo=feedback_repo,
        chat_repo=chat_repo,
        supplier_repo=supplier_repo,
    )
    return use_case, feedback_repo, chat_repo, user_id, supplier.id, tender_id, msg.id


@pytest.mark.asyncio
async def test_submit_dislike_success():
    use_case, feedback_repo, _, user_id, supplier_id, tender_id, message_id = await _setup()

    res = await use_case.execute(
        user_id=user_id,
        supplier_id=supplier_id,
        tender_id=tender_id,
        message_id=message_id,
        reason="El plazo en las bases dice 30 días, no 10.",
    )

    assert res.message_id == message_id
    assert res.user_id == user_id
    assert res.supplier_id == supplier_id
    assert res.tender_id == tender_id
    assert res.reason == "El plazo en las bases dice 30 días, no 10."

    stored = await feedback_repo.get_by_message(message_id, user_id)
    assert stored is not None
    assert stored.reason == "El plazo en las bases dice 30 días, no 10."


@pytest.mark.asyncio
async def test_submit_dislike_nonexistent_message_raises_404():
    use_case, _, _, user_id, supplier_id, tender_id, _ = await _setup()
    with pytest.raises(MessageNotFoundError):
        await use_case.execute(
            user_id=user_id,
            supplier_id=supplier_id,
            tender_id=tender_id,
            message_id=uuid4(),
            reason="Cualquier motivo",
        )


@pytest.mark.asyncio
async def test_submit_dislike_message_from_different_tender_raises_404():
    use_case, _, _, user_id, supplier_id, _, message_id = await _setup()
    with pytest.raises(MessageNotFoundError):
        await use_case.execute(
            user_id=user_id,
            supplier_id=supplier_id,
            tender_id=uuid4(),  # otra licitacion
            message_id=message_id,
            reason="Cualquier motivo",
        )
