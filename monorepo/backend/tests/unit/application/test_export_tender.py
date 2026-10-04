import asyncio
import time
from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.exports.build_export_snapshot import (
    BuildExportSnapshotUseCase,
)
from app.application.use_cases.exports.export_snapshot import (
    ExportSection,
    ExportSnapshot,
)
from app.application.use_cases.exports.export_tender import (
    ExportFile,
    ExportQueued,
    ExportTenderUseCase,
)
from app.domain.entities.export_job import ExportFormat, ExportJob, ExportJobStatus
from app.domain.entities.supplier_member import MemberRole, WorkspaceContext
from app.domain.entities.tender import Tender
from app.domain.errors.export_errors import (
    ExportForbidden,
    ExportGenerationFailed,
    ExportSectionsRequired,
)
from tests.unit.application.export_fakes import (
    InMemoryExportJobRepository,
    InMemoryQuotationRepository,
)
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemoryTenderRepository,
)

AHORA = datetime(2026, 9, 28, 12, 0, 0)
CORREO = "rep@andes.cl"
UMBRAL = 0.05  # En producción son 10 s; acá basta con que el renderer lo supere.


class RendererFalso:
    """Renderer que tarda lo que se le pida y registra con qué se lo llamó."""

    def __init__(self, contenido: bytes, demora: float = 0.0, error: Exception | None = None):
        self.contenido = contenido
        self.demora = demora
        self.error = error
        self.llamadas: list[tuple[ExportSnapshot, list[ExportSection] | None]] = []

    def _generar(self, snapshot, sections) -> bytes:
        self.llamadas.append((snapshot, None if sections is None else list(sections)))
        time.sleep(self.demora)
        if self.error:
            raise self.error
        return self.contenido


class PdfFalso(RendererFalso):
    def render(self, snapshot: ExportSnapshot) -> bytes:
        return self._generar(snapshot, None)


class ExcelFalso(RendererFalso):
    def render(self, snapshot: ExportSnapshot, sections: Sequence[ExportSection]) -> bytes:
        return self._generar(snapshot, sections)


class SegundoPlanoFalso:
    def __init__(self) -> None:
        self.programados: list[tuple[ExportJob, asyncio.Task, str, str]] = []

    def schedule(self, job, render, recipient, tender_name) -> None:
        self.programados.append((job, render, recipient, tender_name))


def _contexto(permisos: list[str] | None = None) -> WorkspaceContext:
    return WorkspaceContext(
        user_id=uuid4(),
        active_supplier_id=uuid4(),
        active_supplier_name="Constructora Andes",
        role=MemberRole.MEMBER,
        permissions=["view_matches"] if permisos is None else permisos,
    )


class Escenario:
    def __init__(self, pdf: PdfFalso | None = None, excel: ExcelFalso | None = None) -> None:
        tenders = InMemoryTenderRepository()
        self.tender = Tender(
            code="1057539-228/COT26",
            name="Mantención de áreas verdes",
            status_id=1,
            published_at=AHORA - timedelta(days=2),
            closing_at=AHORA + timedelta(days=10),
            last_change_at=AHORA,
            buyer_rut="61.980.170-9",
            buyer_unit="Operaciones",
        )
        tenders.tenders[self.tender.id] = self.tender
        self.jobs = InMemoryExportJobRepository()
        self.pdf = pdf or PdfFalso(b"%PDF-rapido")
        self.excel = excel or ExcelFalso(b"PK-rapido")
        self.fondo = SegundoPlanoFalso()
        self.use_case = ExportTenderUseCase(
            snapshots=BuildExportSnapshotUseCase(
                tenders=tenders,
                matching_results=InMemoryMatchingResultRepository(),
                quotations=InMemoryQuotationRepository(),
                now=lambda: AHORA,
            ),
            jobs=self.jobs,
            pdf_renderer=self.pdf,
            excel_renderer=self.excel,
            background=self.fondo,
            inline_timeout_seconds=UMBRAL,
            now=lambda: AHORA,
        )

    async def exportar(self, formato: ExportFormat, secciones=None, ctx=None):
        return await self.use_case.execute(
            ctx or _contexto(), CORREO, self.tender.id, formato, secciones or []
        )


class TestRapido:
    async def test_un_pdf_rapido_se_entrega_de_inmediato(self):
        esc = Escenario()

        resultado = await esc.exportar(ExportFormat.PDF)

        assert isinstance(resultado, ExportFile)
        assert resultado.content == b"%PDF-rapido"
        assert resultado.media_type == "application/pdf"
        # El código trae "/", que no puede ir en un nombre de archivo.
        assert resultado.file_name == "licitacion-1057539-228_COT26.pdf"

    async def test_sin_pasar_a_segundo_plano_no_deja_rastro(self):
        esc = Escenario()

        await esc.exportar(ExportFormat.PDF)

        assert esc.jobs.jobs == {}
        assert esc.fondo.programados == []

    async def test_el_excel_recibe_las_secciones_elegidas(self):
        # Criterio 5.
        esc = Escenario()

        resultado = await esc.exportar(
            ExportFormat.XLSX, [ExportSection.HITOS, ExportSection.MONTOS]
        )

        assert isinstance(resultado, ExportFile)
        assert resultado.file_name.endswith(".xlsx")
        assert esc.excel.llamadas[0][1] == [ExportSection.HITOS, ExportSection.MONTOS]

    async def test_un_excel_sin_secciones_no_se_genera(self):
        esc = Escenario()

        with pytest.raises(ExportSectionsRequired):
            await esc.exportar(ExportFormat.XLSX, [])
        assert esc.excel.llamadas == []

    async def test_si_el_renderer_falla_a_tiempo_se_informa(self):
        esc = Escenario(pdf=PdfFalso(b"", error=RuntimeError("fuente rota")))

        with pytest.raises(ExportGenerationFailed):
            await esc.exportar(ExportFormat.PDF)

    async def test_si_el_render_mismo_lanza_timeout_no_pasa_a_segundo_plano(self):
        esc = Escenario(pdf=PdfFalso(b"", error=TimeoutError("socket")))

        with pytest.raises(ExportGenerationFailed):
            await esc.exportar(ExportFormat.PDF)
        assert esc.fondo.programados == []
        assert esc.jobs.jobs == {}

    async def test_sin_permiso_no_genera_nada(self):
        esc = Escenario()

        with pytest.raises(ExportForbidden):
            await esc.exportar(ExportFormat.PDF, ctx=_contexto(permisos=[]))
        assert esc.pdf.llamadas == []


class TestLento:
    async def test_un_pdf_lento_pasa_a_segundo_plano(self):
        # Criterio 8.
        esc = Escenario(pdf=PdfFalso(b"%PDF-lento", demora=0.3))

        resultado = await esc.exportar(ExportFormat.PDF)

        assert isinstance(resultado, ExportQueued)
        job, tarea, destinatario, nombre = esc.fondo.programados[0]
        assert job.id == resultado.job.id
        assert destinatario == CORREO
        assert nombre == "Mantención de áreas verdes"
        # La generación sigue sola y termina con el archivo.
        assert await tarea == b"%PDF-lento"

    async def test_un_excel_lento_tambien(self):
        # Criterio 9.
        esc = Escenario(excel=ExcelFalso(b"PK-lento", demora=0.3))

        resultado = await esc.exportar(ExportFormat.XLSX, [ExportSection.HITOS])

        assert isinstance(resultado, ExportQueued)
        await esc.fondo.programados[0][1]

    async def test_queda_registrado_en_proceso_para_poder_consultarlo(self):
        esc = Escenario(pdf=PdfFalso(b"%PDF-lento", demora=0.3))

        resultado = await esc.exportar(ExportFormat.PDF)

        guardado = esc.jobs.jobs[resultado.job.id]
        assert guardado.status is ExportJobStatus.PROCESSING
        assert guardado.format is ExportFormat.PDF
        assert guardado.tender_id == esc.tender.id
        await esc.fondo.programados[0][1]
