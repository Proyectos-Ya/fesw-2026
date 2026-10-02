"""Repositorio de exportaciones en segundo plano contra Postgres real (HdU 19)."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.export_job import ExportFormat, ExportJob, ExportJobStatus
from app.infrastructure.repositories.export_job_repository import ExportJobRepository
from tests.integration.test_tender_share_link_repository import _escenario

AHORA = datetime(2026, 9, 28, 12, 0, 0)


def _job(user_id: UUID, supplier_id: UUID, tender_id: UUID, now: datetime = AHORA) -> ExportJob:
    return ExportJob.crear(
        user_id=user_id,
        supplier_id=supplier_id,
        tender_id=tender_id,
        format=ExportFormat.XLSX,
        sections=["hitos", "montos"],
        file_name="licitacion-COT26.xlsx",
        now=now,
    )


async def test_guarda_y_lee_el_archivo_binario(db_session: AsyncSession):
    ids = await _escenario(db_session)
    repo = ExportJobRepository(db_session)
    # Bytes arbitrarios, incluidos nulos: tiene que volver idéntico.
    contenido = bytes(range(256)) * 40
    job = await repo.save(_job(*ids))

    await repo.save(job.listo(contenido, AHORA + timedelta(seconds=20)))
    db_session.expunge_all()

    leido = await repo.get(job.id)
    assert leido is not None
    assert leido.status is ExportJobStatus.READY
    assert leido.content == contenido
    assert leido.sections == ["hitos", "montos"]
    assert leido.format is ExportFormat.XLSX


async def test_al_arrancar_marca_fallido_lo_que_quedo_en_proceso(db_session: AsyncSession):
    ids = await _escenario(db_session)
    repo = ExportJobRepository(db_session)
    colgado = await repo.save(_job(*ids))
    listo = await repo.save(_job(*ids).listo(b"x", AHORA))

    assert await repo.fail_stale(AHORA) == 1
    db_session.expunge_all()

    assert (await repo.get(colgado.id)).status is ExportJobStatus.FAILED
    assert (await repo.get(listo.id)).status is ExportJobStatus.READY


async def test_vacia_el_contenido_de_los_vencidos(db_session: AsyncSession):
    ids = await _escenario(db_session)
    repo = ExportJobRepository(db_session)
    viejo = await repo.save(_job(*ids, now=AHORA - timedelta(days=8)).listo(b"viejo", AHORA))
    vigente = await repo.save(_job(*ids).listo(b"vigente", AHORA))

    assert await repo.purge_expired(AHORA) == 1
    db_session.expunge_all()

    assert (await repo.get(viejo.id)).content is None
    assert (await repo.get(vigente.id)).content == b"vigente"
