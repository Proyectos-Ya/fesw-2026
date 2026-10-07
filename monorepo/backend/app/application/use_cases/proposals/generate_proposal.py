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
    TechnicalDocumentDTO,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals._documentos import adjuntos_del_usuario
from app.application.use_cases.proposals._postulacion import postulacion_abierta
from app.domain.entities.capability import ExperienceCatalog, ExperienceItem
from app.domain.entities.proposal import (
    TECHNICAL_SECTIONS,
    DraftContent,
    DraftParagraph,
    DraftSection,
    DraftSource,
    ProposalDraft,
    TechnicalDocument,
    TechnicalSection,
    es_declaracion_de_habilidad,
)
from app.domain.errors.proposal_errors import InvalidProposalTransition

_VACIO_SIN_RESPALDO = "[[INSERTAR: respaldo de esta afirmación]]"


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
    """Primero los detectados en la factibilidad; después los que sume la IA.

    Sin la Declaración Jurada de Habilidad: se acepta al enviar, no se adjunta.
    """
    textos = [
        r.text
        for r in draft.requirements
        if r.kind == "documento" and not es_declaracion_de_habilidad(r.text)
    ]
    vistos = {_clave(t) for t in textos}
    for parrafo in dto.paragraphs:
        if es_declaracion_de_habilidad(parrafo.text):
            continue
        if _clave(parrafo.text) not in vistos:
            vistos.add(_clave(parrafo.text))
            textos.append(parrafo.text)
    return DraftSection(
        paragraphs=[DraftParagraph.from_ai_text(t, sources=[]) for t in textos]
    )


def _un_solo_parrafo(seccion: DraftSection) -> DraftSection:
    """El "Detalle de la cotización" es un solo campo del formulario (plan 292,
    §2.7 A). Si la IA escribió varios párrafos, se juntan en uno con todas sus
    fuentes (sin repetir) y sus vacíos en orden. No se recorta: si pasa de
    `MAX_DETALLE_COTIZACION`, la pantalla lo marca y se regenera.
    """
    if len(seccion.paragraphs) < 2:
        return seccion
    fuentes: dict[str, DraftSource] = {}
    for parrafo in seccion.paragraphs:
        for fuente in parrafo.sources:
            fuentes.setdefault(fuente.id, fuente)
    texto = " ".join(
        t for p in seccion.paragraphs if (t := re.sub(r"\s+", " ", p.text).strip())
    )
    return DraftSection(
        paragraphs=[
            DraftParagraph(
                text=texto,
                sources=list(fuentes.values()),
                placeholders=[v for p in seccion.paragraphs for v in p.placeholders],
            )
        ]
    )


# Qué dato pedir cuando una sección del documento técnico viene vacía. Por
# defecto, el título de la sección; el equipo casi nunca está en el catálogo.
_VACIO_POR_SECCION = {"equipo": "nombre y experiencia del equipo"}


def _documento_tecnico(
    draft: ProposalDraft,
    dto: TechnicalDocumentDTO | None,
    items: dict[str, ExperienceItem],
) -> TechnicalDocument | None:
    """Plantilla fija, solo si las bases lo exigen (CA1), diga lo que diga la IA.

    Las secciones obligatorias van siempre: si la IA no las escribió, con un
    vacío en vez de texto inventado. "Otros requisitos" va solo si tiene algo.
    """
    if not draft.requires_technical_document:
        return None
    secciones: list[TechnicalSection] = []
    for plantilla in TECHNICAL_SECTIONS:
        redactada = getattr(dto, plantilla.key, None) if dto else None
        if redactada is not None and redactada.paragraphs:
            parrafos = _seccion(redactada, items).paragraphs
        elif plantilla.optional:
            continue
        else:
            dato = _VACIO_POR_SECCION.get(plantilla.key, plantilla.title.lower())
            parrafos = [
                DraftParagraph.from_ai_text(f"[[INSERTAR: {dato}]]", sources=[])
            ]
        secciones.append(
            TechnicalSection(
                key=plantilla.key, title=plantilla.title, paragraphs=parrafos
            )
        )
    return TechnicalDocument(sections=secciones)


def armar_contenido(
    draft: ProposalDraft, dto: DraftContentDTO, catalog: ExperienceCatalog
) -> DraftContent:
    items = {item.id: item for item in catalog.items}
    return DraftContent(
        offer_name=_seccion(dto.offer_name, items),
        offer_description=_un_solo_parrafo(_seccion(dto.offer_description, items)),
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
        require_ready: bool = False,
        request_technical_document: bool = False,
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
        if require_ready and draft.status != "READY":
            raise InvalidProposalTransition(draft.status, "regenerar")
        if not draft.can_generate():
            raise InvalidProposalTransition(draft.status, "redactar")
        if request_technical_document:
            # La empresa lo pide aunque el análisis no lo detectó en las bases.
            draft.request_technical_document()

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
