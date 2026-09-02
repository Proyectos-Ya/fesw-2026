from uuid import uuid4
from datetime import datetime

import pytest

from app.domain.entities.tender_chat import (
    TenderChatSession,
    TenderChatMessage,
    Citation,
    utc_now_naive,
)
from app.domain.errors.tender_chat_errors import (
    ChatSessionNotFoundError,
    ChatHistoryLoadError,
)


def test_create_tender_chat_session_default_values():
    tender_id = uuid4()
    user_id = uuid4()

    session = TenderChatSession(
        tender_id=tender_id,
        user_id=user_id,
    )

    assert session.id is not None
    assert session.tender_id == tender_id
    assert session.user_id == user_id
    assert session.title is None
    assert session.is_active is True
    assert isinstance(session.created_at, datetime)
    assert isinstance(session.updated_at, datetime)


def test_create_tender_chat_session_with_custom_values():
    session_id = uuid4()
    tender_id = uuid4()
    user_id = uuid4()
    custom_title = "Consulta sobre boleta de garantía"

    session = TenderChatSession(
        id=session_id,
        tender_id=tender_id,
        user_id=user_id,
        title=custom_title,
        is_active=False,
    )

    assert session.id == session_id
    assert session.title == custom_title
    assert session.is_active is False


def test_message_links_to_session_id():
    session_id = uuid4()
    tender_id = uuid4()
    user_id = uuid4()

    message = TenderChatMessage(
        session_id=session_id,
        tender_id=tender_id,
        user_id=user_id,
        role="user",
        content="¿Qué requisitos de experiencia exigen?",
    )

    assert message.session_id == session_id
    assert message.role == "user"
    assert message.content == "¿Qué requisitos de experiencia exigen?"


def test_message_session_id_optional_backwards_compatible():
    tender_id = uuid4()
    user_id = uuid4()

    message = TenderChatMessage(
        tender_id=tender_id,
        user_id=user_id,
        role="assistant",
        content="Se exige un mínimo de 3 años.",
    )

    assert message.session_id is None


def test_chat_session_not_found_error_message():
    err = ChatSessionNotFoundError()
    assert "La sesión de chat solicitada no existe." in str(err)


def test_chat_history_load_error_message():
    err = ChatHistoryLoadError()
    assert "No se pudo cargar el historial de la conversación" in str(err)
    assert "inicie un nuevo chat" in str(err)
