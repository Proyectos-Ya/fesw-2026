import unicodedata
from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.quotation_repository import IQuotationRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.schemas.proposal_schema import (
    PostulationCompanyInfo,
    PostulationItem,
    PostulationPackage,
    PostulationRequiredDocument,
    PostulationTenderInfo,
)
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.config import Settings, settings as default_settings
from app.domain.errors.proposal_errors import (
    PostulationFeatureDisabled,
    ProposalDraftNotFound,
    ProposalDraftNotReady,
)
from app.domain.errors.tender_errors import TenderClosedForProposal, TenderNotFound


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes/diacríticos y con un solo espacio entre palabras."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


class BuildPostulationPackageUseCase:
    """Construye el paquete de postulación determinista para Mercado Público (HU-032)."""

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
        quotation_repo: IQuotationRepository,
        settings: Settings | None = None,
    ) -> None:
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo
        self.quotation_repo = quotation_repo
        self.settings = settings or default_settings

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None, tender_id: UUID
    ) -> PostulationPackage:
        is_enabled = bool(self.settings.extension_enabled) and bool(
            getattr(self.settings, "extension_postulation_enabled", False)
        )
        if not is_enabled:
            raise PostulationFeatureDisabled()

        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        tender = tenders[0]

        if tender.esta_cerrada():
            raise TenderClosedForProposal(tender.id)

        draft = await self.draft_repo.get(supplier.id, tender_id)
        if draft is None:
            raise ProposalDraftNotFound(tender_id)

        if not draft.content:
            raise ProposalDraftNotReady(tender_id)

        # Cotización si existe
        quotation = await self.quotation_repo.get(supplier.id, tender_id)

        warnings: list[str] = []
        postulation_items: list[PostulationItem] = []
        used_materials: set[int] = set()

        is_clp = quotation is not None and quotation.currency == "CLP"
        if quotation and not is_clp:
            warnings.append(
                f"La cotización guardada está en moneda distinta a CLP ({quotation.currency}). "
                "Los precios no se cargarán automáticamente."
            )

        _STOPWORDS = {
            "servicio",
            "servicios",
            "adquisicion",
            "compra",
            "suministro",
            "para",
            "este",
            "esta",
            "con",
            "por",
            "del",
            "las",
            "los",
            "una",
            "uno",
            "que",
        }

        # Matching determinista de ítems
        for pos, item in enumerate(tender.items, start=1):
            key = normalizar_texto(item.description or item.name)
            key_name = normalizar_texto(item.name or "")
            key_desc = normalizar_texto(item.description or "")
            matched_material = None
            matched_idx = None

            if is_clp and quotation:
                # 1. Coincidencia exacta
                for idx, mat in enumerate(quotation.items):
                    if idx in used_materials:
                        continue
                    mat_norm = normalizar_texto(mat.description)
                    if mat_norm == key or mat_norm == key_name or mat_norm == key_desc:
                        matched_material = mat
                        matched_idx = idx
                        break

                # 2. Coincidencia por solapamiento semántico de palabras clave relevantes
                if matched_material is None:
                    words_tender = {
                        w
                        for w in (key_desc + " " + key_name).split()
                        if len(w) > 3 and w not in _STOPWORDS
                    }
                    best_overlap_count = 0
                    best_overlap_idx = None
                    for idx, mat in enumerate(quotation.items):
                        if idx in used_materials:
                            continue
                        words_mat = {
                            w
                            for w in normalizar_texto(mat.description).split()
                            if len(w) > 3 and w not in _STOPWORDS
                        }
                        overlap = words_tender & words_mat
                        if len(overlap) >= 2 and len(overlap) > best_overlap_count:
                            best_overlap_count = len(overlap)
                            best_overlap_idx = idx

                    if best_overlap_idx is not None:
                        matched_material = quotation.items[best_overlap_idx]
                        matched_idx = best_overlap_idx

            if matched_material is not None and matched_idx is not None:
                used_materials.add(matched_idx)
                unit_price = int(matched_material.unit_price)
                price_source = "cotizacion"
                quot_qty = float(matched_material.quantity)
                if quot_qty != float(item.quantity):
                    warnings.append(
                        f"La cantidad en cotización ({matched_material.quantity}) difiere "
                        f"de la licitación ({item.quantity}) para el ítem {item.name}."
                    )
            else:
                unit_price = None
                price_source = "sin_precio"
                quot_qty = None

            postulation_items.append(
                PostulationItem(
                    position=pos,
                    product_code=item.product_code,
                    name=item.name,
                    description=item.description,
                    quantity=float(item.quantity),
                    unit_of_measure=item.unit_of_measure,
                    unit_price=unit_price,
                    price_source=price_source,
                    quotation_quantity=quot_qty,
                )
            )

        if is_clp and quotation:
            unused_names = [
                mat.description
                for idx, mat in enumerate(quotation.items)
                if idx not in used_materials
            ]
            if unused_names:
                warnings.append(
                    f"La cotización incluye ítems que no corresponden a la licitación: {', '.join(unused_names)}."
                )

        # Campos de texto y placeholders
        offer_name = (
            draft.content.offer_name.paragraphs[0].text
            if draft.content.offer_name.paragraphs
            else tender.name
        )
        offer_desc = (
            draft.content.offer_description.paragraphs[0].text
            if draft.content.offer_description.paragraphs
            else ""
        )
        placeholders = (
            draft.content.offer_description.paragraphs[0].placeholders
            if draft.content.offer_description.paragraphs
            else []
        )

        # Documentos requeridos
        req_docs: list[PostulationRequiredDocument] = []
        if draft.content.required_documents.paragraphs:
            for p in draft.content.required_documents.paragraphs:
                req_docs.append(
                    PostulationRequiredDocument(name=p.text, is_mandatory=True, kind="documento")
                )

        technical_doc_available = (
            draft.content.technical_document is not None
            and len(draft.content.technical_document.sections) > 0
        )

        closing_iso = tender.closing_at.isoformat() if tender.closing_at else None
        quot_updated_iso = (
            quotation.updated_at.isoformat() if quotation and quotation.updated_at else None
        )

        return PostulationPackage(
            tender=PostulationTenderInfo(
                id=str(tender.id),
                code=tender.code,
                name=tender.name,
                closing_at=closing_iso,
            ),
            company=PostulationCompanyInfo(
                rut=supplier.rut,
                legal_name=supplier.legal_name,
                trade_name=supplier.trade_name,
            ),
            offer_name=offer_name,
            offer_description=offer_desc,
            offer_description_placeholders=placeholders,
            items=postulation_items,
            technical_document_available=technical_doc_available,
            required_documents=req_docs,
            warnings=warnings,
            quotation_updated_at=quot_updated_iso,
        )
