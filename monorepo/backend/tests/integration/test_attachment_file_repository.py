"""Archivos de anexos y cupo mensual contra Postgres real (plan 233, decisión 2).

Lo que hay que proteger, y que un doble en memoria no puede probar:

- el cupo y la fila se escriben en **una sola transacción**: un choque con la
  clave única no cobra, y llegar al tope no deja fila;
- los CHECK y los `server_default` que describe la migración;
- el borrado en cascada (empresa) y el `SET NULL` (usuario).

`db_session` y el esquema limpio los aporta tests/integration/conftest.py, que
apunta a la base de test y no a la de desarrollo. Las sesiones de integración
usan `expire_on_commit=True`: no se lee un modelo después de un commit.
"""

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.infrastructure.repositories.models  # noqa: F401
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.errors.attachment_errors import (
    ConcurrentUploadConflict,
    UploadQuotaExceeded,
)
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.infrastructure.repositories.attachment_file_model import (
    AttachmentFileModel,
    AttachmentUploadQuotaModel,
)
from app.infrastructure.repositories.sql_attachment_file_repository import (
    SqlAttachmentFileRepository,
)
from app.infrastructure.repositories.sql_tender_attachment_repository import (
    SqlTenderAttachmentRepository,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.user_model import UserModel
from app.shared.regions import CHILE_REGIONS

pytestmark = pytest.mark.asyncio

AHORA = datetime(2026, 10, 3, 15, 0)
OCTUBRE = date(2026, 10, 1)
SEPTIEMBRE = date(2026, 9, 1)
SHA_A = "a" * 64
SHA_B = "b" * 64


class Mundo:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.ws_a = uuid4()
        self.ws_b = uuid4()
        self.tender_id = uuid4()
        self.anexo_id: UUID
        self.anexo2_id: UUID


async def _empresa(session: AsyncSession, supplier_id: UUID, rut: str) -> None:
    session.add(
        SupplierModel(
            id=supplier_id,
            rut=rut,
            legal_name=f"Empresa {rut}",
            created_at=AHORA,
            updated_at=AHORA,
        )
    )


async def sembrar(session: AsyncSession) -> Mundo:
    m = Mundo()
    session.add(
        UserModel(
            id=m.user_id,
            email="usuario@example.com",
            full_name="Usuario de Prueba",
            created_at=AHORA,
            updated_at=AHORA,
        )
    )
    await _empresa(session, m.ws_a, "76.086.428-5")
    await _empresa(session, m.ws_b, "96.511.130-7")
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=2, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="Municipalidad de Santiago",
            region_id=13,
            created_at=AHORA,
            updated_at=AHORA,
        )
    )
    session.add(
        TenderModel(
            id=m.tender_id,
            code="1057539-1-COT26",
            name="Materiales Eléctricos",
            description="Compra de cables y enchufes",
            status_id=2,
            published_at=AHORA,
            closing_at=AHORA + timedelta(hours=48),
            last_change_at=AHORA,
            buyer_rut="12.345.678-9",
            buyer_unit="Operaciones",
            available_amount_clp=500000.0,
            created_at=AHORA,
            updated_at=AHORA,
        )
    )
    await session.commit()
    await SqlTenderAttachmentRepository(session).sync_official_lists(
        {
            m.tender_id: [
                DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf"),
                DocumentoOficialDTO(mp_document_id=2, nombre="Anexo 1.docx"),
            ]
        },
        visto_en=AHORA,
    )
    lista = await SqlTenderAttachmentRepository(session).get_official_list(m.tender_id)
    assert lista is not None
    m.anexo_id, m.anexo2_id = (a.id for a in lista.attachments)
    return m


def archivo(
    m: Mundo,
    *,
    ws: UUID | None = None,
    sha: str = SHA_A,
    anexo: UUID | None = None,
    estado: AttachmentFileStatus = AttachmentFileStatus.UPLOADING,
    visibilidad: AttachmentVisibility = AttachmentVisibility.PRIVATE,
    clave: str | None = None,
) -> AttachmentFile:
    ws = ws or m.ws_a
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=anexo or m.anexo_id,
        tender_id=m.tender_id,
        sha256=sha,
        size_bytes=2048,
        mime_declared="application/pdf",
        storage_key=clave or f"private/{ws}/{sha}.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=m.user_id,
        workspace_id=ws,
        visibility=visibilidad,
        status=estado,
        created_at=AHORA,
        purge_after=AHORA + timedelta(hours=24),
    )


def canonico(
    m: Mundo,
    *,
    sha: str = SHA_A,
    estado: AttachmentFileStatus = AttachmentFileStatus.STORED,
    visibilidad: AttachmentVisibility = AttachmentVisibility.SHARED,
    confianza: AttachmentTrust = AttachmentTrust.CORROBORATED,
) -> AttachmentFile:
    """La versión compartida de un anexo: sin empresa ni autor (decisión 6)."""
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=m.anexo_id,
        tender_id=m.tender_id,
        sha256=sha,
        size_bytes=2048,
        storage_key=f"shared/{m.tender_id}/1/{sha}.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=visibilidad,
        trust=confianza,
        status=estado,
        created_at=AHORA,
    )


def _columnas(f: AttachmentFile) -> dict[str, object]:
    return {
        **f.model_dump(),
        "source": f.source.value,
        "visibility": f.visibility.value,
        "trust": f.trust.value,
        "status": f.status.value,
    }


async def contar(session: AsyncSession, modelo: type) -> int:
    return (await session.exec(select(func.count()).select_from(modelo))).one()


async def test_el_cupo_suma_por_empresa_y_mes(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)

    await repo.create_consuming_quota(archivo(m, sha=SHA_A), month=OCTUBRE, limit=10)
    await repo.create_consuming_quota(archivo(m, sha=SHA_B), month=OCTUBRE, limit=10)

    assert await repo.get_quota_used(workspace_id=m.ws_a, month=OCTUBRE) == 2
    assert await repo.get_quota_used(workspace_id=m.ws_a, month=SEPTIEMBRE) == 0
    assert await repo.get_quota_used(workspace_id=m.ws_b, month=OCTUBRE) == 0


async def test_al_tope_lanza_y_no_inserta(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create_consuming_quota(archivo(m, sha=SHA_A), month=OCTUBRE, limit=1)

    with pytest.raises(UploadQuotaExceeded) as info:
        await repo.create_consuming_quota(archivo(m, sha=SHA_B), month=OCTUBRE, limit=1)

    assert info.value.extra == {"used": 1, "limit": 1}
    assert await contar(db_session, AttachmentFileModel) == 1
    assert await repo.get_quota_used(workspace_id=m.ws_a, month=OCTUBRE) == 1


async def test_chocar_la_unica_no_gasta_cupo(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create_consuming_quota(archivo(m), month=OCTUBRE, limit=10)

    with pytest.raises(ConcurrentUploadConflict):
        await repo.create_consuming_quota(archivo(m), month=OCTUBRE, limit=10)

    assert await repo.get_quota_used(workspace_id=m.ws_a, month=OCTUBRE) == 1
    assert await contar(db_session, AttachmentFileModel) == 1


async def test_create_sin_cupo_tambien_traduce_el_choque(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(archivo(m))

    with pytest.raises(ConcurrentUploadConflict):
        await repo.create(archivo(m))

    assert await repo.get_quota_used(workspace_id=m.ws_a, month=OCTUBRE) == 0


async def test_visibles_no_incluyen_privados_ajenos_ni_purgados(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    propio = await repo.create(archivo(m, sha="1" * 64))
    compartido = await repo.create(canonico(m, sha="2" * 64))
    await repo.create(archivo(m, ws=m.ws_b, sha="3" * 64))  # privado ajeno
    await repo.create(archivo(m, sha="4" * 64, estado=AttachmentFileStatus.PURGED))

    visibles = await repo.list_visible_for_tender(tender_id=m.tender_id, workspace_id=m.ws_a)
    sin_empresa = await repo.list_visible_for_tender(tender_id=m.tender_id, workspace_id=None)

    assert {f.id for f in visibles} == {propio.id, compartido.id}
    assert {f.id for f in sin_empresa} == {compartido.id}


async def test_defaults_del_servidor(db_session: AsyncSession):
    m = await sembrar(db_session)
    file_id = uuid4()

    await db_session.execute(
        text(
            "INSERT INTO attachment_file (id, tender_attachment_id, tender_id, sha256, "
            "size_bytes, storage_key, source, workspace_id, status, created_at) "
            "VALUES (:id, :a, :t, :sha, 10, 'k', 'manual', :ws, 'uploading', :ahora)"
        ),
        {
            "id": file_id,
            "a": m.anexo_id,
            "t": m.tender_id,
            "sha": SHA_A,
            "ws": m.ws_a,
            "ahora": AHORA,
        },
    )
    await db_session.commit()

    fila = (
        await db_session.execute(
            text("SELECT visibility, trust FROM attachment_file WHERE id = :id"),
            {"id": file_id},
        )
    ).one()
    assert tuple(fila) == ("private", "pending")


async def test_check_rechaza_un_estado_desconocido(db_session: AsyncSession):
    m = await sembrar(db_session)
    db_session.add(AttachmentFileModel(**{**_columnas(archivo(m)), "status": "foo"}))

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_check_rechaza_un_sha256_mal_formado(db_session: AsyncSession):
    m = await sembrar(db_session)
    db_session.add(AttachmentFileModel(**{**_columnas(archivo(m)), "sha256": "XYZ"}))

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_borrar_el_usuario_deja_el_archivo_sin_autor(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    creado = await repo.create(archivo(m))

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": m.user_id})
    await db_session.commit()

    recuperado = await repo.get(creado.id)
    assert recuperado is not None
    assert recuperado.uploader_user_id is None


async def test_borrar_la_empresa_borra_archivos_y_cupo(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create_consuming_quota(archivo(m), month=OCTUBRE, limit=10)

    await db_session.execute(text("DELETE FROM supplier WHERE id = :id"), {"id": m.ws_a})
    await db_session.commit()

    assert await contar(db_session, AttachmentFileModel) == 0
    assert await contar(db_session, AttachmentUploadQuotaModel) == 0


async def test_find_stored_by_storage_key_y_referencias(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    clave = f"private/{m.ws_a}/{SHA_A}.pdf"
    guardado = await repo.create(
        archivo(m, anexo=m.anexo_id, estado=AttachmentFileStatus.STORED)
    )
    otro = await repo.create(
        archivo(m, anexo=m.anexo2_id, estado=AttachmentFileStatus.UPLOADING)
    )
    purgado = archivo(m, sha="9" * 64, clave=clave, estado=AttachmentFileStatus.PURGED)
    await repo.create(purgado)

    encontrado = await repo.find_stored_by_storage_key(clave)

    assert encontrado is not None
    assert encontrado.id == guardado.id
    assert await repo.find_stored_by_storage_key("private/x/y") is None
    # Cuenta las otras filas no purgadas con la misma clave (el purgado no cuenta).
    assert await repo.count_other_references(storage_key=clave, excluding_id=guardado.id) == 1
    assert await repo.count_other_references(storage_key=clave, excluding_id=otro.id) == 1
    assert (
        await repo.count_other_references(storage_key=clave, excluding_id=uuid4()) == 2
    )


async def test_busquedas_por_empresa_y_compartidos(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    propio = await repo.create(archivo(m, sha=SHA_A))
    compartido = await repo.create(canonico(m, sha=SHA_B))
    privado_ajeno = await repo.create(
        archivo(m, ws=m.ws_b, sha="c" * 64, estado=AttachmentFileStatus.STORED)
    )

    por_empresa = await repo.find_for_workspace(
        tender_attachment_id=m.anexo_id, sha256=SHA_A, workspace_id=m.ws_a
    )
    assert por_empresa is not None and por_empresa.id == propio.id
    assert (
        await repo.find_for_workspace(
            tender_attachment_id=m.anexo_id, sha256=SHA_A, workspace_id=m.ws_b
        )
        is None
    )

    shared = await repo.find_shared_stored(tender_attachment_id=m.anexo_id, sha256=SHA_B)
    assert shared is not None and shared.id == compartido.id
    # Un privado de otra empresa nunca cuenta como compartido.
    assert (
        await repo.find_shared_stored(tender_attachment_id=m.anexo_id, sha256="c" * 64)
        is None
    )
    assert privado_ajeno.workspace_id == m.ws_b

    propias = await repo.list_for_workspace_attachment(
        tender_attachment_id=m.anexo_id, workspace_id=m.ws_a
    )
    assert [f.id for f in propias] == [propio.id]


async def test_update_y_delete(db_session: AsyncSession):
    m = await sembrar(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    creado = await repo.create(archivo(m))

    guardado = await repo.update(creado.como_guardado(ahora=AHORA))

    recuperado = await repo.get(creado.id)
    assert recuperado == guardado
    assert recuperado is not None
    assert recuperado.status == AttachmentFileStatus.STORED
    assert recuperado.purge_after is None
    assert recuperado.completed_at == AHORA

    await repo.delete(creado.id)

    assert await repo.get(creado.id) is None
