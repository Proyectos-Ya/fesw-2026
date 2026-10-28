"""Pruebas unitarias para QuestionRepositoryImpl.

Verifican el contrato y métodos de IQuestionRepository:
- get_by_id
- get_by_provider_and_tender
- save
- update
- Mapeo bidireccional preservando tender_id y target_keyword
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.entities.question import Question
from app.infrastructure.repositories.question_model import QuestionModel
from app.infrastructure.repositories.question_repository import QuestionRepositoryImpl


def _make_question(**kwargs) -> Question:
    defaults = {
        "provider_id": uuid4(),
        "question": "¿Pregunta de prueba?",
        "target_profile_field": "test_field",
        "target_category": "construccion",
        "options": ["Sí", "No"],
        "tender_id": uuid4(),
        "target_keyword": "certificacion:iso_9001",
    }
    defaults.update(kwargs)
    return Question(**defaults)


def _make_model(question: Question) -> QuestionModel:
    return QuestionModel(**question.model_dump())


class TestQuestionRepository:
    def test_implements_the_whole_contract(self) -> None:
        """La clase concreta se puede instanciar sin métodos abstractos faltantes."""
        assert QuestionRepositoryImpl.__abstractmethods__ == frozenset()
        QuestionRepositoryImpl(MagicMock())

    def test_mapping_preserves_tender_id_and_target_keyword(self) -> None:
        """Verifica que el mapeo preserve los nuevos campos tender_id y target_keyword."""
        repo = QuestionRepositoryImpl(MagicMock())
        question = _make_question()

        model = repo._to_model(question)
        assert model.tender_id == question.tender_id
        assert model.target_keyword == "certificacion:iso_9001"

        restored = repo._to_entity(model)
        assert restored.tender_id == question.tender_id
        assert restored.target_keyword == "certificacion:iso_9001"

    async def test_get_by_id_returns_entity_when_found(self) -> None:
        session = MagicMock()
        q = _make_question()
        model = _make_model(q)
        session.get = AsyncMock(return_value=model)

        repo = QuestionRepositoryImpl(session)
        result = await repo.get_by_id(q.id)

        assert result is not None
        assert result.id == q.id
        assert result.tender_id == q.tender_id
        assert result.target_keyword == q.target_keyword
        session.get.assert_awaited_once_with(QuestionModel, q.id)

    async def test_get_by_id_returns_none_when_not_found(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)

        repo = QuestionRepositoryImpl(session)
        missing_id = uuid4()
        result = await repo.get_by_id(missing_id)

        assert result is None
        session.get.assert_awaited_once_with(QuestionModel, missing_id)

    async def test_get_by_provider_and_tender(self) -> None:
        session = MagicMock()
        provider_id = uuid4()
        tender_id = uuid4()

        q1 = _make_question(provider_id=provider_id, tender_id=tender_id)
        q2 = _make_question(provider_id=provider_id, tender_id=tender_id)

        mock_result = MagicMock()
        mock_result.all.return_value = [_make_model(q1), _make_model(q2)]
        session.exec = AsyncMock(return_value=mock_result)

        repo = QuestionRepositoryImpl(session)
        results = await repo.get_by_provider_and_tender(provider_id, tender_id)

        assert len(results) == 2
        assert results[0].id == q1.id
        assert results[1].id == q2.id
        session.exec.assert_awaited_once()

    async def test_save_adds_and_flushes(self) -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        repo = QuestionRepositoryImpl(session)
        q = _make_question()
        saved = await repo.save(q)

        assert saved.id == q.id
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    async def test_update_updates_and_flushes(self) -> None:
        session = MagicMock()
        q = _make_question()
        model = _make_model(q)
        session.get = AsyncMock(return_value=model)
        session.add = MagicMock()
        session.flush = AsyncMock()

        repo = QuestionRepositoryImpl(session)
        q.answered = True
        q.answer = "Sí"

        updated = await repo.update(q)

        assert updated.answered is True
        assert updated.answer == "Sí"
        session.get.assert_awaited_once_with(QuestionModel, q.id)
        session.flush.assert_awaited_once()

    async def test_update_raises_when_not_found(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)

        repo = QuestionRepositoryImpl(session)
        q = _make_question()

        with pytest.raises(ValueError, match="not found"):
            await repo.update(q)
