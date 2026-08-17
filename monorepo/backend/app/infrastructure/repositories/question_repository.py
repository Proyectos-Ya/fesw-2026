from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.question_repository import IQuestionRepository
from app.domain.entities.question import Question
from app.infrastructure.repositories.question_model import QuestionModel


class QuestionRepositoryImpl(IQuestionRepository):
    """Implementación concreta de IQuestionRepository utilizando SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: QuestionModel) -> Question:
        return Question(**model.model_dump())

    def _to_model(self, entity: Question) -> QuestionModel:
        return QuestionModel(**entity.model_dump())

    async def get_active_by_provider(self, provider_id: UUID) -> list[Question]:
        statement = select(QuestionModel).where(
            QuestionModel.provider_id == provider_id,
            QuestionModel.answered == False,
            QuestionModel.omitted == False,
        )
        result = await self.session.exec(statement)
        models = result.all()
        return [self._to_entity(m) for m in models]

    async def save_all(self, questions: list[Question]) -> list[Question]:
        saved_entities: list[Question] = []
        for entity in questions:
            model = self._to_model(entity)
            self.session.add(model)
            # Flush para obtener los IDs generados por Postgres de inmediato
            await self.session.flush()
            saved_entities.append(self._to_entity(model))
        return saved_entities
