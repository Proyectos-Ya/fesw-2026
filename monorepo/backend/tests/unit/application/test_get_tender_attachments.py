"""Lo que ve quien abre la ficha: la lista oficial de anexos y su estado.

`list_synced_at` nulo no es lo mismo que "sin anexos": significa que la lista
todavía no se sincronizó con Mercado Público, y la interfaz lo dice distinto.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.tender_attachments.get_tender_attachments import (
    GetTenderAttachmentsUseCase,
    UploadQuota,
    WorkspaceAccess,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.attachment_processing import (
    EstadoDeExtraccion,
    ProcessingState,
)
from app.domain.entities.tender_attachment import AttachmentStatus
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    InMemoryAttachmentFileRepository,
    canonico,
)

T1 = datetime(2026, 9, 28, 16, 0)
T2 = datetime(2026, 9, 28, 17, 0)
AHORA = datetime(2026, 10, 3, 15, 0)
WS = uuid4()
OTRA = uuid4()


def _caso(
    repo: InMemoryTenderAttachmentRepository,
    archivos: InMemoryAttachmentFileRepository | None = None,
    **kw,
) -> GetTenderAttachmentsUseCase:
    return GetTenderAttachmentsUseCase(
        repo,
        archivos or InMemoryAttachmentFileRepository(),
        uploads_per_month=kw.pop("uploads_per_month", 100),
        storage_available=kw.pop("storage_available", True),
        clock=lambda: AHORA,
        **kw,
    )


async def _con_un_anexo() -> tuple[InMemoryTenderAttachmentRepository, UUID, UUID]:
    tender_id = uuid4()
    repo = InMemoryTenderAttachmentRepository({"A": tender_id})
    await repo.sync_official_lists(
        {tender_id: [DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")]},
        visto_en=T1,
    )
    return repo, tender_id, repo.filas[(tender_id, 1)].id


def _archivo(
    tender_id: UUID,
    attachment_id: UUID,
    *,
    ws: UUID = WS,
    visibilidad: AttachmentVisibility = AttachmentVisibility.PRIVATE,
    estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
) -> AttachmentFile:
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=attachment_id,
        tender_id=tender_id,
        sha256="0" * 64,
        size_bytes=2048,
        storage_key=f"private/{ws}/{'0' * 64}.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=ws,
        visibility=visibilidad,
        status=estado,
        created_at=AHORA,
    )


async def test_una_licitacion_con_lista_devuelve_cada_anexo_como_faltante():
    tender_id = uuid4()
    repo = InMemoryTenderAttachmentRepository({"A": tender_id})
    await repo.sync_official_lists(
        {
            tender_id: [
                DocumentoOficialDTO(mp_document_id=2, nombre="Anexo 1.docx"),
                DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf"),
            ]
        },
        visto_en=T1,
    )

    resultado = await _caso(repo).execute(tender_id)

    assert [v.attachment.name for v in resultado.official] == ["Bases.pdf", "Anexo 1.docx"]
    assert {v.status for v in resultado.official} == {AttachmentStatus.MISSING}
    assert {v.file for v in resultado.official} == {None}
    assert resultado.list_synced_at == T1
    assert resultado.quota is None
    assert resultado.can_upload is False


async def test_los_retirados_quedan_fuera():
    tender_id = uuid4()
    repo = InMemoryTenderAttachmentRepository({"A": tender_id})
    doc1 = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")
    doc2 = DocumentoOficialDTO(mp_document_id=2, nombre="Anexo 1.docx")
    await repo.sync_official_lists({tender_id: [doc1, doc2]}, visto_en=T1)
    await repo.sync_official_lists({tender_id: [doc1]}, visto_en=T2)

    resultado = await _caso(repo).execute(tender_id)

    assert [v.attachment.mp_document_id for v in resultado.official] == [1]
    assert resultado.list_synced_at == T2


async def test_una_licitacion_existente_sin_sincronizar_no_tiene_lista_ni_fecha():
    tender_id = uuid4()
    repo = InMemoryTenderAttachmentRepository({"A": tender_id})

    resultado = await _caso(repo).execute(tender_id)

    assert resultado.official == []
    assert resultado.list_synced_at is None


async def test_una_licitacion_inexistente_lanza_tender_not_found():
    repo = InMemoryTenderAttachmentRepository({"A": uuid4()})

    with pytest.raises(TenderNotFound):
        await _caso(repo).execute(uuid4())


async def test_el_archivo_propio_guardado_marca_el_anexo_como_subido():
    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    propio = _archivo(tender_id, anexo_id)
    archivos.filas[propio.id] = propio

    resultado = await _caso(repo, archivos).execute(
        tender_id, access=WorkspaceAccess(WS, can_upload=True)
    )

    [vista] = resultado.official
    assert vista.status == AttachmentStatus.STORED
    assert vista.file is not None
    assert vista.file.file == propio
    assert vista.file.is_mine is True


async def test_el_privado_de_otra_empresa_no_se_ve():
    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    ajeno = _archivo(tender_id, anexo_id, ws=OTRA)
    archivos.filas[ajeno.id] = ajeno

    resultado = await _caso(repo, archivos).execute(
        tender_id, access=WorkspaceAccess(WS, can_upload=True)
    )

    [vista] = resultado.official
    assert vista.status == AttachmentStatus.MISSING
    assert vista.file is None


async def test_el_compartido_de_otra_empresa_se_ve_pero_no_es_mio():
    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    compartido = canonico(tender_attachment_id=anexo_id, tender_id=tender_id, sha256="0" * 64)
    archivos.filas[compartido.id] = compartido

    resultado = await _caso(repo, archivos).execute(
        tender_id, access=WorkspaceAccess(WS, can_upload=True)
    )

    [vista] = resultado.official
    assert vista.status == AttachmentStatus.STORED
    assert vista.file is not None
    assert vista.file.is_mine is False


async def test_sin_empresa_la_canonica_no_es_mia():
    # Regresión: la canónica no tiene empresa y quien mira sin empresa tampoco, y
    # `None == None` la volvería "propia".
    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    compartido = canonico(tender_attachment_id=anexo_id, tender_id=tender_id, sha256="0" * 64)
    archivos.filas[compartido.id] = compartido

    resultado = await _caso(repo, archivos).execute(tender_id)

    [vista] = resultado.official
    assert vista.status == AttachmentStatus.STORED
    assert vista.file is not None
    assert vista.file.is_mine is False


async def test_una_canonica_oculta_no_aparece():
    # Suspendida por un conflicto: sin empresa, pero privada. Nadie la ve.
    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    oculta = canonico(
        tender_attachment_id=anexo_id,
        tender_id=tender_id,
        sha256="0" * 64,
        visibility=AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.CONFLICT,
    )
    archivos.filas[oculta.id] = oculta

    for acceso in (None, WorkspaceAccess(WS, can_upload=True)):
        [vista] = (await _caso(repo, archivos).execute(tender_id, access=acceso)).official
        assert vista.status == AttachmentStatus.MISSING
        assert vista.file is None


async def test_sin_empresa_solo_se_ven_los_compartidos():
    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    propio = _archivo(tender_id, anexo_id)
    archivos.filas[propio.id] = propio

    resultado = await _caso(repo, archivos).execute(tender_id)

    assert resultado.official[0].file is None
    assert resultado.quota is None


async def test_el_cupo_es_el_del_mes_de_chile():
    repo, tender_id, _ = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    archivos.cupo[(WS, date(2026, 10, 1))] = 1
    archivos.cupo[(WS, date(2026, 9, 1))] = 40

    resultado = await _caso(repo, archivos).execute(
        tender_id, access=WorkspaceAccess(WS, can_upload=True)
    )

    assert resultado.quota == UploadQuota(used=1, limit=100)


@pytest.mark.parametrize(
    ("can_upload", "storage_available", "esperado"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
async def test_puede_subir_solo_con_permiso_y_almacenamiento(
    can_upload: bool, storage_available: bool, esperado: bool
):
    repo, tender_id, _ = await _con_un_anexo()

    resultado = await _caso(repo, storage_available=storage_available).execute(
        tender_id, access=WorkspaceAccess(WS, can_upload=can_upload)
    )

    assert resultado.can_upload is esperado


async def test_el_maximo_de_subida_son_50_mb():
    repo, tender_id, _ = await _con_un_anexo()

    resultado = await _caso(repo).execute(tender_id)

    assert resultado.max_upload_size_bytes == 52428800


class _FakeStatusReader:
    def __init__(self, states: dict[UUID, EstadoDeExtraccion] | None = None) -> None:
        self.states = dict(states or {})
        self.received_ids: list[list[UUID]] = []

    async def extraction_states(
        self, file_ids: list[UUID], *, prompt_version: str
    ) -> dict[UUID, EstadoDeExtraccion]:
        self.received_ids.append(list(file_ids))
        return {
            fid: self.states.get(
                fid, EstadoDeExtraccion(extraida=False, fallida=False)
            )
            for fid in file_ids
        }

    async def pending_count(
        self, *, tender_id: UUID, workspace_id: UUID | None, prompt_version: str
    ) -> int:
        return 0


async def test_processing_estados_segun_senial():
    from app.domain.entities.attachment_processing import (
        EstadoDeExtraccion,
        ProcessingState,
    )

    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()

    # Archivo STORED
    f_ready = canonico(
        tender_attachment_id=anexo_id,
        tender_id=tender_id,
        sha256="1" * 64,
    )
    archivos.filas[f_ready.id] = f_ready

    reader = _FakeStatusReader(
        {f_ready.id: EstadoDeExtraccion(extraida=True, fallida=False)}
    )
    res = await _caso(
        repo, archivos, processing=reader, processing_enabled=True
    ).execute(tender_id)
    assert res.processing_enabled is True
    assert res.official[0].processing == ProcessingState.READY

    # FAILED
    reader.states[f_ready.id] = EstadoDeExtraccion(extraida=False, fallida=True)
    res = await _caso(repo, archivos, processing=reader).execute(tender_id)
    assert res.official[0].processing == ProcessingState.FAILED

    # PROCESSING (sin senal extraida ni fallida)
    reader.states[f_ready.id] = EstadoDeExtraccion(
        extraida=False, fallida=False
    )
    res = await _caso(repo, archivos, processing=reader).execute(tender_id)
    assert res.official[0].processing == ProcessingState.PROCESSING

    # UNSUPPORTED
    f_unsupported = f_ready.model_copy(
        update={"status": AttachmentFileStatus.UNSUPPORTED}
    )
    archivos.filas[f_ready.id] = f_unsupported
    res = await _caso(repo, archivos, processing=reader).execute(tender_id)
    assert res.official[0].processing == ProcessingState.UNSUPPORTED


async def test_uploading_da_none_en_processing():
    from app.domain.entities.attachment_processing import EstadoDeExtraccion

    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    f_uploading = canonico(
        tender_attachment_id=anexo_id,
        tender_id=tender_id,
        sha256="2" * 64,
    ).model_copy(update={"status": AttachmentFileStatus.UPLOADING})
    archivos.filas[f_uploading.id] = f_uploading

    reader = _FakeStatusReader()
    res = await _caso(repo, archivos, processing=reader).execute(tender_id)
    assert res.official[0].processing is None


async def test_processing_recibe_solo_ids_elegidos_y_no_privados_ajenos():
    from app.domain.entities.attachment_processing import EstadoDeExtraccion

    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()

    # Archivo privado de OTRA empresa
    f_ajeno = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=anexo_id,
        tender_id=tender_id,
        sha256="3" * 64,
        size_bytes=100,
        storage_key="k",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=OTRA,
        visibility=AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.PENDING,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )
    archivos.filas[f_ajeno.id] = f_ajeno

    reader = _FakeStatusReader()
    res = await _caso(repo, archivos, processing=reader).execute(
        tender_id, access=WorkspaceAccess(WS, can_upload=True)
    )
    assert res.official[0].file is None
    assert res.official[0].processing is None
    # No se paso f_ajeno al reader
    assert reader.received_ids == []


async def test_sin_lector_processing_queda_en_none():
    repo, tender_id, anexo_id = await _con_un_anexo()
    archivos = InMemoryAttachmentFileRepository()
    f = canonico(
        tender_attachment_id=anexo_id,
        tender_id=tender_id,
        sha256="4" * 64,
    )
    archivos.filas[f.id] = f

    res = await _caso(repo, archivos, processing=None).execute(tender_id)
    assert res.official[0].processing is None
    assert res.processing_enabled is False

