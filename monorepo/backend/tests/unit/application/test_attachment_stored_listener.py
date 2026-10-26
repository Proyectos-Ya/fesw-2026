"""Punto de extensión "archivo guardado" (plan 233, decisión 2).

Las decisiones 4 (extracción) y 6 (promoción) se cuelgan de acá sin tocar los
casos de uso. Que un listener falle no puede tumbar a los demás ni a la subida.
"""

from datetime import datetime
from uuid import uuid4

from app.application.services.attachment_stored_listener import (
    CompositeAttachmentStoredListener,
    NoopAttachmentStoredListener,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from tests.unit.application.attachment_file_fakes import RecordingStoredListener


def _archivo() -> AttachmentFile:
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=uuid4(),
        sha256="0" * 64,
        size_bytes=1,
        storage_key="private/x",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=uuid4(),
        status=AttachmentFileStatus.STORED,
        created_at=datetime(2026, 10, 3),
    )


async def test_el_compuesto_avisa_a_todos_en_orden() -> None:
    primero, segundo = RecordingStoredListener(), RecordingStoredListener()
    archivo = _archivo()

    await CompositeAttachmentStoredListener([primero, segundo]).on_stored(archivo)

    assert primero.recibidos == [archivo]
    assert segundo.recibidos == [archivo]


async def test_si_el_primero_falla_el_segundo_igual_recibe_el_archivo() -> None:
    primero = RecordingStoredListener(falla_con=RuntimeError("boom"))
    segundo = RecordingStoredListener()
    archivo = _archivo()

    await CompositeAttachmentStoredListener([primero, segundo]).on_stored(archivo)

    assert segundo.recibidos == [archivo]


async def test_el_listener_nulo_no_hace_nada() -> None:
    await NoopAttachmentStoredListener().on_stored(_archivo())
