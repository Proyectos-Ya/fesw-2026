"""Pedir la URL para subir un anexo (plan 233, decisión 2).

El orden de las validaciones fija los códigos de error y, sobre todo, qué cuesta
cupo: nada se cobra hasta que el archivo calzó con el anexo oficial, y un
reintento o un duplicado no vuelven a cobrar. La privacidad se prueba aparte: lo
que sube otra empresa en privado no puede dar pistas.
"""

import hashlib
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.tender_attachments.request_attachment_upload import (
    RequestAttachmentUploadUseCase,
    UploadDeduplicated,
    UploadRequest,
    UploadTicket,
)
from app.domain.entities.attachment_file import (
    PLAZO_DE_SUBIDA_INCOMPLETA,
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.tender_attachment import OfficialAttachment
from app.domain.errors.attachment_errors import (
    AttachmentAlreadyUploaded,
    AttachmentExtensionMismatch,
    AttachmentNameMismatch,
    AttachmentNotFound,
    AttachmentStorageUnavailable,
    AttachmentTooLarge,
    UploadQuotaExceeded,
)
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.domain.services.attachment_files import (
    MAX_ATTACHMENT_SIZE_BYTES,
    clave_privada,
)
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
    RecordingStoredListener,
    canonico,
)

T = uuid4()
T2 = uuid4()
WS_A = uuid4()
WS_B = uuid4()
USER = uuid4()
AHORA = datetime(2026, 10, 3, 15, 0)
CONTENIDO = b"hola"
SHA = hashlib.sha256(CONTENIDO).hexdigest()
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NOMBRE_XLSX = "Anexo 3 Composición personalidad juridica.xlsx"
# Como lo deja el navegador al descargar dos veces el mismo archivo.
DESCARGADO_XLSX = "anexo 3 composicion personalidad juridica (1).XLSX"
T1_SYNC = datetime(2026, 9, 28, 16, 0)


def _sha(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


class Mundo:
    """Una licitación T con dos anexos oficiales, y T2 con uno del mismo nombre."""

    def __init__(self, *, uploads_per_month: int = 2, con_almacenamiento: bool = True) -> None:
        self.anexos = InMemoryTenderAttachmentRepository({"A": T, "B": T2})
        self.archivos = InMemoryAttachmentFileRepository()
        self.storage = FakeAttachmentStorage()
        self.listener = RecordingStoredListener()
        self.reloj = AHORA
        self.uploads_per_month = uploads_per_month
        self.con_almacenamiento = con_almacenamiento

    async def sincronizar(self) -> None:
        await self.anexos.sync_official_lists(
            {
                T: [
                    DocumentoOficialDTO(mp_document_id=1931002, nombre=NOMBRE_XLSX),
                    DocumentoOficialDTO(mp_document_id=1931003, nombre="Bases.pdf"),
                ],
                T2: [DocumentoOficialDTO(mp_document_id=77, nombre=NOMBRE_XLSX)],
            },
            visto_en=T1_SYNC,
        )

    def anexo(self, mp_document_id: int, tender_id: UUID = T) -> OfficialAttachment:
        return self.anexos.filas[(tender_id, mp_document_id)]

    @property
    def xlsx(self) -> OfficialAttachment:
        return self.anexo(1931002)

    @property
    def pdf(self) -> OfficialAttachment:
        return self.anexo(1931003)

    def caso(self) -> RequestAttachmentUploadUseCase:
        return RequestAttachmentUploadUseCase(
            attachments=self.anexos,
            files=self.archivos,
            storage=self.storage if self.con_almacenamiento else None,
            listener=self.listener,
            uploads_per_month=self.uploads_per_month,
            clock=lambda: self.reloj,
        )

    def pedido(
        self,
        anexo: OfficialAttachment | None = None,
        *,
        tender_id: UUID = T,
        ws: UUID = WS_A,
        nombre: str = DESCARGADO_XLSX,
        size: int = 4,
        mime: str = MIME_XLSX,
        sha: str = SHA,
    ) -> UploadRequest:
        return UploadRequest(
            tender_id=tender_id,
            attachment_id=(anexo or self.xlsx).id,
            workspace_id=ws,
            user_id=USER,
            file_name=nombre,
            size_bytes=size,
            mime=mime,
            sha256=sha,
        )

    def sembrar(
        self,
        anexo: OfficialAttachment | None = None,
        *,
        ws: UUID = WS_A,
        sha: str = SHA,
        estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
        visibilidad: AttachmentVisibility = AttachmentVisibility.PRIVATE,
        ext: str = "xlsx",
    ) -> AttachmentFile:
        anexo = anexo or self.xlsx
        archivo = AttachmentFile(
            id=uuid4(),
            tender_attachment_id=anexo.id,
            tender_id=anexo.tender_id,
            sha256=sha,
            size_bytes=4,
            storage_key=clave_privada(ws, sha, ext),
            source=AttachmentFileSource.MANUAL,
            uploader_user_id=USER,
            workspace_id=ws,
            visibility=visibilidad,
            status=estado,
            created_at=AHORA - timedelta(days=1),
        )
        self.archivos.filas[archivo.id] = archivo
        return archivo


@pytest.fixture
async def mundo() -> Mundo:
    m = Mundo()
    await m.sincronizar()
    return m


async def test_emite_la_url_y_crea_la_fila_subiendo(mundo: Mundo) -> None:
    resultado = await mundo.caso().execute(mundo.pedido())

    assert isinstance(resultado, UploadTicket)
    [fila] = mundo.archivos.filas.values()
    assert fila.status == AttachmentFileStatus.UPLOADING
    assert fila.storage_key == f"private/{WS_A}/{SHA}.xlsx"
    assert fila.source == AttachmentFileSource.MANUAL
    assert fila.visibility == AttachmentVisibility.PRIVATE
    assert fila.trust == AttachmentTrust.PENDING
    assert fila.uploader_user_id == USER
    assert fila.purge_after == AHORA + PLAZO_DE_SUBIDA_INCOMPLETA
    assert mundo.archivos.cupo[(WS_A, date(2026, 10, 1))] == 1
    assert mundo.storage.firmadas[0] == {
        "key": fila.storage_key,
        "size_bytes": 4,
        "sha256_hex": SHA,
        "content_type": MIME_XLSX,
        "expires_in_seconds": 900,
        "now": AHORA,
    }
    assert resultado.upload_id == fila.id
    assert resultado.method == "PUT"
    assert resultado.expires_at == AHORA + timedelta(minutes=15)


async def test_sin_almacenamiento_no_crea_nada() -> None:
    m = Mundo(con_almacenamiento=False)
    await m.sincronizar()

    with pytest.raises(AttachmentStorageUnavailable):
        await m.caso().execute(m.pedido())

    assert m.archivos.filas == {}


async def test_fila_de_otra_licitacion_es_404(mundo: Mundo) -> None:
    ajena = mundo.anexo(77, T2)

    with pytest.raises(AttachmentNotFound):
        await mundo.caso().execute(mundo.pedido(ajena, tender_id=T))


async def test_fila_retirada_es_404(mundo: Mundo) -> None:
    pdf = mundo.pdf
    await mundo.anexos.sync_official_lists(
        {T: [DocumentoOficialDTO(mp_document_id=1931002, nombre=NOMBRE_XLSX)]},
        visto_en=T1_SYNC + timedelta(hours=1),
    )

    with pytest.raises(AttachmentNotFound):
        await mundo.caso().execute(mundo.pedido(pdf, nombre="bases.pdf", mime="application/pdf"))


async def test_supera_50_mb(mundo: Mundo) -> None:
    with pytest.raises(AttachmentTooLarge) as info:
        await mundo.caso().execute(mundo.pedido(size=MAX_ATTACHMENT_SIZE_BYTES + 1))

    assert info.value.extra == {"max_size_bytes": MAX_ATTACHMENT_SIZE_BYTES}
    assert mundo.archivos.cupo == {}
    # Justo en el máximo, sí.
    assert isinstance(
        await mundo.caso().execute(mundo.pedido(size=MAX_ATTACHMENT_SIZE_BYTES)),
        UploadTicket,
    )


async def test_extension_distinta_no_gasta_cupo(mundo: Mundo) -> None:
    with pytest.raises(AttachmentExtensionMismatch):
        await mundo.caso().execute(mundo.pedido(nombre="Anexo 3 Composición personalidad juridica.pdf"))

    assert mundo.archivos.cupo == {}
    assert mundo.archivos.filas == {}


async def test_nombre_distinto_informa_el_esperado(mundo: Mundo) -> None:
    with pytest.raises(AttachmentNameMismatch) as info:
        await mundo.caso().execute(mundo.pedido(nombre="Otro.xlsx"))

    assert info.value.extra["expected_name"] == NOMBRE_XLSX
    assert mundo.archivos.cupo == {}


async def test_mismo_sha_ya_guardado_por_la_empresa_deduplica(mundo: Mundo) -> None:
    existente = mundo.sembrar()

    resultado = await mundo.caso().execute(mundo.pedido())

    assert isinstance(resultado, UploadDeduplicated)
    assert resultado.file.id == existente.id
    assert mundo.storage.firmadas == []
    assert mundo.archivos.cupo == {}


async def test_compartido_guardado_deduplica(mundo: Mundo) -> None:
    # La versión compartida es la canónica, sin empresa (decisión 6).
    compartido = canonico(
        tender_attachment_id=mundo.xlsx.id, tender_id=T, sha256=SHA, storage_key="shared/x"
    )
    mundo.archivos.filas[compartido.id] = compartido

    resultado = await mundo.caso().execute(mundo.pedido())

    assert isinstance(resultado, UploadDeduplicated)
    assert resultado.file.id == compartido.id
    assert mundo.archivos.cupo == {}


async def test_privado_de_otra_empresa_no_deduplica(mundo: Mundo) -> None:
    # Privacidad: que otra empresa tenga estos mismos bytes en privado no puede
    # saltarse la subida ni revelar que existen.
    mundo.sembrar(ws=WS_B, visibilidad=AttachmentVisibility.PRIVATE)

    resultado = await mundo.caso().execute(mundo.pedido())

    assert isinstance(resultado, UploadTicket)
    assert mundo.archivos.cupo[(WS_A, date(2026, 10, 1))] == 1


async def test_otro_sha_ya_guardado_es_409(mundo: Mundo) -> None:
    mundo.sembrar(sha=_sha(b"otro contenido"))

    with pytest.raises(AttachmentAlreadyUploaded):
        await mundo.caso().execute(mundo.pedido())

    assert mundo.archivos.cupo == {}


async def test_mismo_objeto_en_otro_anexo_no_sube_ni_gasta_cupo(mundo: Mundo) -> None:
    # Los mismos bytes ya están verificados para otro anexo de la empresa (misma
    # clave de objeto): no se emite una URL que podría sobrescribirlos ni se cobra.
    mundo.sembrar(mundo.anexo(77, T2))

    resultado = await mundo.caso().execute(mundo.pedido())

    assert isinstance(resultado, UploadDeduplicated)
    assert resultado.file.tender_attachment_id == mundo.xlsx.id
    assert resultado.file.status == AttachmentFileStatus.STORED
    assert resultado.file.purge_after is None
    assert mundo.storage.firmadas == []
    assert mundo.archivos.cupo == {}
    assert mundo.listener.recibidos == [resultado.file]
    assert resultado.file.id in mundo.archivos.filas


async def test_reintento_reusa_la_fila_y_no_cobra(mundo: Mundo) -> None:
    primero = await mundo.caso().execute(mundo.pedido())
    segundo = await mundo.caso().execute(mundo.pedido())

    assert isinstance(primero, UploadTicket) and isinstance(segundo, UploadTicket)
    assert primero.upload_id == segundo.upload_id
    assert len(mundo.storage.firmadas) == 2
    assert mundo.archivos.cupo[(WS_A, date(2026, 10, 1))] == 1
    assert len(mundo.archivos.filas) == 1


async def test_rechazado_se_reintenta_sobre_la_misma_fila(mundo: Mundo) -> None:
    rechazado = mundo.sembrar(estado=AttachmentFileStatus.REJECTED)

    resultado = await mundo.caso().execute(mundo.pedido())

    assert isinstance(resultado, UploadTicket)
    assert resultado.upload_id == rechazado.id
    assert mundo.archivos.filas[rechazado.id].status == AttachmentFileStatus.UPLOADING
    assert mundo.archivos.cupo == {}


async def test_tope_mensual(mundo: Mundo) -> None:
    await mundo.caso().execute(mundo.pedido(sha=_sha(b"uno")))
    await mundo.caso().execute(mundo.pedido(sha=_sha(b"dos")))

    with pytest.raises(UploadQuotaExceeded) as info:
        await mundo.caso().execute(mundo.pedido(sha=_sha(b"tres")))

    assert info.value.extra == {"used": 2, "limit": 2}
    assert len(mundo.archivos.filas) == 2


async def test_el_mes_del_tope_es_el_de_chile(mundo: Mundo) -> None:
    # 02:59 UTC del 1 de octubre todavía es septiembre en Chile (UTC-3).
    mundo.reloj = datetime(2026, 10, 1, 2, 59)
    await mundo.caso().execute(mundo.pedido(sha=_sha(b"uno")))
    await mundo.caso().execute(mundo.pedido(sha=_sha(b"dos")))
    assert mundo.archivos.cupo == {(WS_A, date(2026, 9, 1)): 2}
    with pytest.raises(UploadQuotaExceeded):
        await mundo.caso().execute(mundo.pedido(sha=_sha(b"tres")))

    # Un minuto después es octubre: el cupo se renovó.
    mundo.reloj = datetime(2026, 10, 1, 3, 0)
    await mundo.caso().execute(mundo.pedido(sha=_sha(b"tres")))

    assert mundo.archivos.cupo[(WS_A, date(2026, 10, 1))] == 1


async def test_mime_vacio(mundo: Mundo) -> None:
    await mundo.caso().execute(mundo.pedido(mime=""))

    assert mundo.storage.firmadas[0]["content_type"] == "application/octet-stream"
    [fila] = mundo.archivos.filas.values()
    assert fila.mime_declared is None
