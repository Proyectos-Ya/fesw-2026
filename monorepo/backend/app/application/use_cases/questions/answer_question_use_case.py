import logging
from uuid import UUID

from app.application.repositories.question_repository import IQuestionRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.use_cases.supplier.create_supplier import _build_supplier_text
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.question import Question
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


class AnswerQuestionUseCase:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        question_repo: IQuestionRepository | None = None,
        vector_repo: ISupplierVectorRepository | None = None,
        embedding_service: IEmbeddingService | None = None,
    ):
        self.supplier_repo = supplier_repo
        self.question_repo = question_repo
        self.vector_repo = vector_repo
        self.embedding_service = embedding_service

    async def execute(
        self,
        user_id: UUID,
        field_name: str | None = None,
        answer: str = "",
        question_id: UUID | None = None,
        supplier_id: UUID | None = None,
    ) -> None:
        """Guarda la respuesta en las keywords o memoria negativa de la empresa del usuario.

        - En flujo 'No': marca la pregunta como respondida y persiste target_keyword
          en `supplier.negative_keywords` con timestamp, sin tocar Qdrant.
        - En flujo 'Sí': marca la pregunta respondida, inyecta `target_keyword` en
          `supplier.keywords`, limpia `supplier.negative_keywords`, actualiza
          `profile_changed_at` y sincroniza con Qdrant de forma transaccional.
        """
        supplier = await resolver_empresa(self.supplier_repo, user_id, supplier_id)
        if supplier is None:
            raise ValueError("El usuario no tiene una empresa asociada.")

        now = utc_now_naive()
        question: Question | None = None

        if question_id is not None:
            if self.question_repo is None:
                raise RuntimeError("Question repository no configurado.")
            question = await self.question_repo.get_by_id(question_id)
            if question is None:
                raise ValueError("Pregunta no encontrada.")

        # Determinar el target_keyword asociado
        target_kw: str | None = None
        if question and question.target_keyword:
            target_kw = question.target_keyword
        elif field_name:
            target_kw = f"{field_name}:{answer}"
        elif question and question.target_profile_field:
            target_kw = f"{question.target_profile_field}:{answer}"

        clean_answer = answer.strip().lower()
        is_negative = (
            clean_answer == "no"
            or clean_answer.startswith("no,")
            or clean_answer.startswith("no ")
            or clean_answer == "descartar"
        )

        if is_negative:
            # === FLUJO NO ===
            if question and self.question_repo:
                question.answered = True
                question.answer = answer
                question.answered_at = now
                await self.question_repo.update(question)

            if target_kw:
                current_negatives = supplier.negative_keywords or []
                updated_negatives = [
                    item
                    for item in current_negatives
                    if isinstance(item, dict) and item.get("keyword") != target_kw
                ]
                updated_negatives.append(
                    {
                        "keyword": target_kw,
                        "discarded_at": now.isoformat(),
                    }
                )
                supplier.negative_keywords = updated_negatives

                if supplier.keywords:
                    supplier.keywords = [
                        k for k in supplier.keywords if k != target_kw
                    ]

            supplier.updated_at = now
            await self.supplier_repo.update(supplier)
            return

        # === FLUJO SÍ ===
        if question and self.question_repo:
            question.answered = True
            question.answer = answer
            question.answered_at = now
            await self.question_repo.update(question)

        if supplier.keywords is None:
            supplier.keywords = []

        if target_kw:
            if field_name:
                supplier.keywords = [
                    kw
                    for kw in supplier.keywords
                    if not kw.startswith(f"{field_name}:")
                ]
            if target_kw not in supplier.keywords:
                supplier.keywords.append(target_kw)

            # Limpieza automática de la keyword en negative_keywords
            if supplier.negative_keywords:
                supplier.negative_keywords = [
                    item
                    for item in supplier.negative_keywords
                    if isinstance(item, dict) and item.get("keyword") != target_kw
                ]

        supplier.updated_at = now
        supplier.profile_changed_at = now

        # Sincronización transaccional con Qdrant
        if self.embedding_service and self.vector_repo:
            text = _build_supplier_text(supplier)
            vectors = await self.embedding_service.embed([text])

            saved = await self.supplier_repo.stage_update(supplier)
            try:
                previous_vector = await self.vector_repo.get_vector(saved.id)
                await self.vector_repo.upsert(saved.id, vectors[0])
            except Exception:
                await self.supplier_repo.rollback()
                raise

            try:
                await self.supplier_repo.commit()
            except Exception:
                await self._restore_vector(saved.id, previous_vector)
                await self.supplier_repo.rollback()
                raise
        else:
            await self.supplier_repo.update(supplier)

    async def _restore_vector(
        self, supplier_id: UUID, previous_vector: list[float] | None
    ) -> None:
        try:
            if previous_vector is None:
                await self.vector_repo.delete(supplier_id)
            else:
                await self.vector_repo.upsert(supplier_id, previous_vector)
        except Exception:
            logger.exception(
                "No se pudo restaurar el vector del proveedor %s tras un commit fallido.",
                supplier_id,
            )
