import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from app.domain.entities.export_job import ExportFormat, ExportJob
from app.infrastructure.services.exports.background import AsyncioExportBackground

AHORA = datetime(2026, 9, 28, 12, 0, 0)


def _job() -> ExportJob:
    return ExportJob.crear(
        user_id=uuid4(),
        supplier_id=uuid4(),
        tender_id=uuid4(),
        format=ExportFormat.PDF,
        sections=[],
        file_name="x.pdf",
        now=AHORA,
    )


class CompletarFalso:
    def __init__(self, error: Exception | None = None) -> None:
        self.llamadas: list[tuple] = []
        self.error = error

    async def execute(self, job, render, recipient, tender_name):
        contenido = await render
        self.llamadas.append((job.id, contenido, recipient, tender_name))
        if self.error:
            raise self.error


def _fondo(completar: CompletarFalso, sesiones: list[str]) -> AsyncioExportBackground:
    @asynccontextmanager
    async def abrir():
        # Cada trabajo abre su propia sesión: la de la petición ya se cerró.
        sesiones.append("abierta")
        yield completar
        sesiones.append("cerrada")

    return AsyncioExportBackground(abrir)


async def _generar(contenido: bytes, demora: float = 0.0) -> bytes:
    await asyncio.sleep(demora)
    return contenido


async def test_termina_el_trabajo_con_una_sesion_propia():
    completar, sesiones = CompletarFalso(), []
    fondo = _fondo(completar, sesiones)
    job = _job()

    fondo.schedule(job, asyncio.create_task(_generar(b"%PDF")), "rep@andes.cl", "Áreas verdes")
    await fondo.wait_idle()

    assert completar.llamadas == [(job.id, b"%PDF", "rep@andes.cl", "Áreas verdes")]
    assert sesiones == ["abierta", "cerrada"]
    assert fondo.pending == 0


async def test_mantiene_viva_la_tarea_mientras_corre():
    completar = CompletarFalso()
    fondo = _fondo(completar, [])

    fondo.schedule(_job(), asyncio.create_task(_generar(b"x", 0.05)), "a@b.cl", "x")

    assert fondo.pending == 1
    await fondo.wait_idle()
    assert fondo.pending == 0


async def test_un_error_al_completar_no_se_propaga():
    completar = CompletarFalso(error=RuntimeError("base caída"))
    fondo = _fondo(completar, [])

    fondo.schedule(_job(), asyncio.create_task(_generar(b"x")), "a@b.cl", "x")
    await fondo.wait_idle()

    assert len(completar.llamadas) == 1


async def test_al_apagar_cancela_lo_pendiente():
    completar = CompletarFalso()
    fondo = _fondo(completar, [])
    render = asyncio.create_task(_generar(b"x", 10))

    fondo.schedule(_job(), render, "a@b.cl", "x")
    await asyncio.sleep(0)
    await fondo.shutdown()

    assert fondo.pending == 0
    assert render.cancelled()
    assert completar.llamadas == []
