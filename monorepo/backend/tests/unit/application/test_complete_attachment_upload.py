"""Confirmar una subida (plan 233, decisión 2).

El navegador sube directo al almacenamiento, así que el backend no vio los
bytes: acá se comprueba con un HEAD que llegó lo que se declaró. El tamaño se
verifica siempre; la huella, cuando el almacenamiento la informa.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from app.application.use_cases.tender_attachments.complete_attachment_upload import (
    CompleteAttachmentUploadUseCase,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from app.domain.errors.attachment_errors import (
    UploadedObjectMissing,
    UploadNotFound,
    UploadNotInProgress,
    UploadVerificationFailed,
)
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
    RecordingStoredListener,
)

T = uuid4()
WS = uuid4()
AHORA = datetime(2026, 10, 3, 15, 0)
CONTENIDO = b"hola"
SHA = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79"
KEY = f"private/{WS}/{SHA}.pdf"


def _subiendo(**cambios: object) -> AttachmentFile:
    base = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=T,
        sha256=SHA,
        size_bytes=4,
        storage_key=KEY,
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=WS,
        status=AttachmentFileStatus.UPLOADING,
        created_at=AHORA,
        purge_after=AHORA,
    )
    return base.model_copy(update=cambios)


class Escenario:
    def __init__(self, *, informa_checksum: bool = True, listener_falla: Exception | None = None):
        self.archivos = InMemoryAttachmentFileRepository()
        self.storage = FakeAttachmentStorage(informa_checksum=informa_checksum)
        self.listener = RecordingStoredListener(falla_con=listener_falla)

    def caso(self) -> CompleteAttachmentUploadUseCase:
        return CompleteAttachmentUploadUseCase(
            files=self.archivos,
            storage=self.storage,
            listener=self.listener,
            clock=lambda: AHORA,
        )

    def sembrar(self, archivo: AttachmentFile) -> AttachmentFile:
        self.archivos.filas[archivo.id] = archivo
        return archivo


async def test_tamano_y_huella_correctos_quedan_guardados() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo())
    e.storage.subir(KEY, CONTENIDO)

    resultado = await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert resultado.status == AttachmentFileStatus.STORED
    assert resultado.completed_at == AHORA
    assert resultado.purge_after is None
    assert e.archivos.filas[archivo.id] == resultado
    assert e.listener.recibidos == [resultado]


async def test_sin_checksum_del_almacenamiento_basta_el_tamano() -> None:
    # R2 podría no devolver el checksum: queda guardado y la decisión 4 lo recalcula.
    e = Escenario(informa_checksum=False)
    archivo = e.sembrar(_subiendo())
    e.storage.subir(KEY, CONTENIDO)

    resultado = await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert resultado.status == AttachmentFileStatus.STORED


async def test_tamano_distinto_borra_y_rechaza() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo())
    e.storage.subir(KEY, b"hola mundo")

    with pytest.raises(UploadVerificationFailed) as info:
        await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert e.storage.borradas == [KEY]
    fila = e.archivos.filas[archivo.id]
    assert fila.status == AttachmentFileStatus.REJECTED
    assert fila.purge_after == AHORA
    assert info.value.file == fila
    assert e.listener.recibidos == []


async def test_huella_distinta_borra_y_rechaza() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo())
    e.storage.subir(KEY, b"chao")  # mismo tamaño, otros bytes

    with pytest.raises(UploadVerificationFailed):
        await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert e.storage.borradas == [KEY]
    assert e.archivos.filas[archivo.id].status == AttachmentFileStatus.REJECTED
    assert e.listener.recibidos == []


async def test_no_borra_un_objeto_que_otra_fila_usa() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo())
    # Otra fila de la misma empresa (otro anexo, mismos bytes) apunta al mismo objeto.
    e.sembrar(_subiendo(id=uuid4(), tender_attachment_id=uuid4(), status=AttachmentFileStatus.STORED))
    e.storage.subir(KEY, b"chao")

    with pytest.raises(UploadVerificationFailed):
        await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert e.storage.borradas == []


async def test_sin_objeto_es_409_y_sigue_subiendo() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo())

    with pytest.raises(UploadedObjectMissing):
        await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert e.archivos.filas[archivo.id].status == AttachmentFileStatus.UPLOADING


async def test_subida_de_otra_empresa_es_404() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo())
    e.storage.subir(KEY, CONTENIDO)

    with pytest.raises(UploadNotFound):
        await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=uuid4())


async def test_subida_de_otra_licitacion_es_404() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo())

    with pytest.raises(UploadNotFound):
        await e.caso().execute(tender_id=uuid4(), upload_id=archivo.id, workspace_id=WS)


async def test_subida_inexistente_es_404() -> None:
    with pytest.raises(UploadNotFound):
        await Escenario().caso().execute(tender_id=T, upload_id=uuid4(), workspace_id=WS)


async def test_ya_guardado_es_idempotente() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo(status=AttachmentFileStatus.STORED, purge_after=None))

    resultado = await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert resultado == archivo
    assert e.storage.heads == 0
    assert e.listener.recibidos == []


async def test_rechazado_no_se_completa() -> None:
    e = Escenario()
    archivo = e.sembrar(_subiendo(status=AttachmentFileStatus.REJECTED))

    with pytest.raises(UploadNotInProgress):
        await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)


async def test_un_listener_que_falla_no_cambia_la_respuesta() -> None:
    e = Escenario(listener_falla=RuntimeError("boom"))
    archivo = e.sembrar(_subiendo())
    e.storage.subir(KEY, CONTENIDO)

    resultado = await e.caso().execute(tender_id=T, upload_id=archivo.id, workspace_id=WS)

    assert resultado.status == AttachmentFileStatus.STORED
    assert e.archivos.filas[archivo.id].status == AttachmentFileStatus.STORED
