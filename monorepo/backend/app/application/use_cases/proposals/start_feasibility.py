import hashlib
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
from app.application.services.tender_assistant_ai_service import DocumentContextDTO
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
    AnalysisDocument,
    ProposalDraft,
    Requirement,
    RequirementStatus,
    perfil_cubre,
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
    # si la IA lo cita como cobertura y `perfil_cubre` lo acepta, se cumple.
    None: "cumple",
}
_PREFIJO_CAPACIDAD = "capacidad:"
# Pocas y útiles: más preguntas cansan sin mejorar mucho la redacción.
_MAX_SUGERIDAS = 3
# Versión de la lógica de factibilidad (prompt, esquema y reglas). Entra en la
# huella: al subirla, "Volver a analizar" rehace los borradores hechos con la
# versión anterior aunque no cambien la ficha, el perfil ni los adjuntos. Se
# sube cada vez que cambia lo que el análisis produce.
VERSION_DEL_ANALISIS = "292-documento-tecnico-ambiguo"


def huella_del_analisis(
    tender: Tender,
    catalog: ExperienceCatalog,
    categoria: str,
    documentos: list[DocumentContextDTO],
) -> str:
    """Resume lo que usa la factibilidad, para saber si volver a analizar cambia algo.

    Cuenta la versión del análisis (`VERSION_DEL_ANALISIS`), la ficha (su
    última modificación), los datos del perfil que recibe la IA (los ítems
    `perfil:` del catálogo y el rubro) y el contenido de cada adjunto. No usa `supplier.updated_at`: el banner del home lo mueve al guardar
    `keywords`, que la factibilidad no lee, y descartaría el borrador sin motivo.

    **No** cuenta las respuestas al banco: las de la propia postulación las pidió
    este análisis, y si se cuentan, responder las preguntas ya bastaría para
    descartar el borrador. Tampoco la respuesta de la IA, que puede variar con
    las mismas entradas.
    """
    partes = [
        f"version:{VERSION_DEL_ANALISIS}",
        f"ficha:{tender.last_change_at.isoformat()}",
        f"rubro:{categoria}",
    ]
    perfil = sorted(
        (item.id, item.detail) for item in catalog.items if item.origin == "perfil"
    )
    partes += [f"perfil:{item_id}:{detalle}" for item_id, detalle in perfil]
    for doc in sorted(documentos, key=lambda d: d.document_name):
        contenido = hashlib.sha256(doc.file_bytes).hexdigest()
        partes.append(f"adjunto:{doc.document_name}:{doc.is_corrupted}:{contenido}")
    return hashlib.sha256("\n".join(partes).encode()).hexdigest()


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
    - no acepta el perfil genérico como prueba de experiencia o certificación
      (`perfil_cubre`): ahí pregunta;
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
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        force: bool = False,
    ) -> ProposalDraft:
        """Con `force`, vuelve a analizar aunque ya haya borrador.

        Sirve para cuando se subieron bases que faltaban. El borrador se rehace
        sobre el mismo id (una fila por empresa y licitación): exigencias nuevas,
        sin texto redactado ni decisiones. Las respuestas de la empresa siguen en
        el banco, así que lo ya respondido no se vuelve a preguntar.
        """
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)
        tender = await self._licitacion(tender_id)

        existente = await self.draft_repo.get(supplier.id, tender.id)
        if existente is not None and not force:
            return existente
        if tender.esta_cerrada():
            raise TenderClosedForProposal(tender.id)

        catalog = await self.catalog_use_case.execute(
            user_id=user_id, supplier_id=supplier.id
        )
        documentos = await adjuntos_del_usuario(
            self.chat_repo, self.validator_service, user_id, tender.id
        )
        categoria = categoria_de(supplier)
        huella = huella_del_analisis(tender, catalog, categoria, documentos)
        if existente is not None and existente.analysis_fingerprint == huella:
            # Nada cambió desde el análisis anterior: el borrador sigue sirviendo.
            return existente

        banco = await self.question_repo.list_active({categoria})

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
        requirements += await self._sugeridas(
            resultado.offer_questions, supplier, tender, catalog, categoria
        )

        draft = ProposalDraft(
            supplier_id=supplier.id,
            tender_id=tender.id,
            requires_technical_document=resultado.requires_technical_document,
            # Si la IA lo marca exigido y ambiguo a la vez, manda exigido.
            technical_document_ambiguous=resultado.technical_document_ambiguous
            and not resultado.requires_technical_document,
            technical_document_reason=resultado.technical_document_reason,
            analysis_fingerprint=huella,
            analysis_documents=[
                AnalysisDocument(name=doc.document_name, corrupted=doc.is_corrupted)
                for doc in documentos
            ],
            mentions_attachments=resultado.mentions_attachments,
            created_by_user_id=user_id,
        )
        if existente is not None:
            # Mismo id: se actualiza la fila en vez de chocar con la restricción
            # única (`supplier_id`, `tender_id`).
            draft.id = existente.id
            draft.created_at = existente.created_at
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

        # 1. Cubierta por el catálogo: solo si el id existe de verdad y ese
        # elemento puede probar este tipo de exigencia. La descripción o el rubro
        # no prueban una experiencia: en ese caso se pregunta.
        item = next((i for i in catalog.items if i.id == dto.catalog_item_id), None)
        cobertura_descartada = item is not None and not perfil_cubre(dto.kind, item.id)
        if item is not None and not cobertura_descartada:
            return base.model_copy(
                update={
                    "status": _ESTADO_POR_POLARIDAD[item.polarity],
                    "catalog_item_id": item.id,
                    # Con la pregunta se puede corregir la respuesta si pausa.
                    "capability_question_id": _pregunta_de_item(item),
                }
            )

        # 2. Una pregunta del banco, existente o nueva.
        pregunta = await self._pregunta(
            dto, supplier, categoria, con_respaldo=cobertura_descartada
        )
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

    async def _sugeridas(
        self,
        dtos: list[FeasibilityRequirementDTO],
        supplier: Supplier,
        tender: Tender,
        catalog: ExperienceCatalog,
        categoria: str,
    ) -> list[Requirement]:
        """Preguntas para fortalecer la oferta: solo las que quedan por responder.

        Lo que la empresa ya respondió o el catálogo ya cubre no se sugiere, y
        una condición del servicio o un documento no describen a la empresa.
        """
        sugeridas: list[Requirement] = []
        for dto in dtos:
            if len(sugeridas) == _MAX_SUGERIDAS:
                break
            if dto.kind in KINDS_SIN_PREGUNTA:
                continue
            requisito = await self._exigencia(
                len(sugeridas) + 1,
                dto.model_copy(update={"mandatory": False, "catalog_item_id": None}),
                supplier,
                tender,
                catalog,
                categoria,
            )
            if requisito.status != "desconocido":
                continue
            sugeridas.append(
                requisito.model_copy(
                    update={
                        "id": f"sug-{len(sugeridas) + 1}",
                        "suggested": True,
                        "origin": "Sugerida para fortalecer la oferta",
                    }
                )
            )
        return sugeridas

    async def _pregunta(
        self,
        dto: FeasibilityRequirementDTO,
        supplier: Supplier,
        categoria: str,
        con_respaldo: bool = False,
    ) -> CapabilityQuestion | None:
        """La pregunta del banco para la exigencia, si hay cómo hacerla.

        `con_respaldo`: se descartó la cobertura del perfil y, si la IA no dejó
        `question_key` ni `new_question`, se usa su `fallback_question`.
        """
        if dto.question_key:
            existente = await self.question_repo.get_by_key(categoria, dto.question_key)
            if existente is not None:
                return existente
        if dto.new_question is not None:
            nueva = await self._registrar(dto.new_question, supplier, categoria)
            if nueva is not None:
                return nueva
        if con_respaldo and dto.fallback_question is not None:
            return await self._registrar(dto.fallback_question, supplier, categoria)
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
