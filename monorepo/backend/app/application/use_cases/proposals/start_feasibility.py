import logging
from uuid import UUID

from app.application.repositories.capability_repository import (
    ICapabilityAnswerRepository,
    ICapabilityQuestionRepository,
)
from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.application.services.proposal_ai_service import (
    FeasibilityRequirementDTO,
    IProposalAIService,
    NewQuestionDTO,
)
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals._documentos import adjuntos_del_usuario
from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityOption,
    CapabilityQuestion,
    ExperienceCatalog,
    ExperienceItem,
    question_leaks_supplier_data,
)
from app.domain.entities.proposal import (
    KINDS_SIN_PREGUNTA,
    ProposalDraft,
    Requirement,
    RequirementStatus,
)
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.capability_errors import DuplicateCapabilityQuestion
from app.domain.errors.tender_errors import TenderClosedForProposal, TenderNotFound
from app.shared.slug import slugify

logger = logging.getLogger(__name__)

# Las preguntas que propone la IA son de Sí o No: es lo que decide si la empresa
# cumple una exigencia. El detalle ("3 obras en 2024") va en los proyectos.
_OPCIONES_NUEVAS = [
    CapabilityOption(label="Sí", polarity="afirmativa"),
    CapabilityOption(label="No", polarity="negativa"),
]
_ESTADO_POR_POLARIDAD: dict[str | None, RequirementStatus] = {
    "afirmativa": "cumple",
    "negativa": "no_cumple",
    "neutra": "parcial",
    # Un dato del perfil (región, certificación declarada) no tiene polaridad:
    # si la IA lo cita como cobertura, la exigencia se cumple.
    None: "cumple",
}
_PREFIJO_CAPACIDAD = "capacidad:"


def categoria_de(supplier: Supplier) -> str:
    """Rubro del banco para la empresa: el primero de sus sectores.

    Las preguntas de un rubro solo se ofrecen a empresas de ese rubro, y la
    deduplicación del banco es por (rubro, clave).
    """
    for sector in supplier.sectors or []:
        clave = slugify(sector)
        if clave:
            return clave
    return "general"


def _pregunta_de_item(item: ExperienceItem) -> UUID | None:
    if not item.id.startswith(_PREFIJO_CAPACIDAD):
        return None
    try:
        return UUID(item.id.removeprefix(_PREFIJO_CAPACIDAD))
    except ValueError:
        return None


class StartFeasibilityUseCase:
    """Inicia (o recupera) la postulación de la empresa activa: fase de factibilidad.

    La IA lee la ficha, los adjuntos y el catálogo de la empresa y decide qué
    cubre cada exigencia. Este caso de uso no le cree a ciegas:

    - solo acepta ids que existan en el catálogo (guardrail contra alucinaciones);
    - reutiliza las preguntas del banco antes de crear otras;
    - una pregunta que nombre a la empresa no entra al banco compartido;
    - una respuesta que la empresa ya dio no se vuelve a pedir.

    Si ya hay borrador, lo devuelve sin llamar a la IA: la factibilidad se hace
    una vez por empresa y licitación.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
        question_repo: ICapabilityQuestionRepository,
        answer_repo: ICapabilityAnswerRepository,
        catalog_use_case: BuildExperienceCatalogUseCase,
        chat_repo: ITenderChatRepository,
        ai_service: IProposalAIService,
        validator_service: IDocumentValidatorService | None = None,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.catalog_use_case = catalog_use_case
        self.chat_repo = chat_repo
        self.ai_service = ai_service
        self.validator_service = validator_service

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None, tender_id: UUID
    ) -> ProposalDraft:
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)
        tender = await self._licitacion(tender_id)

        existente = await self.draft_repo.get(supplier.id, tender.id)
        if existente is not None:
            return existente
        if tender.esta_cerrada():
            raise TenderClosedForProposal(tender.id)

        catalog = await self.catalog_use_case.execute(
            user_id=user_id, supplier_id=supplier.id
        )
        categoria = categoria_de(supplier)
        banco = await self.question_repo.list_active({categoria})
        documentos = await adjuntos_del_usuario(
            self.chat_repo, self.validator_service, user_id, tender.id
        )

        resultado = await self.ai_service.analyze_feasibility(
            tender=tender,
            catalog=catalog,
            bank_questions=banco,
            documents=documentos,
        )

        requirements = [
            await self._exigencia(indice, dto, supplier, tender, catalog, categoria)
            for indice, dto in enumerate(resultado.requirements, start=1)
        ]

        draft = ProposalDraft(
            supplier_id=supplier.id,
            tender_id=tender.id,
            requires_technical_document=resultado.requires_technical_document,
            technical_document_reason=resultado.technical_document_reason,
            created_by_user_id=user_id,
        )
        draft.load_requirements(requirements)
        return await self.draft_repo.save(draft)

    async def _licitacion(self, tender_id: UUID) -> Tender:
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        return tenders[0]

    async def _exigencia(
        self,
        indice: int,
        dto: FeasibilityRequirementDTO,
        supplier: Supplier,
        tender: Tender,
        catalog: ExperienceCatalog,
        categoria: str,
    ) -> Requirement:
        base = Requirement(
            id=f"req-{indice}",
            text=dto.text,
            kind=dto.kind,
            mandatory=dto.mandatory,
            origin=dto.origin,
        )

        # 0. Una condición del servicio o un documento a adjuntar no describen a
        # la empresa: se dan por aceptados y no se preguntan, aunque la IA haya
        # propuesto una pregunta.
        if dto.kind in KINDS_SIN_PREGUNTA:
            return base.model_copy(update={"status": "cumple"})

        # 1. Cubierta por el catálogo: solo si el id existe de verdad.
        item = next((i for i in catalog.items if i.id == dto.catalog_item_id), None)
        if item is not None:
            return base.model_copy(
                update={
                    "status": _ESTADO_POR_POLARIDAD[item.polarity],
                    "catalog_item_id": item.id,
                    # Con la pregunta se puede corregir la respuesta si pausa.
                    "capability_question_id": _pregunta_de_item(item),
                }
            )

        # 2. Una pregunta del banco, existente o nueva.
        pregunta = await self._pregunta(dto, supplier, categoria)
        if pregunta is None:
            # No hay cómo preguntarla: queda a la vista pero no bloquea la
            # redacción, que la marcará como dato por completar.
            logger.warning(
                "Exigencia sin cobertura ni pregunta válida en %s: %s",
                tender.code,
                dto.text,
            )
            return base.model_copy(update={"status": "parcial"})

        status = await self._estado_de_la_respuesta(supplier, pregunta, tender)
        return base.model_copy(
            update={"status": status, "capability_question_id": pregunta.id}
        )

    async def _pregunta(
        self, dto: FeasibilityRequirementDTO, supplier: Supplier, categoria: str
    ) -> CapabilityQuestion | None:
        if dto.question_key:
            existente = await self.question_repo.get_by_key(categoria, dto.question_key)
            if existente is not None:
                return existente
        if dto.new_question is not None:
            return await self._registrar(dto.new_question, supplier, categoria)
        return None

    async def _registrar(
        self, nueva: NewQuestionDTO, supplier: Supplier, categoria: str
    ) -> CapabilityQuestion | None:
        if question_leaks_supplier_data(nueva.question, supplier):
            logger.warning(
                "Pregunta descartada por nombrar a la empresa: %s", nueva.question
            )
            return None
        try:
            pregunta = CapabilityQuestion(
                question=nueva.question,
                target_field=nueva.target_field,
                category=categoria,
                kind=nueva.kind,
                work_type=nueva.work_type
                if nueva.kind == "experiencia_proyecto"
                else None,
                options=_OPCIONES_NUEVAS,
                origin="ia",
            )
        except ValueError:
            logger.warning("Pregunta inválida propuesta por la IA: %s", nueva)
            return None
        try:
            return await self.question_repo.add(pregunta)
        except DuplicateCapabilityQuestion as duplicada:
            return duplicada.existing

    async def _estado_de_la_respuesta(
        self, supplier: Supplier, pregunta: CapabilityQuestion, tender: Tender
    ) -> RequirementStatus:
        """Usa la respuesta vigente si la hay; si no, deja una pendiente."""
        respuesta = await self.answer_repo.get(supplier.id, pregunta.id)
        if respuesta is not None and respuesta.is_current() and respuesta.answer:
            return _ESTADO_POR_POLARIDAD[pregunta.polarity_of(respuesta.answer)]
        if respuesta is None:
            await self.answer_repo.save(
                CapabilityAnswer(
                    supplier_id=supplier.id,
                    question_id=pregunta.id,
                    tender_id=tender.id,
                )
            )
        return "desconocido"
