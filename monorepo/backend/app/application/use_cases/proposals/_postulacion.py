from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.domain.entities.capability import ExperienceCatalog, Polarity
from app.domain.entities.proposal import ProposalDraft
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.proposal_errors import ProposalDraftNotFound
from app.domain.errors.tender_errors import TenderClosedForProposal, TenderNotFound


@dataclass
class Postulacion:
    supplier: Supplier
    tender: Tender
    draft: ProposalDraft


async def postulacion_abierta(
    supplier_repo: ISupplierRepository,
    tender_repo: ITenderRepository,
    draft_repo: IProposalDraftRepository,
    user_id: UUID,
    supplier_id: UUID | None,
    tender_id: UUID,
) -> Postulacion:
    """Empresa activa, licitación y borrador, para una acción que escribe.

    Una licitación cerrada ya no acepta cambios en su postulación: el borrador
    se sigue pudiendo leer, pero no avanzar.
    """
    supplier = await empresa_o_error(supplier_repo, user_id, supplier_id)
    tenders = await tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
    if not tenders:
        raise TenderNotFound(tender_id)
    tender = tenders[0]
    if tender.esta_cerrada():
        raise TenderClosedForProposal(tender.id)
    draft = await draft_repo.get(supplier.id, tender.id)
    if draft is None:
        raise ProposalDraftNotFound(tender.id)
    return Postulacion(supplier=supplier, tender=tender, draft=draft)


def respuestas_vigentes(
    draft: ProposalDraft, catalog: ExperienceCatalog
) -> dict[UUID, tuple[Polarity | None, datetime | None]]:
    """Por cada pregunta del borrador, su polaridad vigente y cuándo se respondió.

    Una pregunta sin respuesta vigente en el catálogo (vencida o nunca
    respondida) queda con `(None, None)`.
    """
    items = {item.id: item for item in catalog.items}
    vigentes: dict[UUID, tuple[Polarity | None, datetime | None]] = {}
    for requirement in draft.requirements:
        question_id = requirement.capability_question_id
        if question_id is None:
            continue
        item = items.get(f"capacidad:{question_id}")
        vigentes[question_id] = (
            (item.polarity, item.answered_at) if item is not None else (None, None)
        )
    return vigentes
