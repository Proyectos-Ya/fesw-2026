import pytest
from uuid import uuid4

from app.application.use_cases.get_tender_chat_history_use_case import GetTenderChatHistoryUseCase
from app.domain.entities.tender_chat import TenderChatMessage, Citation
from tests.unit.application.fakes import InMemoryTenderChatRepository


@pytest.fixture
def repo():
    return InMemoryTenderChatRepository()


@pytest.fixture
def use_case(repo):
    return GetTenderChatHistoryUseCase(chat_repo=repo)


@pytest.mark.asyncio
async def test_get_history_empty(use_case):
    tender_id = uuid4()
    user_id = uuid4()
    history = await use_case.execute(tender_id=tender_id, user_id=user_id)
    assert history == []


@pytest.mark.asyncio
async def test_get_history_returns_messages_in_chronological_order(use_case, repo):
    tender_id = uuid4()
    user_id = uuid4()

    msg1 = TenderChatMessage(
        tender_id=tender_id,
        user_id=user_id,
        role="user",
        content="¿Cuál es el plazo?"
    )
    msg2 = TenderChatMessage(
        tender_id=tender_id,
        user_id=user_id,
        role="assistant",
        content="El plazo es de 3 días.",
        citations=[Citation(document_name="bases.pdf", quote="3 días")]
    )
    msg_other_tender = TenderChatMessage(
        tender_id=uuid4(),
        user_id=user_id,
        role="user",
        content="Otra licitacion"
    )

    await repo.save_message(msg1)
    await repo.save_message(msg2)
    await repo.save_message(msg_other_tender)

    history = await use_case.execute(tender_id=tender_id, user_id=user_id)
    assert len(history) == 2
    assert history[0].content == "¿Cuál es el plazo?"
    assert history[1].content == "El plazo es de 3 días."
    assert len(history[1].citations) == 1
