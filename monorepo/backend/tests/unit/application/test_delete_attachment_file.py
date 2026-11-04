"""Borrar un archivo de anexo (plan 233, decisiones 2 y 6).

Un borrado nunca revela que existe el archivo privado de otra empresa (404, no
403), no rompe a otro anexo que comparte el mismo objeto, y no devuelve el cupo.
Un aporte ya corroborado tampoco se borra: no "descomparte" nada y confundiría.
Borrar uno que no lo está avisa a la promoción, porque puede destrabar un conflicto.
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
    AttachmentTrust,
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
    RecordingDeletedListener,
    canonico,
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
    confianza=AttachmentTrust.PENDING,
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
        trust=confianza,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )


class Escenario:
    def __init__(self) -> None:
        self.archivos = InMemoryAttachmentFileRepository()
        self.storage = FakeAttachmentStorage()
        self.listener = RecordingDeletedListener()

    def sembrar(self, archivo: AttachmentFile) -> AttachmentFile:
        self.archivos.filas[archivo.id] = archivo
        self.storage.subir(archivo.storage_key, b"hola")
        return archivo

    def caso(self, *, con_almacenamiento: bool = True) -> DeleteAttachmentFileUseCase:
        return DeleteAttachmentFileUseCase(
            files=self.archivos,
            storage=self.storage if con_almacenamiento else None,
            listener=self.listener,
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


async def test_la_version_compartida_no_es_de_nadie() -> None:
    e = Escenario()
    compartida = e.sembrar(
        canonico(
            tender_attachment_id=uuid4(),
            tender_id=T,
            sha256=SHA,
            storage_key=f"shared/{T}/1/{SHA}.pdf",
        )
    )

    with pytest.raises(NotAttachmentFileOwner):
        await e.caso().execute(tender_id=T, file_id=compartida.id, workspace_id=WS)

    assert compartida.id in e.archivos.filas
    assert e.storage.borradas == []
    assert e.listener.recibidos == []


async def test_una_canonica_oculta_responde_como_inexistente() -> None:
    # Suspendida por un conflicto: sin empresa, pero nadie la ve. Que la guardia de
    # dueño compare `None != ws` no puede dejar pasar a "es de otra empresa".
    e = Escenario()
    oculta = e.sembrar(
        canonico(
            tender_attachment_id=uuid4(),
            tender_id=T,
            sha256=SHA,
            storage_key=f"shared/{T}/1/{SHA}.pdf",
            visibility=AttachmentVisibility.PRIVATE,
            trust=AttachmentTrust.CONFLICT,
        )
    )

    with pytest.raises(AttachmentFileNotFound):
        await e.caso().execute(tender_id=T, file_id=oculta.id, workspace_id=WS)

    assert oculta.id in e.archivos.filas


async def test_un_aporte_propio_ya_corroborado_no_se_borra() -> None:
    e = Escenario()
    propio = e.sembrar(_archivo(confianza=AttachmentTrust.CORROBORATED))

    with pytest.raises(AttachmentFileIsShared):
        await e.caso().execute(tender_id=T, file_id=propio.id, workspace_id=WS)

    assert propio.id in e.archivos.filas
    assert e.storage.borradas == []
    assert e.listener.recibidos == []


@pytest.mark.parametrize(
    "confianza",
    [AttachmentTrust.PENDING, AttachmentTrust.CONFLICT, AttachmentTrust.REJECTED],
)
async def test_un_aporte_propio_sin_confirmar_se_borra_y_avisa(
    confianza: AttachmentTrust,
) -> None:
    e = Escenario()
    archivo = e.sembrar(_archivo(confianza=confianza))

    await e.caso().execute(tender_id=T, file_id=archivo.id, workspace_id=WS)

    assert archivo.id not in e.archivos.filas
    # Decisión 6: borrar una versión que chocaba puede destrabar lo compartido.
    assert e.listener.recibidos == [archivo]


async def test_un_listener_que_falla_no_cambia_el_resultado() -> None:
    e = Escenario()
    e.listener.falla_con = RuntimeError("boom")
    archivo = e.sembrar(_archivo())

    await e.caso().execute(tender_id=T, file_id=archivo.id, workspace_id=WS)

    assert archivo.id not in e.archivos.filas
    assert e.storage.borradas == [archivo.storage_key]


async def test_sin_listener_el_borrado_funciona_igual() -> None:
    e = Escenario()
    archivo = e.sembrar(_archivo())

    await DeleteAttachmentFileUseCase(files=e.archivos, storage=e.storage).execute(
        tender_id=T, file_id=archivo.id, workspace_id=WS
    )

    assert archivo.id not in e.archivos.filas


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
