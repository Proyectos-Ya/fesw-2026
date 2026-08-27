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


@pytest.mark.asyncio
async def test_get_history_with_specific_session_id(use_case, repo):
    tender_id = uuid4()
    user_id = uuid4()

    session_1 = await repo.create_session(user_id=user_id, tender_id=tender_id)
    msg1 = TenderChatMessage(
        session_id=session_1.id,
        tender_id=tender_id,
        user_id=user_id,
        role="user",
        content="Pregunta en sesión 1",
    )
    await repo.save_message(msg1)

    session_2 = await repo.create_session(user_id=user_id, tender_id=tender_id)
    msg2 = TenderChatMessage(
        session_id=session_2.id,
        tender_id=tender_id,
        user_id=user_id,
        role="user",
        content="Pregunta en sesión 2",
    )
    await repo.save_message(msg2)

    history_1 = await use_case.execute(tender_id=tender_id, user_id=user_id, session_id=session_1.id)
    assert len(history_1) == 1
    assert history_1[0].content == "Pregunta en sesión 1"

    history_2 = await use_case.execute(tender_id=tender_id, user_id=user_id, session_id=session_2.id)
    assert len(history_2) == 1
    assert history_2[0].content == "Pregunta en sesión 2"


@pytest.mark.asyncio
async def test_get_history_with_non_existent_session_raises_error(use_case):
    from app.domain.errors.tender_chat_errors import ChatSessionNotFoundError

    tender_id = uuid4()
    user_id = uuid4()
    fake_session_id = uuid4()

    with pytest.raises(ChatSessionNotFoundError):
        await use_case.execute(tender_id=tender_id, user_id=user_id, session_id=fake_session_id)

