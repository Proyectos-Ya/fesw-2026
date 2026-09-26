from app.application.services.tender_refresher import (
    ITenderRefresher,
    OfficialTenderDates,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)


class MercadoPublicoTenderRefresher(ITenderRefresher):
    """Refresca una licitación con la ingesta existente y expone sus fechas oficiales."""

    def __init__(self, ingestion_service: TenderIngestionService):
        self.ingestion_service = ingestion_service

    async def refresh(self, code: str) -> OfficialTenderDates | None:
        dto = await self.ingestion_service.refresh_tender(code)
        if dto is None:
            return None
        return OfficialTenderDates(published_at=dto.published_at, closing_at=dto.closing_at)
