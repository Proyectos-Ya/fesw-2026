"""Borrar un archivo de anexo (plan 233, decisión 2).

Un borrado nunca revela que existe el archivo privado de otra empresa (404, no
403), no rompe a otro anexo que comparte el mismo objeto, y no devuelve el cupo.
"""

from datetime import date, datetime
from uuid import uuid4

import pytest

from app.application.services.attachment_storage import AttachmentStorageError
from app.application.use_cases.tender_attachments.delete_attachment_file import (
    DeleteAttachmentFileUseCase,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentVisibility,
)
from app.domain.errors.attachment_errors import (
    AttachmentFileIsShared,
    AttachmentFileNotFound,
    AttachmentStorageUnavailable,
    NotAttachmentFileOwner,
)
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
)

T = uuid4()
WS = uuid4()
OTRA = uuid4()
SHA = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79"
AHORA = datetime(2026, 10, 3, 15, 0)


def _archivo(
    *,
    ws=WS,
    tender=T,
    visibilidad=AttachmentVisibility.PRIVATE,
    clave: str | None = None,
) -> AttachmentFile:
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=tender,
        sha256=SHA,
        size_bytes=4,
        storage_key=clave or f"private/{ws}/{SHA}.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=ws,
        visibility=visibilidad,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )


class Escenario:
    def __init__(self) -> None:
        self.archivos = InMemoryAttachmentFileRepository()
        self.storage = FakeAttachmentStorage()

    def sembrar(self, archivo: AttachmentFile) -> AttachmentFile:
        self.archivos.filas[archivo.id] = archivo
        self.storage.subir(archivo.storage_key, b"hola")
        return archivo

    def caso(self, *, con_almacenamiento: bool = True) -> DeleteAttachmentFileUseCase:
        return DeleteAttachmentFileUseCase(
            files=self.archivos, storage=self.storage if con_almacenamiento else None
        )


async def test_borra_el_objeto_y_la_fila_propios() -> None:
    e = Escenario()
    archivo = e.sembrar(_archivo())

    await e.caso().execute(tender_id=T, file_id=archivo.id, workspace_id=WS)

    assert e.storage.borradas == [archivo.storage_key]
    assert archivo.id not in e.archivos.filas


async def test_si_otra_fila_usa_el_objeto_solo_se_borra_la_fila() -> None:
    e = Escenario()
    archivo = e.sembrar(_archivo())
    otra = _archivo(clave=archivo.storage_key)
    e.archivos.filas[otra.id] = otra

    await e.caso().execute(tender_id=T, file_id=archivo.id, workspace_id=WS)

    assert e.storage.borradas == []
    assert archivo.id not in e.archivos.filas
    assert otra.id in e.archivos.filas


async def test_el_privado_de_otra_empresa_no_se_ve_como_existente() -> None:
    e = Escenario()
    ajeno = e.sembrar(_archivo(ws=OTRA))

    with pytest.raises(AttachmentFileNotFound):
        await e.caso().execute(tender_id=T, file_id=ajeno.id, workspace_id=WS)

    assert ajeno.id in e.archivos.filas
    assert e.storage.borradas == []


async def test_de_otra_licitacion_es_404() -> None:
    e = Escenario()
    archivo = e.sembrar(_archivo())

    with pytest.raises(AttachmentFileNotFound):
        await e.caso().execute(tender_id=uuid4(), file_id=archivo.id, workspace_id=WS)


async def test_inexistente_es_404() -> None:
    with pytest.raises(AttachmentFileNotFound):
        await Escenario().caso().execute(tender_id=T, file_id=uuid4(), workspace_id=WS)


async def test_compartido_ajeno_no_es_del_que_pide() -> None:
    e = Escenario()
    ajeno = e.sembrar(_archivo(ws=OTRA, visibilidad=AttachmentVisibility.SHARED))

    with pytest.raises(NotAttachmentFileOwner):
        await e.caso().execute(tender_id=T, file_id=ajeno.id, workspace_id=WS)

    assert ajeno.id in e.archivos.filas


async def test_compartido_propio_no_se_borra() -> None:
    e = Escenario()
    propio = e.sembrar(_archivo(visibilidad=AttachmentVisibility.SHARED))

    with pytest.raises(AttachmentFileIsShared):
        await e.caso().execute(tender_id=T, file_id=propio.id, workspace_id=WS)

    assert propio.id in e.archivos.filas


async def test_si_el_almacenamiento_falla_la_fila_sigue() -> None:
    # Primero el objeto, después la fila: un fallo no deja un registro sin archivo.
    e = Escenario()
    archivo = e.sembrar(_archivo())
    e.storage.falla_con = AttachmentStorageError("boom")

    with pytest.raises(AttachmentStorageError):
        await e.caso().execute(tender_id=T, file_id=archivo.id, workspace_id=WS)

    assert archivo.id in e.archivos.filas


async def test_sin_almacenamiento_es_503() -> None:
    e = Escenario()
    archivo = e.sembrar(_archivo())

    with pytest.raises(AttachmentStorageUnavailable):
        await e.caso(con_almacenamiento=False).execute(
            tender_id=T, file_id=archivo.id, workspace_id=WS
        )


async def test_borrar_no_devuelve_el_cupo() -> None:
    e = Escenario()
    archivo = e.sembrar(_archivo())
    e.archivos.cupo[(WS, date(2026, 10, 1))] = 3

    await e.caso().execute(tender_id=T, file_id=archivo.id, workspace_id=WS)

    assert e.archivos.cupo == {(WS, date(2026, 10, 1)): 3}
