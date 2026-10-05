"""La promoción de anexos compartidos contra Postgres real (plan 233, decisión 6).

Lo que hay que proteger, y que un doble en memoria no puede probar:

- el candado `FOR NO KEY UPDATE` serializa dos promociones del mismo anexo y, a
  diferencia de `FOR UPDATE`, no frena el INSERT de una subida nueva;
- los CHECK y los únicos parciales impiden publicar una fila de empresa o dejar dos
  versiones compartidas;
- borrar una empresa o a un autor no alcanza a lo compartido;
- dos `complete` simultáneos de empresas distintas terminan en una sola versión
  compartida, en cualquier intercalado.

`db_session` y el esquema limpio los aporta tests/integration/conftest.py (base de
test). Las sesiones de integración usan `expire_on_commit=True`: no se lee un modelo
después de un commit.
"""

import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.infrastructure.repositories.models  # noqa: F401
from app.application.services.attachment_stored_listener import (
    CompositeAttachmentStoredListener,
)
from app.application.services.attachment_visibility_listener import (
    NoopAttachmentVisibilityListener,
)
from app.application.use_cases.tender_attachments.complete_attachment_upload import (
    CompleteAttachmentUploadUseCase,
)
from app.application.use_cases.tender_attachments.promote_attachment import (
    AttachmentPromotionListener,
    PromoteAttachmentUseCase,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.infrastructure.repositories.attachment_file_model import AttachmentFileModel
from app.infrastructure.repositories.sql_attachment_file_repository import (
    SqlAttachmentFileRepository,
)
from app.infrastructure.repositories.sql_attachment_trust_repository import (
    SqlAttachmentTrustRepository,
)
from tests.integration.attachment_seed import (
    MundoAnexo,
    aporte,
    canonica,
    sembrar_anexo,
    sembrar_empresa,
)
from tests.unit.application.attachment_file_fakes import FakeAttachmentStorage

pytestmark = pytest.mark.asyncio

HOLA = b"hola"
S1 = hashlib.sha256(HOLA).hexdigest()
S2 = hashlib.sha256(b"chao").hexdigest()
RUT_1, RUT_2, RUT_3 = "76.000.001-1", "76.000.002-2", "76.000.003-3"
OCTUBRE = date(2026, 10, 1)


def caso(session: AsyncSession, storage: FakeAttachmentStorage) -> PromoteAttachmentUseCase:
    return PromoteAttachmentUseCase(
        trust=SqlAttachmentTrustRepository(session),
        storage=storage,
        visibility_listener=NoopAttachmentVisibilityListener(),
    )


async def sembrar_dos_aportes(
    session: AsyncSession, storage: FakeAttachmentStorage
) -> tuple[MundoAnexo, UUID, UUID, UUID, UUID]:
    """Dos empresas independientes con el mismo archivo ya guardado (aún sin evaluar)."""
    m = await sembrar_anexo(session)
    w1, u1 = await sembrar_empresa(session, RUT_1)
    w2, u2 = await sembrar_empresa(session, RUT_2)
    repo = SqlAttachmentFileRepository(session)
    for empresa, autor in ((w1, u1), (w2, u2)):
        await repo.create(aporte(m, empresa, autor, sha=S1))
        storage.subir(f"private/{empresa}/{S1}.xlsx", HOLA)
    return m, w1, u1, w2, u2


async def filas(session: AsyncSession) -> list[AttachmentFileModel]:
    session.expire_all()
    return list((await session.exec(select(AttachmentFileModel))).all())


@asynccontextmanager
async def sesion(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(engine) as s:
        yield s


# --- Lectura bajo candado ---


async def test_el_candado_trae_filas_y_personas(db_session: AsyncSession):
    m = await sembrar_anexo(db_session)
    u2 = uuid4()
    w1, u1 = await sembrar_empresa(db_session, RUT_1, miembros={u2: "inactive"})
    w2, u3 = await sembrar_empresa(db_session, RUT_2)
    repo = SqlAttachmentFileRepository(db_session)
    a1 = await repo.create(aporte(m, w1, u1, sha=S1))
    a2 = await repo.create(aporte(m, w2, u3, sha=S1))
    purgado = await repo.create(aporte(m, w2, u3, sha=S2, estado=AttachmentFileStatus.PURGED))

    trust = SqlAttachmentTrustRepository(db_session)
    foto = await trust.lock_for_promotion(m.attachment_id)

    assert foto is not None
    assert foto.attachment.id == m.attachment_id
    assert {f.id for f in foto.files} == {a1.id, a2.id}
    assert purgado.id not in {f.id for f in foto.files}
    # Dueño legado y membresías en cualquier estado, también la revocada.
    assert foto.people == {w1: frozenset({u1, u2}), w2: frozenset({u3})}
    await trust.release()


async def test_un_anexo_inexistente_devuelve_none(db_session: AsyncSession):
    trust = SqlAttachmentTrustRepository(db_session)

    assert await trust.lock_for_promotion(uuid4()) is None
    await trust.release()


# --- Promover ---


async def test_dos_empresas_comparten_en_una_fila_sin_empresa(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    storage = FakeAttachmentStorage()
    m, w1, _, w2, _ = await sembrar_dos_aportes(db_session, storage)

    resultado = await caso(db_session, storage).execute(m.attachment_id)

    assert resultado.shared is not None
    async with sesion(integration_engine) as s:
        todas = await filas(s)
        [comp] = [f for f in todas if f.workspace_id is None]
        assert comp.id == resultado.shared.id
        assert comp.uploader_user_id is None
        assert comp.visibility == "shared"
        assert comp.trust == "corroborated"
        assert comp.status == "stored"
        assert comp.storage_key.startswith("shared/")
        aportes = [f for f in todas if f.workspace_id is not None]
        assert {f.workspace_id for f in aportes} == {w1, w2}
        assert {(f.trust, f.visibility) for f in aportes} == {("corroborated", "private")}
        clave = comp.storage_key
    assert storage.objetos[clave] == HOLA


# --- Invariantes de la base ---


async def test_el_check_impide_compartir_una_fila_de_empresa(db_session: AsyncSession):
    storage = FakeAttachmentStorage()
    await sembrar_dos_aportes(db_session, storage)
    [primera, *_] = await filas(db_session)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "UPDATE attachment_file SET visibility = 'shared', trust = 'corroborated' "
                "WHERE id = :id"
            ),
            {"id": primera.id},
        )
    await db_session.rollback()


async def test_el_check_impide_compartir_lo_no_corroborado(db_session: AsyncSession):
    m = await sembrar_anexo(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(canonica(m, sha=S1))

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE attachment_file SET trust = 'pending' WHERE workspace_id IS NULL")
        )
    await db_session.rollback()


async def test_el_check_impide_una_canonica_con_autor(db_session: AsyncSession):
    m = await sembrar_anexo(db_session)
    _, dueno = await sembrar_empresa(db_session, RUT_1)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(canonica(m, sha=S1, visibilidad=AttachmentVisibility.PRIVATE))

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE attachment_file SET uploader_user_id = :u WHERE workspace_id IS NULL"),
            {"u": dueno},
        )
    await db_session.rollback()


async def test_solo_una_version_compartida_por_anexo(db_session: AsyncSession):
    m = await sembrar_anexo(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(canonica(m, sha=S1))

    with pytest.raises(IntegrityError):
        await repo.create(canonica(m, sha=S2))
    await db_session.rollback()


async def test_una_sola_canonica_por_version(db_session: AsyncSession):
    # La UQ (anexo, sha, empresa) no alcanza a las filas sin empresa: NULL != NULL.
    m = await sembrar_anexo(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(canonica(m, sha=S1, visibilidad=AttachmentVisibility.PRIVATE))

    with pytest.raises(IntegrityError):
        await repo.create(canonica(m, sha=S1, visibilidad=AttachmentVisibility.PRIVATE))
    await db_session.rollback()


async def test_guardar_oculta_antes_de_mostrar(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    m = await sembrar_anexo(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    s1 = await repo.create(canonica(m, sha=S1))
    s2 = await repo.create(
        canonica(
            m, sha=S2, visibilidad=AttachmentVisibility.PRIVATE, trust=AttachmentTrust.REJECTED
        )
    )
    trust = SqlAttachmentTrustRepository(db_session)
    await trust.lock_for_promotion(m.attachment_id)

    # A propósito en el orden que rompería el único parcial si se aplicara tal cual.
    await trust.save_promotion(
        updated=[
            s2.model_copy(
                update={
                    "visibility": AttachmentVisibility.SHARED,
                    "trust": AttachmentTrust.CORROBORATED,
                }
            ),
            s1.model_copy(
                update={
                    "visibility": AttachmentVisibility.PRIVATE,
                    "trust": AttachmentTrust.REJECTED,
                }
            ),
        ],
        created=[],
    )

    async with sesion(integration_engine) as s:
        visibles = [f for f in await filas(s) if f.visibility == "shared"]
    assert [f.id for f in visibles] == [s2.id]


async def test_guardar_no_pisa_el_status(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    # La decisión 4 puede marcar `unsupported`: la promoción solo toca trust y visibility.
    m = await sembrar_anexo(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    s1 = await repo.create(canonica(m, sha=S1, visibilidad=AttachmentVisibility.PRIVATE))
    await db_session.execute(
        text("UPDATE attachment_file SET status = 'unsupported' WHERE id = :id"), {"id": s1.id}
    )
    await db_session.commit()
    trust = SqlAttachmentTrustRepository(db_session)
    await trust.lock_for_promotion(m.attachment_id)

    await trust.save_promotion(
        updated=[s1.model_copy(update={"visibility": AttachmentVisibility.SHARED})],
        created=[],
    )

    async with sesion(integration_engine) as s:
        [fila] = await filas(s)
    assert (fila.status, fila.visibility) == ("unsupported", "shared")


# --- Borrados ---


async def test_borrar_la_empresa_no_borra_lo_compartido(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    storage = FakeAttachmentStorage()
    m, w1, _, w2, _ = await sembrar_dos_aportes(db_session, storage)
    w3, _ = await sembrar_empresa(db_session, RUT_3)
    await caso(db_session, storage).execute(m.attachment_id)

    for empresa in (w1, w2):
        await db_session.execute(text("DELETE FROM supplier WHERE id = :id"), {"id": empresa})
        await db_session.commit()
        async with sesion(integration_engine) as s:
            todas = await filas(s)
        assert empresa not in {f.workspace_id for f in todas}
        [comp] = [f for f in todas if f.workspace_id is None]
        assert comp.visibility == "shared"

    async with sesion(integration_engine) as s:
        repo = SqlAttachmentFileRepository(s)
        para_w3 = await repo.list_visible_for_tender(tender_id=m.tender_id, workspace_id=w3)
        sin_empresa = await repo.list_visible_for_tender(tender_id=m.tender_id, workspace_id=None)
    assert [f.workspace_id for f in para_w3] == [None]
    assert [f.id for f in sin_empresa] == [f.id for f in para_w3]


async def test_borrar_al_autor_no_toca_lo_compartido(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    storage = FakeAttachmentStorage()
    m = await sembrar_anexo(db_session)
    u2 = uuid4()
    w1, u1 = await sembrar_empresa(db_session, RUT_1)
    w2, _ = await sembrar_empresa(db_session, RUT_2, miembros={u2: "active"})
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(aporte(m, w1, u1, sha=S1))
    aporte_w2 = await repo.create(aporte(m, w2, u2, sha=S1))
    for empresa in (w1, w2):
        storage.subir(f"private/{empresa}/{S1}.xlsx", HOLA)
    await caso(db_session, storage).execute(m.attachment_id)

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": u2})
    await db_session.commit()

    async with sesion(integration_engine) as s:
        todas = {f.id: f for f in await filas(s)}
    assert todas[aporte_w2.id].uploader_user_id is None
    [comp] = [f for f in todas.values() if f.workspace_id is None]
    assert (comp.visibility, comp.trust, comp.uploader_user_id) == (
        "shared",
        "corroborated",
        None,
    )


async def test_lista_sin_empresa_no_trae_canonicas_ocultas(db_session: AsyncSession):
    m = await sembrar_anexo(db_session)
    repo = SqlAttachmentFileRepository(db_session)
    await repo.create(
        canonica(
            m, sha=S1, visibilidad=AttachmentVisibility.PRIVATE, trust=AttachmentTrust.CONFLICT
        )
    )
    w1, _ = await sembrar_empresa(db_session, RUT_1)

    # `workspace_id IS NULL` las traería: tiene que filtrar solo por visibility.
    assert await repo.list_visible_for_tender(tender_id=m.tender_id, workspace_id=None) == []
    assert await repo.list_visible_for_tender(tender_id=m.tender_id, workspace_id=w1) == []
    assert await repo.find_shared_stored(tender_attachment_id=m.attachment_id, sha256=S1) is None


async def test_una_canonica_no_gasta_cupo(db_session: AsyncSession):
    m = await sembrar_anexo(db_session)
    repo = SqlAttachmentFileRepository(db_session)

    with pytest.raises(ValueError):
        await repo.create_consuming_quota(canonica(m, sha=S1), month=OCTUBRE, limit=10)


# --- Concurrencia ---


async def test_la_promocion_espera_al_candado(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    storage = FakeAttachmentStorage()
    m, *_ = await sembrar_dos_aportes(db_session, storage)
    async with sesion(integration_engine) as sa, sesion(integration_engine) as sb:
        repo_a = SqlAttachmentTrustRepository(sa)
        await repo_a.lock_for_promotion(m.attachment_id)

        tarea = asyncio.create_task(caso(sb, storage).execute(m.attachment_id))
        await asyncio.sleep(0.5)
        assert not tarea.done()

        await repo_a.release()
        resultado = await asyncio.wait_for(tarea, 10)

    assert resultado.shared is not None


async def test_el_candado_no_frena_una_subida_nueva(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    # Justifica FOR NO KEY UPDATE frente a FOR UPDATE: la FK de la fila nueva pide
    # FOR KEY SHARE sobre el anexo, que es compatible con el primero.
    storage = FakeAttachmentStorage()
    m, *_ = await sembrar_dos_aportes(db_session, storage)
    w3, u3 = await sembrar_empresa(db_session, RUT_3)
    async with sesion(integration_engine) as sa, sesion(integration_engine) as sb:
        repo_a = SqlAttachmentTrustRepository(sa)
        await repo_a.lock_for_promotion(m.attachment_id)

        await asyncio.wait_for(
            SqlAttachmentFileRepository(sb).create(aporte(m, w3, u3, sha=S2)), 3
        )

        await repo_a.release()


async def test_dos_promociones_simultaneas_crean_una_sola_version(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    storage = FakeAttachmentStorage()
    m, *_ = await sembrar_dos_aportes(db_session, storage)
    async with sesion(integration_engine) as sa, sesion(integration_engine) as sb:
        r1, r2 = await asyncio.wait_for(
            asyncio.gather(
                caso(sa, storage).execute(m.attachment_id),
                caso(sb, storage).execute(m.attachment_id),
            ),
            20,
        )

    async with sesion(integration_engine) as s:
        canonicas = (
            await s.exec(
                select(func.count())
                .select_from(AttachmentFileModel)
                .where(col(AttachmentFileModel.workspace_id).is_(None))
            )
        ).one()
    assert canonicas == 1
    assert len(storage.copias) == 1
    assert r1.shared is not None and r2.shared is not None
    assert r1.shared.id == r2.shared.id


async def test_dos_complete_simultaneos_de_empresas_distintas(
    db_session: AsyncSession, integration_engine: AsyncEngine
):
    storage = FakeAttachmentStorage()
    m = await sembrar_anexo(db_session)
    w1, u1 = await sembrar_empresa(db_session, RUT_1)
    w2, u2 = await sembrar_empresa(db_session, RUT_2)
    repo = SqlAttachmentFileRepository(db_session)
    subidas: list[tuple[AttachmentFile, UUID]] = []
    for empresa, autor in ((w1, u1), (w2, u2)):
        fila = await repo.create(
            aporte(m, empresa, autor, sha=S1, estado=AttachmentFileStatus.UPLOADING)
        )
        subidas.append((fila, empresa))
        storage.subir(fila.storage_key, HOLA)
    fabrica = async_sessionmaker(integration_engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def abrir() -> AsyncIterator[PromoteAttachmentUseCase]:
        # Sesión propia, como en producción (`build_promotion_opener`).
        async with fabrica() as s:
            yield caso(s, storage)

    listener = CompositeAttachmentStoredListener([AttachmentPromotionListener(abrir)])

    async def completar(subida: AttachmentFile, empresa: UUID) -> AttachmentFile:
        async with fabrica() as s:
            return await CompleteAttachmentUploadUseCase(
                files=SqlAttachmentFileRepository(s), storage=storage, listener=listener
            ).execute(tender_id=m.tender_id, upload_id=subida.id, workspace_id=empresa)

    await asyncio.wait_for(asyncio.gather(*(completar(f, e) for f, e in subidas)), 30)

    async with sesion(integration_engine) as s:
        todas = await filas(s)
    canonicas = [f for f in todas if f.workspace_id is None]
    aportes = [f for f in todas if f.workspace_id is not None]
    # Vale en cualquier intercalado: la última evaluación en tomar el candado ve las
    # dos filas ya confirmadas.
    assert len(canonicas) == 1
    assert {f.trust for f in aportes} == {"corroborated"}
    assert len(storage.copias) == 1
