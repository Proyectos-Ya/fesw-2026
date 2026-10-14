"""Listener para refrescar resúmenes cuando cambia la visibilidad compartida (plan 233, decisión 4 y 6)."""

from app.application.services.attachment_visibility_listener import (
    IAttachmentVisibilityListener,
)
from app.application.use_cases.attachment_processing.schedule_tender_digests import (
    ScheduleTenderDigestsUseCase,
)
from app.domain.entities.attachment_file import AttachmentFile


class RefreshDigestsOnShared(IAttachmentVisibilityListener):
    def __init__(self, schedule: ScheduleTenderDigestsUseCase) -> None:
        self._schedule = schedule

    async def on_visibility_changed(self, file: AttachmentFile) -> None:
        await self._schedule.after_visibility_change(file.tender_id)
