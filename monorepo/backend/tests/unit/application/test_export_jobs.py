import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.exports.export_jobs import (
    CompleteExportJobUseCase,
    DownloadExportFileUseCase,
    GetExportJobUseCase,
    ReconcileExportJobsUseCase,
)
from app.domain.entities.export_job import ExportFormat, ExportJob, ExportJobStatus
from app.domain.errors.export_errors import ExportFileUnavailable, ExportJobNotFound
from tests.unit.application.export_fakes import InMemoryExportJobRepository
from tests.unit.application.fakes import FakeEmailService

AHORA = datetime(2026, 9, 28, 12, 0, 0)
BASE_URL = "https://app.test"
CORREO = "rep@andes.cl"
USUARIO = uuid4()


def _job(formato: ExportFormat = ExportFormat.PDF) -> ExportJob:
    return ExportJob.crear(
        user_id=USUARIO,
        supplier_id=uuid4(),
        tender_id=uuid4(),
        format=formato,
        sections=[],
        file_name=f"licitacion-COT26.{formato.value}",
        now=AHORA,
    )


async def _listo(contenido: bytes) -> bytes:
    return contenido


async def _falla() -> bytes:
    raise RuntimeError("fuente rota")


def _completar(jobs, correo, ahora=AHORA) -> CompleteExportJobUseCase:
    return CompleteExportJobUseCase(jobs=jobs, email=correo, base_url=BASE_URL, now=lambda: ahora)


class TestCompletar:
    async def test_guarda_el_archivo_y_avisa_por_correo_con_el_enlace(self):
        # Criterio 8: "le avisará por correo cuando esté listo para descargar".
        jobs, correo = InMemoryExportJobRepository(), FakeEmailService()
        job = await jobs.save(_job())

        await _completar(jobs, correo).execute(job, _listo(b"%PDF"), CORREO, "Áreas verdes")

        guardado = jobs.jobs[job.id]
        assert guardado.status is ExportJobStatus.READY
        assert guardado.content == b"%PDF"
        [mensaje] = correo.sent
        assert mensaje.to == CORREO
        assert "PDF" in mensaje.subject
        assert f"{BASE_URL}/exportaciones/{job.id}" in mensaje.text_body
        assert f"{BASE_URL}/exportaciones/{job.id}" in mensaje.html_body
        assert "Áreas verdes" in mensaje.text_body

    async def test_el_correo_del_excel_dice_excel(self):
        # Criterio 9.
        jobs, correo = InMemoryExportJobRepository(), FakeEmailService()
        job = await jobs.save(_job(ExportFormat.XLSX))

        await _completar(jobs, correo).execute(job, _listo(b"PK"), CORREO, "Áreas verdes")

        assert "Excel" in correo.sent[0].subject

    async def test_escapa_el_nombre_de_la_licitacion_en_el_html(self):
        jobs, correo = InMemoryExportJobRepository(), FakeEmailService()
        job = await jobs.save(_job())

        await _completar(jobs, correo).execute(job, _listo(b"%PDF"), CORREO, "<script>x</script>")

        assert "<script>" not in correo.sent[0].html_body
        assert "&lt;script&gt;" in correo.sent[0].html_body

    async def test_si_la_generacion_falla_queda_fallido_y_avisa(self):
        jobs, correo = InMemoryExportJobRepository(), FakeEmailService()
        job = await jobs.save(_job())

        await _completar(jobs, correo).execute(job, _falla(), CORREO, "Áreas verdes")

        guardado = jobs.jobs[job.id]
        assert guardado.status is ExportJobStatus.FAILED
        assert "fuente rota" in (guardado.error or "")
        assert "no se pudo" in correo.sent[0].subject.lower()

    async def test_si_el_correo_falla_el_archivo_igual_queda_disponible(self):
        # El usuario lo puede bajar desde la app aunque el correo no salga.
        jobs, correo = InMemoryExportJobRepository(), FakeEmailService()
        correo.simular_caida()
        job = await jobs.save(_job())

        await _completar(jobs, correo).execute(job, _listo(b"%PDF"), CORREO, "Áreas verdes")

        assert jobs.jobs[job.id].status is ExportJobStatus.READY

    async def test_una_tarea_cancelada_por_el_apagado_no_se_marca_ni_avisa(self):
        # Al reiniciar la API, `ReconcileExportJobsUseCase` la marca fallida.
        jobs, correo = InMemoryExportJobRepository(), FakeEmailService()
        job = await jobs.save(_job())

        async def cancelada() -> bytes:
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await _completar(jobs, correo).execute(job, cancelada(), CORREO, "x")
        assert jobs.jobs[job.id].status is ExportJobStatus.PROCESSING
        assert correo.sent == []


class TestConsultar:
    async def test_el_dueno_ve_el_estado(self):
        jobs = InMemoryExportJobRepository()
        job = await jobs.save(_job())

        assert (await GetExportJobUseCase(jobs).execute(USUARIO, job.id)).id == job.id

    async def test_consultar_el_estado_no_trae_el_archivo(self):
        jobs = InMemoryExportJobRepository()
        job = await jobs.save(_job().listo(b"%PDF", AHORA))

        consultado = await GetExportJobUseCase(jobs).execute(USUARIO, job.id)

        assert consultado.status is ExportJobStatus.READY
        assert consultado.content is None

    async def test_otro_usuario_no_lo_ve(self):
        jobs = InMemoryExportJobRepository()
        job = await jobs.save(_job())

        with pytest.raises(ExportJobNotFound):
            await GetExportJobUseCase(jobs).execute(uuid4(), job.id)


class TestDescargar:
    def _descargar(self, jobs, ahora=AHORA) -> DownloadExportFileUseCase:
        return DownloadExportFileUseCase(jobs=jobs, now=lambda: ahora)

    async def test_entrega_el_archivo_listo(self):
        jobs = InMemoryExportJobRepository()
        job = await jobs.save(_job().listo(b"%PDF", AHORA))

        archivo = await self._descargar(jobs).execute(USUARIO, job.id)

        assert archivo.content == b"%PDF"
        assert archivo.media_type == "application/pdf"
        assert archivo.file_name == "licitacion-COT26.pdf"

    async def test_solo_al_dueno(self):
        jobs = InMemoryExportJobRepository()
        job = await jobs.save(_job().listo(b"%PDF", AHORA))

        with pytest.raises(ExportJobNotFound):
            await self._descargar(jobs).execute(uuid4(), job.id)

    @pytest.mark.parametrize(
        ("preparar", "motivo"),
        [
            (lambda j: j, "processing"),
            (lambda j: j.fallido("x", AHORA), "failed"),
        ],
    )
    async def test_no_disponible_mientras_se_genera_o_si_fallo(self, preparar, motivo):
        jobs = InMemoryExportJobRepository()
        job = await jobs.save(preparar(_job()))

        with pytest.raises(ExportFileUnavailable) as error:
            await self._descargar(jobs).execute(USUARIO, job.id)
        assert error.value.reason == motivo

    async def test_vencido_a_los_siete_dias(self):
        jobs = InMemoryExportJobRepository()
        job = await jobs.save(_job().listo(b"%PDF", AHORA))

        with pytest.raises(ExportFileUnavailable) as error:
            await self._descargar(jobs, AHORA + timedelta(days=7)).execute(USUARIO, job.id)
        assert error.value.reason == "expired"


class TestReconciliar:
    async def test_al_arrancar_falla_lo_que_quedo_en_proceso_y_limpia_lo_vencido(self):
        jobs = InMemoryExportJobRepository()
        colgado = await jobs.save(_job())
        viejo = await jobs.save(
            _job().listo(b"%PDF", AHORA).model_copy(update={"expires_at": AHORA - timedelta(days=1)})
        )

        colgados, purgados = await ReconcileExportJobsUseCase(jobs, now=lambda: AHORA).execute()

        assert (colgados, purgados) == (1, 1)
        assert jobs.jobs[colgado.id].status is ExportJobStatus.FAILED
        assert jobs.jobs[viejo.id].content is None
