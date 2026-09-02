from uuid import uuid4
import pytest

from app.application.use_cases.create_tender_chat_session_use_case import (
    CreateTenderChatSessionUseCase,
)
from app.domain.entities.tender_chat import TenderChatMessage
from tests.unit.application.fakes import InMemoryTenderChatRepository


@pytest.mark.asyncio
async def test_create_session_creates_active_session():
    chat_repo = InMemoryTenderChatRepository()
    use_case = CreateTenderChatSessionUseCase(chat_repo)

    user_id = uuid4()
    tender_id = uuid4()

    session = await use_case.execute(user_id=user_id, tender_id=tender_id, title="Consulta Técnica")

    assert session.id is not None
    assert session.user_id == user_id
    assert session.tender_id == tender_id
    assert session.title == "Consulta Técnica"
    assert session.is_active is True


@pytest.mark.asyncio
async def test_create_session_cleans_memory_and_deactivates_previous_for_same_tender():
    chat_repo = InMemoryTenderChatRepository()
    use_case = CreateTenderChatSessionUseCase(chat_repo)

    user_id = uuid4()
    tender_id = uuid4()

    # 1. Primera sesión con mensajes
    session_1 = await use_case.execute(user_id=user_id, tender_id=tender_id)
    await chat_repo.save_message(
        TenderChatMessage(
            session_id=session_1.id,
            tender_id=tender_id,
            user_id=user_id,
            role="user",
            content="¿Cuál es el presupuesto?",
        )
    )

    # Verificar que session_1 tiene mensajes
    history_1 = await chat_repo.get_session_history(session_1.id, user_id)
    assert len(history_1) == 1

    # 2. Iniciar "Nuevo Chat" para la misma licitación
    session_2 = await use_case.execute(user_id=user_id, tender_id=tender_id)

    assert session_2.id != session_1.id
    assert session_2.is_active is True

    # La sesión anterior quedó inactiva
    s1_updated = await chat_repo.get_session_by_id(session_1.id, user_id)
    assert s1_updated is not None
    assert s1_updated.is_active is False

    # La nueva sesión inicia con memoria limpia (0 mensajes)
    history_2 = await chat_repo.get_session_history(session_2.id, user_id)
    assert len(history_2) == 0

    # get_history() por defecto entrega los mensajes de la sesión activa (vacía)
    active_history = await chat_repo.get_history(user_id=user_id, tender_id=tender_id)
    assert len(active_history) == 0
