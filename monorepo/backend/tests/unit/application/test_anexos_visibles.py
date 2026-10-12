"""Los anexos que una empresa ve de una licitación, con su nombre y tipo (plan 233)."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.application.services.anexos_visibles import anexos_visibles
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    InMemoryAttachmentFileRepository,
)

LICITACION = uuid4()
EMPRESA = uuid4()
AHORA = datetime(2026, 10, 12, 12, 0)


async def _anexo(
    oficiales: InMemoryTenderAttachmentRepository,
    archivos: InMemoryAttachmentFileRepository,
    nombre: str,
    *,
    workspace_id: UUID | None = EMPRESA,
    sha: str | None = None,
    estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
    creado: datetime = AHORA,
) -> AttachmentFile:
    oficial = await oficiales.create_attachment(LICITACION, uuid4(), nombre)
    compartido = workspace_id is None
    archivo = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=oficial.id,
        tender_id=LICITACION,
        sha256=sha or uuid4().hex * 2,
        size_bytes=10,
        storage_key=f"clave/{uuid4()}",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None if compartido else uuid4(),
        workspace_id=workspace_id,
        visibility=AttachmentVisibility.SHARED if compartido else AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.CORROBORATED if compartido else AttachmentTrust.PENDING,
        status=estado,
        created_at=creado,
    )
    archivos.filas[archivo.id] = archivo
    return archivo


async def test_trae_nombre_y_tipo_de_la_lista_oficial():
    oficiales, archivos = InMemoryTenderAttachmentRepository(), InMemoryAttachmentFileRepository()
    bases = await _anexo(oficiales, archivos, "Bases Técnicas.PDF")

    [anexo] = await anexos_visibles(archivos, oficiales, tender_id=LICITACION, workspace_id=EMPRESA)

    assert anexo.archivo.id == bases.id
    assert anexo.nombre == "Bases Técnicas.PDF"
    assert anexo.tipo == "pdf"
    assert anexo.legible


async def test_un_tipo_que_la_ia_no_lee_queda_marcado():
    oficiales, archivos = InMemoryTenderAttachmentRepository(), InMemoryAttachmentFileRepository()
    await _anexo(oficiales, archivos, "Formulario.docx")

    [anexo] = await anexos_visibles(archivos, oficiales, tender_id=LICITACION, workspace_id=EMPRESA)

    assert anexo.tipo == "docx"
    assert not anexo.legible


async def test_solo_los_guardados_y_de_esta_empresa_o_compartidos():
    oficiales, archivos = InMemoryTenderAttachmentRepository(), InMemoryAttachmentFileRepository()
    propio = await _anexo(oficiales, archivos, "propio.pdf")
    compartido = await _anexo(oficiales, archivos, "compartido.pdf", workspace_id=None)
    await _anexo(oficiales, archivos, "ajeno.pdf", workspace_id=uuid4())
    await _anexo(oficiales, archivos, "subiendo.pdf", estado=AttachmentFileStatus.UPLOADING)

    anexos = await anexos_visibles(archivos, oficiales, tender_id=LICITACION, workspace_id=EMPRESA)

    assert {a.archivo.id for a in anexos} == {propio.id, compartido.id}


async def test_el_mismo_archivo_privado_y_compartido_aparece_una_vez_y_gana_el_compartido():
    # Al promoverse, la copia privada y la canónica tienen el mismo contenido.
    oficiales, archivos = InMemoryTenderAttachmentRepository(), InMemoryAttachmentFileRepository()
    sha = "a" * 64
    await _anexo(oficiales, archivos, "bases.pdf", sha=sha)
    canonico = await _anexo(
        oficiales, archivos, "bases.pdf", workspace_id=None, sha=sha, creado=AHORA + timedelta(hours=1)
    )

    anexos = await anexos_visibles(archivos, oficiales, tender_id=LICITACION, workspace_id=EMPRESA)

    assert [a.archivo.id for a in anexos] == [canonico.id]
