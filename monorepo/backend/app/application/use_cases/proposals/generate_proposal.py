import re
from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.tender_repository import ITenderRepository
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.application.services.proposal_ai_service import (
    DraftContentDTO,
    DraftParagraphDTO,
    DraftSectionDTO,
    IProposalAIService,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals._documentos import adjuntos_del_usuario
from app.application.use_cases.proposals._postulacion import postulacion_abierta
from app.domain.entities.capability import ExperienceCatalog, ExperienceItem
from app.domain.entities.proposal import (
    DraftContent,
    DraftParagraph,
    DraftSection,
    DraftSource,
    ProposalDraft,
)
from app.domain.errors.proposal_errors import InvalidProposalTransition

_VACIO_SIN_RESPALDO = "[[INSERTAR: respaldo de esta afirmación]]"
_VACIO_DOCUMENTO_TECNICO = "[[INSERTAR: contenido del documento técnico]]"


def _clave(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _etiqueta(item: ExperienceItem) -> str:
    return f"{item.title}: {item.detail}"


def _parrafo(
    dto: DraftParagraphDTO, items: dict[str, ExperienceItem]
) -> DraftParagraph:
    """Aplica los guardrails de fuentes a un párrafo de la IA (CA5).

    Solo sobreviven las fuentes que existen en el catálogo. Si el párrafo afirma
    algo de la empresa y no le queda ninguna, se le agrega un vacío: el usuario
    ve que falta el respaldo en vez de firmar una afirmación inventada.
    """
    fuentes: list[DraftSource] = []
    for source_id in dict.fromkeys(dto.source_ids):
        item = items.get(source_id)
        if item is not None:
            fuentes.append(DraftSource(id=item.id, label=_etiqueta(item)))
    texto = dto.text
    if dto.asserts_company_fact and not fuentes:
        texto = f"{texto} {_VACIO_SIN_RESPALDO}"
    return DraftParagraph.from_ai_text(texto, sources=fuentes)


def _seccion(dto: DraftSectionDTO, items: dict[str, ExperienceItem]) -> DraftSection:
    return DraftSection(paragraphs=[_parrafo(p, items) for p in dto.paragraphs])


def _documentos_necesarios(draft: ProposalDraft, dto: DraftSectionDTO) -> DraftSection:
    """Primero los detectados en la factibilidad; después los que sume la IA."""
    textos = [r.text for r in draft.requirements if r.kind == "documento"]
    vistos = {_clave(t) for t in textos}
    for parrafo in dto.paragraphs:
        if _clave(parrafo.text) not in vistos:
            vistos.add(_clave(parrafo.text))
            textos.append(parrafo.text)
    return DraftSection(
        paragraphs=[DraftParagraph.from_ai_text(t, sources=[]) for t in textos]
    )


def _documento_tecnico(
    draft: ProposalDraft, dto: DraftSectionDTO | None, items: dict[str, ExperienceItem]
) -> DraftSection | None:
    """Solo si las bases lo exigen (CA1), diga lo que diga la IA."""
    if not draft.requires_technical_document:
        return None
    if dto is None or not dto.paragraphs:
        return DraftSection(
            paragraphs=[
                DraftParagraph.from_ai_text(_VACIO_DOCUMENTO_TECNICO, sources=[])
            ]
        )
    return _seccion(dto, items)


def armar_contenido(
    draft: ProposalDraft, dto: DraftContentDTO, catalog: ExperienceCatalog
) -> DraftContent:
    items = {item.id: item for item in catalog.items}
    return DraftContent(
        offer_name=_seccion(dto.offer_name, items),
        offer_description=_seccion(dto.offer_description, items),
        required_documents=_documentos_necesarios(draft, dto.required_documents),
        technical_document=_documento_tecnico(draft, dto.technical_document, items),
    )


class GenerateProposalUseCase:
    """Redacta el borrador de la postulación (CA1, CA2, CA5; etapa 2 del CA6).

    Solo con la factibilidad resuelta: sin preguntas pendientes, sin pausa y sin
    detener (la "pausa" del CA7). La IA redacta y este caso de uso aplica los
    guardrails antes de guardar. Si la IA falla, el borrador no cambia.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
        catalog_use_case: BuildExperienceCatalogUseCase,
        chat_repo: ITenderChatRepository,
        ai_service: IProposalAIService,
        validator_service: IDocumentValidatorService | None = None,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo
        self.catalog_use_case = catalog_use_case
        self.chat_repo = chat_repo
        self.ai_service = ai_service
        self.validator_service = validator_service

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        instructions: str | None = None,
    ) -> ProposalDraft:
        postulacion = await postulacion_abierta(
            self.supplier_repo,
            self.tender_repo,
            self.draft_repo,
            user_id,
            supplier_id,
            tender_id,
        )
        draft = postulacion.draft
        # Antes de gastar una llamada a la IA.
        if not draft.can_generate():
            raise InvalidProposalTransition(draft.status, "redactar")

        catalog = await self.catalog_use_case.execute(
            user_id=user_id, supplier_id=postulacion.supplier.id
        )
        documentos = await adjuntos_del_usuario(
            self.chat_repo, self.validator_service, user_id, tender_id
        )
        redaccion = await self.ai_service.generate_draft(
            tender=postulacion.tender,
            requirements=draft.requirements,
            catalog=catalog,
            warnings=draft.warnings,
            include_technical_document=draft.requires_technical_document,
            documents=documentos,
            instructions=instructions,
        )

        draft.mark_ready(armar_contenido(draft, redaccion, catalog), instructions)
        return await self.draft_repo.save(draft)
