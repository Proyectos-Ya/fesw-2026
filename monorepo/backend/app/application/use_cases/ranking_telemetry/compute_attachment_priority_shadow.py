"""Calcula la prioridad de anexos en sombra (plan 233, decisión 8).

Se guarda una foto por corrida y nadie la consume: ver
`AttachmentPriorityShadowService`.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from app.application.repositories.ranking_telemetry_repository import (
    IRankingTelemetryRepository,
)
from app.application.services.attachment_priority_shadow_service import (
    TOP_POSITIONS,
    URGENCY_MIN_HOURS,
    AttachmentPriorityShadowService,
)
from app.domain.entities.ranking_telemetry import (
    PRIORITY_WINDOW,
    AttachmentPriorityShadow,
)
from app.shared.datetime_utils import utc_now_naive


class ComputeAttachmentPriorityShadowUseCase:
    """Una prioridad por licitación publicada que cierra en más de 2 h y tiene alguna señal.

    "Subida manual" es hoy un documento en `tender_chat_documents` de los últimos
    7 días; pasará a leer la tabla de anexos con la decisión 2.
    """

    def __init__(
        self,
        repo: IRankingTelemetryRepository,
        service: AttachmentPriorityShadowService,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.repo = repo
        self.service = service
        self.now = now

    async def execute(self) -> int:
        now = self.now()
        since = now - PRIORITY_WINDOW
        top = await self.repo.count_top_impressions_by_tender(since, TOP_POSITIONS)
        interactions = await self.repo.count_interactions_by_tender(since)
        uploads = await self.repo.tenders_with_manual_upload(since)

        candidates = set(top) | set(interactions) | uploads
        if not candidates:
            return 0

        closing = await self.repo.open_tenders_closing_after(
            candidates, now + timedelta(hours=URGENCY_MIN_HOURS)
        )
        snapshots: list[AttachmentPriorityShadow] = []
        for tender_id, closing_at in closing.items():
            hours = (closing_at - now).total_seconds() / 3600
            priority, components = self.service.priority(
                top10_impressions=top.get(tender_id, 0),
                interactions=interactions.get(tender_id, 0),
                manual_upload=tender_id in uploads,
                hours_to_close=hours,
            )
            snapshots.append(
                AttachmentPriorityShadow(
                    tender_id=tender_id,
                    computed_at=now,
                    priority=priority,
                    components=components,
                )
            )
        await self.repo.save_priority_snapshots(snapshots)
        return len(snapshots)
