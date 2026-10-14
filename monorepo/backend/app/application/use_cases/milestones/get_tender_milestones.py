from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
)
from app.application.repositories.milestone_attachment_repository import (
    IMilestoneAttachmentRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.services.anexos_visibles import anexos_visibles
from app.application.services.milestone_extraction_background import (
    IMilestoneExtractionBackground,
    MilestoneExtractionStatus,
)
from app.application.use_cases.milestones.extract_tender_milestones import (
    empresa_del_usuario,
)
from app.application.use_cases.milestones.milestone_views import (
    TenderMilestonesResult,
    describe,
    get_tender,
    remove_orphan_file_milestones,
    save_official_milestones,
)
from app.shared.datetime_utils import utc_now_naive


class GetTenderMilestonesUseCase:
    """Hitos de la licitación para el usuario.

    Los de Mercado Público se guardan (o actualizan) al consultar: tienen que
    existir con id propio para poder elegirlos y sincronizarlos.

    Si la empresa tiene anexos que todavía no se leyeron para este usuario (los
    subió otro miembro), agenda la extracción: así cada miembro recibe los hitos
    al abrir la ficha, sin gastar llamadas en quien nunca la abre (plan 233).
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        milestones: ITenderMilestoneRepository,
        event_links: ICalendarEventLinkRepository,
        files: IAttachmentFileRepository,
        attachments: ITenderAttachmentRepository,
        processed: IMilestoneAttachmentRepository,
        suppliers: ISupplierRepository,
        extraction: IMilestoneExtractionBackground | None = None,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.event_links = event_links
        self.files = files
        self.attachments = attachments
        self.processed = processed
        self.suppliers = suppliers
        self.extraction = extraction
        self.now = now

    async def execute(
        self, user_id: UUID, tender_id: UUID, workspace_id: UUID | None = None
    ) -> TenderMilestonesResult:
        ahora = self.now()
        tender = await get_tender(self.tenders, tender_id)
        await save_official_milestones(self.milestones, self.event_links, tender, user_id, ahora)

        empresa = await empresa_del_usuario(self.suppliers, user_id, workspace_id)
        anexos = await anexos_visibles(
            self.files, self.attachments, tender_id=tender_id, workspace_id=empresa
        )
        # Al borrar un anexo, sus hitos se van en la próxima consulta.
        await remove_orphan_file_milestones(
            self.milestones, self.event_links, user_id, tender_id, {a.archivo.id for a in anexos}
        )
        procesados = await self.processed.list_processed(user_id, tender_id)
        pendientes = [a for a in anexos if a.legible and a.archivo.id not in procesados]

        estado = MilestoneExtractionStatus.IDLE
        if self.extraction is not None:
            estado = self.extraction.status(user_id, tender_id)
            # Si la última falló, reintenta el usuario con el botón: agendar en cada
            # consulta repetiría la llamada a Gemini cada vez que la ficha recarga.
            if pendientes and estado is MilestoneExtractionStatus.IDLE:
                self.extraction.schedule(user_id, tender_id, empresa)
                estado = MilestoneExtractionStatus.RUNNING

        return await describe(
            await self.milestones.list_for_tender(user_id, tender_id),
            self.event_links,
            ahora,
            len(anexos),
            extraction_status=estado,
            pending_documents_count=len(pendientes),
        )
