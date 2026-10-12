from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.capability_repository import (
    ICapabilityAnswerRepository,
    ICapabilityEvidenceRepository,
    ICapabilityQuestionRepository,
)
from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityEvidence,
    CapabilityQuestion,
)
from app.domain.errors.capability_errors import DuplicateCapabilityQuestion
from app.infrastructure.repositories.capability_model import (
    CapabilityAnswerModel,
    CapabilityEvidenceModel,
    CapabilityQuestionModel,
)

_QUESTION_KEY = "uq_capability_question_category_field"


def _violo(exc: IntegrityError, constraint: str) -> bool:
    """asyncpg expone el nombre en la excepción original; el mensaje es el respaldo."""
    original = getattr(exc.orig, "__cause__", None) or exc.orig
    return getattr(
        original, "constraint_name", None
    ) == constraint or constraint in str(exc)


class SqlCapabilityQuestionRepository(ICapabilityQuestionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: CapabilityQuestionModel) -> CapabilityQuestion:
        return CapabilityQuestion(**model.model_dump())

    async def get(self, question_id: UUID) -> CapabilityQuestion | None:
        model = await self.session.get(CapabilityQuestionModel, question_id)
        return self._to_entity(model) if model else None

    async def get_by_key(
        self, category: str, target_field: str
    ) -> CapabilityQuestion | None:
        result = await self.session.exec(
            select(CapabilityQuestionModel).where(
                CapabilityQuestionModel.category == category,
                CapabilityQuestionModel.target_field == target_field,
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def list_active(self, categories: set[str]) -> list[CapabilityQuestion]:
        if not categories:
            return []
        result = await self.session.exec(
            select(CapabilityQuestionModel)
            .where(
                col(CapabilityQuestionModel.category).in_(categories),
                col(CapabilityQuestionModel.active).is_(True),
            )
            .order_by(
                col(CapabilityQuestionModel.created_at),
                col(CapabilityQuestionModel.target_field),
            )
        )
        return [self._to_entity(m) for m in result.all()]

    async def list_by_ids(self, question_ids: list[UUID]) -> list[CapabilityQuestion]:
        if not question_ids:
            return []
        result = await self.session.exec(
            select(CapabilityQuestionModel).where(
                col(CapabilityQuestionModel.id).in_(question_ids)
            )
        )
        return [self._to_entity(m) for m in result.all()]

    async def add(self, question: CapabilityQuestion) -> CapabilityQuestion:
        # Las opciones van al JSONB como dicts, no como modelos de Pydantic.
        datos = question.model_dump()
        datos["options"] = [o.model_dump() for o in question.options]
        self.session.add(CapabilityQuestionModel(**datos))
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if _violo(exc, _QUESTION_KEY):
                existente = await self.get_by_key(
                    question.category, question.target_field
                )
                if existente is not None:
                    raise DuplicateCapabilityQuestion(existente) from exc
            raise
        return question


class SqlCapabilityAnswerRepository(ICapabilityAnswerRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: CapabilityAnswerModel) -> CapabilityAnswer:
        return CapabilityAnswer(**model.model_dump())

    async def get(
        self, supplier_id: UUID, question_id: UUID
    ) -> CapabilityAnswer | None:
        result = await self.session.exec(
            select(CapabilityAnswerModel).where(
                CapabilityAnswerModel.supplier_id == supplier_id,
                CapabilityAnswerModel.question_id == question_id,
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def list_by_supplier(self, supplier_id: UUID) -> list[CapabilityAnswer]:
        result = await self.session.exec(
            select(CapabilityAnswerModel)
            .where(CapabilityAnswerModel.supplier_id == supplier_id)
            .order_by(col(CapabilityAnswerModel.generated_at))
        )
        return [self._to_entity(m) for m in result.all()]

    async def save(self, answer: CapabilityAnswer) -> CapabilityAnswer:
        # Upsert por empresa y pregunta: dos pestañas respondiendo la misma
        # pregunta no pueden crear dos filas ni fallar por la restricción única.
        datos = answer.model_dump()
        sentencia = insert(CapabilityAnswerModel).values(**datos)
        sentencia = sentencia.on_conflict_do_update(
            constraint="uq_capability_answer_supplier_question",
            set_={
                "answer": sentencia.excluded.answer,
                "answered": sentencia.excluded.answered,
                "omitted": sentencia.excluded.omitted,
                "tender_id": sentencia.excluded.tender_id,
                "answered_by_user_id": sentencia.excluded.answered_by_user_id,
                "valid_until": sentencia.excluded.valid_until,
                "answered_at": sentencia.excluded.answered_at,
            },
        )
        await self.session.exec(sentencia)
        await self.session.commit()
        guardada = await self.get(answer.supplier_id, answer.question_id)
        if guardada is None:
            raise RuntimeError("La respuesta no quedó guardada tras el upsert.")
        return guardada


class SqlCapabilityEvidenceRepository(ICapabilityEvidenceRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: CapabilityEvidenceModel) -> CapabilityEvidence:
        return CapabilityEvidence(**model.model_dump())

    async def add(self, evidence: CapabilityEvidence) -> CapabilityEvidence:
        self.session.add(CapabilityEvidenceModel(**evidence.model_dump()))
        await self.session.commit()
        return evidence

    async def list_by_supplier(self, supplier_id: UUID) -> list[CapabilityEvidence]:
        result = await self.session.exec(
            select(CapabilityEvidenceModel)
            .where(CapabilityEvidenceModel.supplier_id == supplier_id)
            .order_by(
                col(CapabilityEvidenceModel.created_at),
                col(CapabilityEvidenceModel.id),
            )
        )
        return [self._to_entity(m) for m in result.all()]
