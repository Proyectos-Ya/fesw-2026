"""Test para verificar que las dependencias del asistente de licitaciones en bootstrap.py
resuelven correctamente sin NameError ni errores de importación."""

from unittest.mock import AsyncMock
from sqlmodel.ext.asyncio.session import AsyncSession

from app.bootstrap import get_tender_chat_repo
from app.infrastructure.repositories.sql_tender_chat_repository import SQLTenderChatRepository


def test_get_tender_chat_repo_instantiation():
    mock_session = AsyncMock(spec=AsyncSession)
    repo = get_tender_chat_repo(mock_session)
    assert isinstance(repo, SQLTenderChatRepository)
    assert repo.session == mock_session
