"""Puntos de extensión de la decisión 6: "cambió la visibilidad" y "se borró un archivo".

Que un listener falle no puede tumbar a los demás ni a la promoción o el borrado
que lo disparó.
"""

from datetime import datetime
from uuid import uuid4

from app.application.services.attachment_deleted_listener import (
    CompositeAttachmentDeletedListener,
    NoopAttachmentDeletedListener,
)
from app.application.services.attachment_visibility_listener import (
    CompositeAttachmentVisibilityListener,
    NoopAttachmentVisibilityListener,
)
from app.domain.entities.attachment_file import AttachmentFile
from tests.unit.application.attachment_file_fakes import (
    RecordingDeletedListener,
    RecordingVisibilityListener,
    canonico,
)


def _canonica() -> AttachmentFile:
    return canonico(
        tender_attachment_id=uuid4(),
        tender_id=uuid4(),
        sha256="0" * 64,
        created_at=datetime(2026, 10, 3),
    )


async def test_el_compuesto_de_visibilidad_avisa_a_todos_en_orden() -> None:
    primero, segundo = RecordingVisibilityListener(), RecordingVisibilityListener()
    archivo = _canonica()

    await CompositeAttachmentVisibilityListener([primero, segundo]).on_visibility_changed(archivo)

    assert primero.recibidos == [archivo]
    assert segundo.recibidos == [archivo]


async def test_si_el_primero_de_visibilidad_falla_el_segundo_igual_recibe_el_archivo() -> None:
    primero = RecordingVisibilityListener(falla_con=RuntimeError("boom"))
    segundo = RecordingVisibilityListener()
    archivo = _canonica()

    await CompositeAttachmentVisibilityListener([primero, segundo]).on_visibility_changed(archivo)

    assert primero.recibidos == [archivo]
    assert segundo.recibidos == [archivo]


async def test_el_compuesto_de_borrados_avisa_a_todos_en_orden() -> None:
    primero, segundo = RecordingDeletedListener(), RecordingDeletedListener()
    archivo = _canonica()

    await CompositeAttachmentDeletedListener([primero, segundo]).on_deleted(archivo)

    assert primero.recibidos == [archivo]
    assert segundo.recibidos == [archivo]


async def test_si_el_primero_de_borrados_falla_el_segundo_igual_recibe_el_archivo() -> None:
    primero = RecordingDeletedListener(falla_con=RuntimeError("boom"))
    segundo = RecordingDeletedListener()
    archivo = _canonica()

    await CompositeAttachmentDeletedListener([primero, segundo]).on_deleted(archivo)

    assert primero.recibidos == [archivo]
    assert segundo.recibidos == [archivo]


async def test_los_listeners_nulos_no_hacen_nada() -> None:
    archivo = _canonica()

    await NoopAttachmentVisibilityListener().on_visibility_changed(archivo)
    await NoopAttachmentDeletedListener().on_deleted(archivo)
