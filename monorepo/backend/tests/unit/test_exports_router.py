from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.application.use_cases.exports.export_snapshot import ExportSection
from app.application.use_cases.exports.export_tender import ExportFile, ExportQueued
from app.domain.entities.export_job import ExportFormat, ExportJob
from app.domain.entities.supplier_member import MemberRole, WorkspaceContext
from app.domain.errors.export_errors import (
    ExportFileUnavailable,
    ExportForbidden,
    ExportGenerationFailed,
    ExportJobNotFound,
    ExportSectionsRequired,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.routers.exports import create_exports_router

AHORA = datetime(2026, 9, 28, 12, 0, 0)
PDF = ExportFile(file_name="licitacion-COT26.pdf", media_type="application/pdf", content=b"%PDF")


@pytest.fixture
def api():
    contexto = WorkspaceContext(
        user_id=uuid4(),
        active_supplier_id=uuid4(),
        active_supplier_name="Constructora Andes",
        role=MemberRole.MEMBER,
        permissions=["view_matches"],
    )
    usuario = SimpleNamespace(id=contexto.user_id, email="rep@andes.cl")
    tender_id = uuid4()
    job = ExportJob.crear(
        user_id=contexto.user_id,
        supplier_id=contexto.active_supplier_id,
        tender_id=tender_id,
        format=ExportFormat.PDF,
        sections=[],
        file_name="licitacion-COT26.pdf",
        now=AHORA,
    )
    exportar, consultar, descargar = AsyncMock(), AsyncMock(), AsyncMock()
    exportar.execute.return_value = PDF
    consultar.execute.return_value = job
    descargar.execute.return_value = PDF

    app = FastAPI()

    def workspace():
        return contexto

    def current_user():
        return usuario

    app.include_router(
        create_exports_router(
            workspace, current_user, lambda: exportar, lambda: consultar, lambda: descargar
        )
    )
    return SimpleNamespace(
        client=TestClient(app),
        app=app,
        workspace=workspace,
        current_user=current_user,
        contexto=contexto,
        tender_id=tender_id,
        job=job,
        exportar=exportar,
        consultar=consultar,
        descargar=descargar,
        path=f"/tenders/{tender_id}/exports",
    )


class TestExportar:
    def test_un_archivo_a_tiempo_se_descarga_directo(self, api):
        respuesta = api.client.post(api.path, json={"format": "pdf"})

        assert respuesta.status_code == 200
        assert respuesta.content == b"%PDF"
        assert respuesta.headers["content-type"] == "application/pdf"
        assert respuesta.headers["content-disposition"] == (
            'attachment; filename="licitacion-COT26.pdf"'
        )
        assert respuesta.headers["cache-control"] == "no-store"

    def test_pasa_el_formato_las_secciones_y_el_correo(self, api):
        api.client.post(api.path, json={"format": "xlsx", "sections": ["hitos", "montos"]})

        api.exportar.execute.assert_awaited_once_with(
            api.contexto,
            "rep@andes.cl",
            api.tender_id,
            ExportFormat.XLSX,
            [ExportSection.HITOS, ExportSection.MONTOS],
        )

    def test_sin_secciones_indicadas_van_todas(self, api):
        api.client.post(api.path, json={"format": "xlsx"})

        assert api.exportar.execute.await_args.args[4] == list(ExportSection)

    def test_si_tarda_responde_202_con_el_trabajo(self, api):
        # Criterios 8 y 9.
        api.exportar.execute.return_value = ExportQueued(job=api.job)

        respuesta = api.client.post(api.path, json={"format": "pdf"})

        assert respuesta.status_code == 202
        cuerpo = respuesta.json()
        assert cuerpo["job_id"] == str(api.job.id)
        assert cuerpo["status"] == "processing"
        assert "correo" in cuerpo["message"]

    def test_un_excel_sin_secciones_es_422(self, api):
        api.exportar.execute.side_effect = ExportSectionsRequired()

        assert api.client.post(api.path, json={"format": "xlsx", "sections": []}).status_code == 422

    def test_una_seccion_desconocida_es_422(self, api):
        respuesta = api.client.post(api.path, json={"format": "xlsx", "sections": ["secreto"]})

        assert respuesta.status_code == 422
        api.exportar.execute.assert_not_awaited()

    def test_un_formato_desconocido_es_422(self, api):
        assert api.client.post(api.path, json={"format": "docx"}).status_code == 422

    @pytest.mark.parametrize(
        ("error", "status"),
        [
            (ExportForbidden(), 403),
            (TenderNotFound(uuid4()), 404),
            (ExportGenerationFailed(), 500),
        ],
    )
    def test_errores(self, api, error, status):
        api.exportar.execute.side_effect = error

        assert api.client.post(api.path, json={"format": "pdf"}).status_code == status

    def test_sin_sesion_es_401(self, api):
        def denegado():
            raise HTTPException(401, "No autenticado")

        api.app.dependency_overrides[api.workspace] = denegado
        api.app.dependency_overrides[api.current_user] = denegado

        assert api.client.post(api.path, json={"format": "pdf"}).status_code == 401
        assert api.client.get(f"/exports/{api.job.id}").status_code == 401
        assert api.client.get(f"/exports/{api.job.id}/file").status_code == 401
        api.exportar.execute.assert_not_awaited()


class TestTrabajo:
    def test_consulta_el_estado_sin_el_contenido(self, api):
        respuesta = api.client.get(f"/exports/{api.job.id}")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["status"] == "processing"
        assert cuerpo["format"] == "pdf"
        assert "content" not in cuerpo
        api.consultar.execute.assert_awaited_once_with(api.contexto.user_id, api.job.id)

    def test_uno_ajeno_es_404(self, api):
        api.consultar.execute.side_effect = ExportJobNotFound()

        assert api.client.get(f"/exports/{api.job.id}").status_code == 404

    def test_descarga_el_archivo_listo(self, api):
        respuesta = api.client.get(f"/exports/{api.job.id}/file")

        assert respuesta.status_code == 200
        assert respuesta.content == b"%PDF"
        assert "attachment" in respuesta.headers["content-disposition"]

    @pytest.mark.parametrize(
        ("motivo", "status", "code"),
        [
            ("processing", 409, "export_processing"),
            ("failed", 410, "export_failed"),
            ("expired", 410, "export_expired"),
        ],
    )
    def test_archivo_no_disponible(self, api, motivo, status, code):
        api.descargar.execute.side_effect = ExportFileUnavailable(motivo)

        respuesta = api.client.get(f"/exports/{api.job.id}/file")

        assert respuesta.status_code == status
        assert respuesta.json()["code"] == code
