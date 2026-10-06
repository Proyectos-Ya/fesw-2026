from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.application.services.milestone_extraction_background import (
    MilestoneExtractionStatus,
)
from app.application.use_cases.milestones.milestone_views import (
    MilestoneView,
    TenderMilestonesResult,
)
from app.domain.entities.calendar import CalendarProvider
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    MilestoneUrgency,
    TenderMilestone,
)
from app.domain.errors.milestone_errors import (
    MilestoneExtractionUnavailable,
    MilestoneNotFound,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.routers.milestones import create_milestones_router


@pytest.fixture
def api():
    user_id, tender_id = uuid4(), uuid4()
    hito = TenderMilestone(
        user_id=user_id,
        tender_id=tender_id,
        kind=MilestoneKind.VISITA_TECNICA,
        title="Visita técnica obligatoria",
        source=MilestoneSource.IA_DOCUMENTO,
        source_excerpt="a las 15:00 del día 20",
        due_at=datetime(2026, 10, 20, 18, 0),
        has_time=True,
    )
    resultado = TenderMilestonesResult(
        milestones=[
            MilestoneView(
                milestone=hito,
                urgency=MilestoneUrgency.CRITICO,
                synced_providers=[CalendarProvider.GOOGLE],
            )
        ],
        documents_count=1,
        discarded_count=2,
        unavailable_documents_count=1,
    )
    listar, extraer, recordar = AsyncMock(), AsyncMock(), AsyncMock()
    recordar.execute.return_value = hito.model_copy(update={"reminder_days_before": 3})
    listar.execute.return_value = resultado
    extraer.execute.return_value = resultado
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=user_id)

    app.include_router(
        create_milestones_router(
            current_user, lambda: listar, lambda: extraer, lambda: recordar
        )
    )
    return SimpleNamespace(
        client=TestClient(app),
        app=app,
        current_user=current_user,
        listar=listar,
        extraer=extraer,
        recordar=recordar,
        path=f"/tenders/{tender_id}/milestones",
        user_id=user_id,
        tender_id=tender_id,
        hito=hito,
    )


def test_lista_los_hitos_con_fecha_utc_urgencia_y_sincronizacion(api):
    respuesta = api.client.get(api.path)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["documents_count"] == 1
    hito = cuerpo["milestones"][0]
    assert hito == {
        "id": str(api.hito.id),
        "kind": "visita_tecnica",
        "title": "Visita técnica obligatoria",
        "description": None,
        "source": "ia_documento",
        "source_excerpt": "a las 15:00 del día 20",
        "due_at": "2026-10-20T18:00:00Z",
        "has_time": True,
        "urgency": "critico",
        "synced_providers": ["google"],
        "reminder_days_before": None,
    }
    api.listar.execute.assert_awaited_once_with(api.user_id, api.tender_id)


def test_extraer_devuelve_los_hitos_y_cuantos_se_descartaron(api):
    respuesta = api.client.post(f"{api.path}/extract")

    assert respuesta.status_code == 200
    assert respuesta.json()["discarded_count"] == 2
    assert respuesta.json()["unavailable_documents_count"] == 1
    api.extraer.execute.assert_awaited_once_with(api.user_id, api.tender_id)


def test_licitacion_inexistente_es_404(api):
    api.listar.execute.side_effect = TenderNotFound(api.tender_id)
    api.extraer.execute.side_effect = TenderNotFound(api.tender_id)

    assert api.client.get(api.path).status_code == 404
    assert api.client.post(f"{api.path}/extract").status_code == 404


def test_ia_no_disponible_es_503_con_mensaje(api):
    api.extraer.execute.side_effect = MilestoneExtractionUnavailable()

    respuesta = api.client.post(f"{api.path}/extract")

    assert respuesta.status_code == 503
    assert "hitos" in respuesta.json()["detail"]


def test_sin_sesion_es_401(api):
    def denegado():
        raise HTTPException(401, "No autenticado")

    api.app.dependency_overrides[api.current_user] = denegado

    assert api.client.get(api.path).status_code == 401
    assert api.client.post(f"{api.path}/extract").status_code == 401
    api.listar.execute.assert_not_awaited()
    api.extraer.execute.assert_not_awaited()


class TestRecordatorio:
    """Criterio 10: activar/apagar el recordatorio de un hito."""

    def _ruta(self, api) -> str:
        return f"{api.path}/{api.hito.id}/reminder"

    def test_activa_el_recordatorio_con_la_anticipacion_elegida(self, api):
        respuesta = api.client.patch(self._ruta(api), json={"days_before": 3})

        assert respuesta.status_code == 200
        assert respuesta.json() == {
            "milestone_id": str(api.hito.id),
            "reminder_days_before": 3,
        }
        api.recordar.execute.assert_awaited_once_with(
            api.user_id, api.tender_id, api.hito.id, 3
        )

    def test_lo_apaga_con_nulo(self, api):
        api.recordar.execute.return_value = api.hito

        respuesta = api.client.patch(self._ruta(api), json={"days_before": None})

        assert respuesta.status_code == 200
        assert respuesta.json()["reminder_days_before"] is None

    @pytest.mark.parametrize("dias", [0, 2, -1, 400])
    def test_rechaza_anticipaciones_fuera_de_las_opciones(self, api, dias):
        respuesta = api.client.patch(self._ruta(api), json={"days_before": dias})

        assert respuesta.status_code == 422
        api.recordar.execute.assert_not_awaited()

    def test_un_hito_ajeno_o_de_otra_licitacion_es_404(self, api):
        api.recordar.execute.side_effect = MilestoneNotFound()

        assert api.client.patch(self._ruta(api), json={"days_before": 1}).status_code == 404

    def test_sin_sesion_es_401(self, api):
        def denegado():
            raise HTTPException(401, "No autenticado")

        api.app.dependency_overrides[api.current_user] = denegado

        assert api.client.patch(self._ruta(api), json={"days_before": 1}).status_code == 401
        api.recordar.execute.assert_not_awaited()


def test_la_lista_dice_si_la_ia_esta_leyendo_las_bases(api):
    api.listar.execute.return_value = TenderMilestonesResult(
        milestones=[],
        documents_count=1,
        extraction_status=MilestoneExtractionStatus.RUNNING,
    )

    respuesta = api.client.get(api.path)

    assert respuesta.json()["extraction_status"] == "running"


def test_por_defecto_no_hay_extraccion_en_curso(api):
    assert api.client.get(api.path).json()["extraction_status"] == "idle"


def test_la_extraccion_manual_pasa_por_el_candado_de_la_automatica(api):
    # Si hay una extracción automática en curso, la manual espera en vez de
    # correr en paralelo y duplicar hitos.
    fondo = AsyncMock()
    fondo.run_now.return_value = api.listar.execute.return_value
    app = FastAPI()
    app.include_router(
        create_milestones_router(
            api.current_user,
            lambda: api.listar,
            lambda: api.extraer,
            lambda: api.recordar,
            lambda: fondo,
        )
    )

    respuesta = TestClient(app).post(f"{api.path}/extract")

    assert respuesta.status_code == 200
    fondo.run_now.assert_awaited_once_with(api.user_id, api.tender_id, api.extraer)
