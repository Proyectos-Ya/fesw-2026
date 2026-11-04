"""Subir un anexo dispara los hitos y el análisis + cotización (plan 233)."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.application.services.schedule_ai_on_stored import (
    ScheduleMilestonesOnStored,
    ScheduleTenderAnalysisOnStored,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)

EMPRESA, AUTOR, LICITACION = uuid4(), uuid4(), uuid4()


class Agenda:
    def __init__(self) -> None:
        self.llamadas: list[tuple] = []

    def schedule(self, *args) -> None:
        self.llamadas.append(args)


def _archivo(
    estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
    *,
    workspace_id: UUID | None = EMPRESA,
) -> AttachmentFile:
    compartido = workspace_id is None
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=LICITACION,
        sha256="a" * 64,
        size_bytes=10,
        storage_key="anexos/x",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None if compartido else AUTOR,
        workspace_id=workspace_id,
        visibility=AttachmentVisibility.SHARED if compartido else AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.CORROBORATED if compartido else AttachmentTrust.PENDING,
        status=estado,
        created_at=datetime(2026, 10, 12, 12, 0),
    )


async def test_agenda_los_hitos_para_quien_subio_y_su_empresa():
    agenda = Agenda()

    await ScheduleMilestonesOnStored(agenda).on_stored(_archivo())

    assert agenda.llamadas == [(AUTOR, LICITACION, EMPRESA)]


async def test_agenda_el_analisis_para_la_empresa():
    agenda = Agenda()

    await ScheduleTenderAnalysisOnStored(agenda).on_stored(_archivo())

    assert agenda.llamadas == [(EMPRESA, LICITACION)]


@pytest.mark.parametrize("listener", [ScheduleMilestonesOnStored, ScheduleTenderAnalysisOnStored])
async def test_ignora_lo_que_no_quedo_guardado(listener):
    agenda = Agenda()

    await listener(agenda).on_stored(_archivo(AttachmentFileStatus.REJECTED))

    assert agenda.llamadas == []


@pytest.mark.parametrize("listener", [ScheduleMilestonesOnStored, ScheduleTenderAnalysisOnStored])
async def test_ignora_la_version_canonica_compartida(listener):
    # No tiene autor ni empresa: los demás reciben los hitos al abrir la ficha.
    agenda = Agenda()

    await listener(agenda).on_stored(_archivo(workspace_id=None))

    assert agenda.llamadas == []
