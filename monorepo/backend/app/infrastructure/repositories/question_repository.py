from uuid import UUID

from sqlmodel import col, select
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
            col(QuestionModel.answered).is_(False),
            col(QuestionModel.omitted).is_(False),
        )
        result = await self.session.exec(statement)
        models = result.all()
        return [self._to_entity(m) for m in models]

    async def get_by_id(self, question_id: UUID) -> Question | None:
        model = await self.session.get(QuestionModel, question_id)
        return self._to_entity(model) if model is not None else None

    async def get_by_provider_and_tender(
        self, provider_id: UUID, tender_id: UUID
    ) -> list[Question]:
        statement = select(QuestionModel).where(
            QuestionModel.provider_id == provider_id,
            QuestionModel.tender_id == tender_id,
        )
        result = await self.session.exec(statement)
        models = result.all()
        return [self._to_entity(m) for m in models]

    async def save(self, question: Question) -> Question:
        model = self._to_model(question)
        self.session.add(model)
        await self.session.flush()
        await self.session.commit()
        return self._to_entity(model)

    async def save_all(self, questions: list[Question]) -> list[Question]:
        saved_entities: list[Question] = []
        for entity in questions:
            model = self._to_model(entity)
            self.session.add(model)
            # Flush para obtener los IDs generados por Postgres de inmediato
            await self.session.flush()
            saved_entities.append(self._to_entity(model))
        await self.session.commit()
        return saved_entities

    async def update(self, question: Question) -> Question:
        model = await self.session.get(QuestionModel, question.id)
        if model is None:
            raise ValueError(f"Question with id {question.id} not found")
        data = question.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(model, key, value)
        self.session.add(model)
        await self.session.flush()
        await self.session.commit()
        return self._to_entity(model)
