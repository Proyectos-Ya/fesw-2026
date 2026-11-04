"""Subir un anexo dispara los hitos y el análisis + cotización (plan 233).

Se cuelgan de "el archivo quedó guardado" (`IAttachmentStoredListener`), que
corre después de confirmar la subida. Solo agendan: la subida no espera a Gemini.
Agendar dos veces cuesta como mucho una pasada más, así que son idempotentes.
"""

from app.application.services.attachment_stored_listener import (
    IAttachmentStoredListener,
)
from app.application.services.milestone_extraction_background import (
    IMilestoneExtractionBackground,
)
from app.application.services.tender_analysis_background import (
    ITenderAnalysisBackground,
)
from app.domain.entities.attachment_file import AttachmentFile, AttachmentFileStatus


def _de_una_empresa(file: AttachmentFile) -> bool:
    # La versión canónica compartida no tiene autor ni empresa: no hay a quién
    # agendarle. Los demás reciben los hitos al abrir la ficha.
    return file.status == AttachmentFileStatus.STORED and file.workspace_id is not None


class ScheduleMilestonesOnStored(IAttachmentStoredListener):
    """Extrae los hitos para quien subió el anexo, con los anexos de su empresa."""

    def __init__(self, extraction: IMilestoneExtractionBackground) -> None:
        self.extraction = extraction

    async def on_stored(self, file: AttachmentFile) -> None:
        if not _de_una_empresa(file) or file.uploader_user_id is None:
            return
        self.extraction.schedule(file.uploader_user_id, file.tender_id, file.workspace_id)


class ScheduleTenderAnalysisOnStored(IAttachmentStoredListener):
    """Rehace el análisis + cotización de la empresa con todos sus anexos."""

    def __init__(self, analysis: ITenderAnalysisBackground) -> None:
        self.analysis = analysis

    async def on_stored(self, file: AttachmentFile) -> None:
        if not _de_una_empresa(file) or file.workspace_id is None:
            return
        self.analysis.schedule(file.workspace_id, file.tender_id)
