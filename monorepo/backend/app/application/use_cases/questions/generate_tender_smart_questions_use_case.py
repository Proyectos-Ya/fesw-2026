from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.question_repository import IQuestionRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.anexos_visibles import anexos_visibles
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.smart_question_ai_service import ISmartQuestionAIService
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.question import Question
from app.infrastructure.services.attachments.pdf_text import pdf_paginas
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


class GenerateTenderSmartQuestionsUseCase:
    """Orquestador para generar preguntas inteligentes basadas en IA y bases de licitación."""

    def __init__(
        self,
        question_repo: IQuestionRepository,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        ai_service: ISmartQuestionAIService,
        files_repo: IAttachmentFileRepository | None = None,
        attachments_repo: ITenderAttachmentRepository | None = None,
        storage: IAttachmentStorage | None = None,
        now_func: Callable[[], datetime] = utc_now_naive,
    ):
        self.question_repo = question_repo
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.ai_service = ai_service
        self.files_repo = files_repo
        self.attachments_repo = attachments_repo
        self.storage = storage
        self.now_func = now_func

    async def execute(
        self,
        user_id: UUID,
        tender_id: UUID,
        supplier_id: UUID | None = None,
    ) -> list[Question]:
        # 1. Resolver proveedor y licitación
        supplier = await resolver_empresa(self.supplier_repo, user_id, supplier_id)
        if supplier is None:
            raise ValueError("El usuario no tiene una empresa asociada.")

        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        tender = tenders[0] if tenders else None
        if tender is None:
            raise ValueError("Licitación no encontrada.")

        # 2. Idempotencia (Zero-Token Replay): si ya existen preguntas, retornar sin llamar a la IA
        existing_questions = await self.question_repo.get_by_provider_and_tender(
            provider_id=supplier.id, tender_id=tender.id
        )
        if existing_questions:
            return existing_questions

        # 3. Contexto RAG: Anexos visibles y extracción de texto PDF
        attachment_texts = await self._extract_attachment_texts(tender.id, supplier.id)

        # 4. Filtro de Memoria Negativa (TTL 6 meses): exclusiones menores a 180 días
        valid_negative_keywords = self._filter_negative_keywords(supplier.negative_keywords)

        # 5. Llamada al servicio de IA
        generated_dtos = await self.ai_service.generate_questions(
            tender=tender,
            supplier=supplier,
            attachment_texts=attachment_texts,
            valid_negative_keywords=valid_negative_keywords,
        )

        # 6. Persistencia asociada a tender_id
        questions_to_save: list[Question] = []
        for dto in generated_dtos:
            q = Question(
                provider_id=supplier.id,
                tender_id=tender.id,
                question=dto.question,
                target_profile_field=(
                    dto.target_keyword.split(":")[0]
                    if ":" in dto.target_keyword
                    else "keyword"
                ),
                target_keyword=dto.target_keyword,
                target_category="dynamic_ai",
                options=dto.options if dto.options else ["Sí", "No"],
            )
            questions_to_save.append(q)

        return await self.question_repo.save_all(questions_to_save)

    async def _extract_attachment_texts(
        self, tender_id: UUID, workspace_id: UUID
    ) -> list[str]:
        if not self.files_repo or not self.attachments_repo or not self.storage:
            return []

        attachment_texts: list[str] = []
        try:
            anexos = await anexos_visibles(
                self.files_repo,
                self.attachments_repo,
                tender_id=tender_id,
                workspace_id=workspace_id,
            )
            for anexo in anexos:
                if anexo.tipo.lower() == "pdf":
                    try:
                        datos = await self.storage.get_bytes(anexo.archivo.storage_key)
                        if datos:
                            paginas = pdf_paginas(datos)
                            texto = "\n".join(p for p in paginas if p.strip())
                            if texto.strip():
                                attachment_texts.append(
                                    f"Documento '{anexo.nombre}':\n{texto.strip()}"
                                )
                    except Exception:
                        logger.warning(
                            "No se pudo extraer texto del anexo %s", anexo.nombre
                        )
        except Exception:
            logger.warning("Error al listar anexos visibles para RAG", exc_info=True)

        return attachment_texts

    def _filter_negative_keywords(
        self, negative_keywords: list[dict[str, str]] | None
    ) -> list[str]:
        if not negative_keywords:
            return []

        now = self.now_func()
        cutoff = now - timedelta(days=180)
        valid: list[str] = []

        for item in negative_keywords:
            if not isinstance(item, dict):
                continue
            kw = item.get("keyword")
            discarded_at_str = item.get("discarded_at")
            if not kw:
                continue
            if not discarded_at_str:
                valid.append(kw)
                continue

            try:
                discarded_at = datetime.fromisoformat(discarded_at_str)
                if discarded_at.tzinfo is not None:
                    discarded_at = discarded_at.replace(tzinfo=None)
                if discarded_at >= cutoff:
                    valid.append(kw)
            except (ValueError, TypeError):
                valid.append(kw)

        return valid
