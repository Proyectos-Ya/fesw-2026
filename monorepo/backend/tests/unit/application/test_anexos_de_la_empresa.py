"""Los anexos que lee la postulación (plan 233, parte 2)."""

from datetime import datetime
from uuid import UUID, uuid4

from app.application.services.document_validator_service import (
    DocumentValidationResult,
    IDocumentValidatorService,
)
from app.application.use_cases.proposals._documentos import anexos_de_la_empresa
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
)

LICITACION = uuid4()
EMPRESA = uuid4()


class RechazaPorNombre(IDocumentValidatorService):
    def __init__(self, nombre: str) -> None:
        self.nombre = nombre

    def validate_integrity(self, file_bytes, file_name, declared_type=None):
        valido = file_name != self.nombre
        return DocumentValidationResult(
            is_valid=valido, file_type=declared_type or "pdf", error_message=None
        )


class Anexos:
    def __init__(self) -> None:
        self.archivos = InMemoryAttachmentFileRepository()
        self.oficiales = InMemoryTenderAttachmentRepository()
        self.almacen = FakeAttachmentStorage()

    async def subir(
        self, nombre: str, *, workspace_id: UUID | None = EMPRESA, contenido: bytes | None = b"%PDF"
    ) -> None:
        oficial = await self.oficiales.create_attachment(LICITACION, uuid4(), nombre)
        compartido = workspace_id is None
        archivo = AttachmentFile(
            id=uuid4(),
            tender_attachment_id=oficial.id,
            tender_id=LICITACION,
            sha256=uuid4().hex * 2,
            size_bytes=4,
            storage_key=f"anexos/{uuid4()}",
            source=AttachmentFileSource.MANUAL,
            uploader_user_id=None if compartido else uuid4(),
            workspace_id=workspace_id,
            visibility=AttachmentVisibility.SHARED if compartido else AttachmentVisibility.PRIVATE,
            trust=AttachmentTrust.CORROBORATED if compartido else AttachmentTrust.PENDING,
            status=AttachmentFileStatus.STORED,
            created_at=datetime(2026, 10, 12, 12, 0),
        )
        self.archivos.filas[archivo.id] = archivo
        if contenido is not None:
            self.almacen.subir(archivo.storage_key, contenido)

    async def leer(self, validator: IDocumentValidatorService | None = None):
        return await anexos_de_la_empresa(
            self.archivos,
            self.oficiales,
            self.almacen,
            validator,
            tender_id=LICITACION,
            workspace_id=EMPRESA,
        )


async def test_devuelve_los_anexos_de_la_empresa_y_los_compartidos():
    anexos = Anexos()
    await anexos.subir("Bases Administrativas.pdf")
    await anexos.subir("Bases Técnicas.pdf", workspace_id=None)
    await anexos.subir("de-otra-empresa.pdf", workspace_id=uuid4())

    documentos = await anexos.leer()

    assert sorted(d.document_name for d in documentos) == [
        "Bases Administrativas.pdf",
        "Bases Técnicas.pdf",
    ]
    assert all(d.file_bytes == b"%PDF" and not d.is_corrupted for d in documentos)
    assert {d.file_type for d in documentos} == {"pdf"}


async def test_un_anexo_que_no_se_puede_leer_va_marcado_como_daniado():
    anexos = Anexos()
    await anexos.subir("bases.pdf", contenido=None)

    [documento] = await anexos.leer()

    assert documento.is_corrupted is True
    assert documento.file_bytes == b""


async def test_un_anexo_que_el_validador_rechaza_va_marcado_como_daniado():
    anexos = Anexos()
    await anexos.subir("bases.pdf")
    await anexos.subir("roto.pdf")

    documentos = await anexos.leer(RechazaPorNombre("roto.pdf"))

    estado = {d.document_name: d.is_corrupted for d in documentos}
    assert estado == {"bases.pdf": False, "roto.pdf": True}


async def test_un_tipo_que_la_ia_no_lee_igual_se_pasa():
    # El servicio de la postulación decide qué mandar; acá no se filtra.
    anexos = Anexos()
    await anexos.subir("Formulario.docx")

    [documento] = await anexos.leer()

    assert documento.file_type == "docx"
    assert documento.is_corrupted is False
