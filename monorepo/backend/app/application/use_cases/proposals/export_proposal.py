import re
from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.proposal_exporter import IProposalExporter
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.domain.errors.proposal_errors import (
    InvalidProposalTransition,
    ProposalDraftNotFound,
)
from app.domain.errors.tender_errors import TenderNotFound


@dataclass(frozen=True)
class ExportedFile:
    filename: str
    content: bytes


def _nombre_de_archivo(codigo: str) -> str:
    """Solo letras, números, puntos y guiones: va en el Content-Disposition."""
    seguro = re.sub(r"[^A-Za-z0-9.-]+", "-", codigo).strip("-")
    return f"postulacion-{seguro or 'compra-agil'}.docx"


class ExportProposalDocxUseCase:
    """Descarga el borrador redactado como Word (CA3).

    Es una lectura: funciona aunque la licitación haya cerrado, como el GET del
    borrador. Exige que esté redactado.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
        exporter: IProposalExporter,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo
        self.exporter = exporter

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None, tender_id: UUID
    ) -> ExportedFile:
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        tender = tenders[0]
        draft = await self.draft_repo.get(supplier.id, tender.id)
        if draft is None:
            raise ProposalDraftNotFound(tender.id)
        if draft.content is None:
            raise InvalidProposalTransition(draft.status, "exportar")
        return ExportedFile(
            filename=_nombre_de_archivo(tender.code),
            content=self.exporter.to_docx(draft, tender),
        )
