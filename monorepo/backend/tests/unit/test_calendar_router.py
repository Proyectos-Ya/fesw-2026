from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.application.use_cases.calendar.calendar_authorization import (
    CalendarAuthorizationResult,
)
from app.application.use_cases.calendar.calendar_connections import (
    CalendarConnectionView,
)
from app.domain.entities.calendar import CalendarProvider
from app.domain.errors.calendar_errors import (
    CalendarAuthExpired,
    CalendarNotConfigured,
    CalendarPermissionMissing,
    CalendarProviderUnavailable,
    InvalidOAuthState,
)
from app.domain.errors.milestone_errors import MilestoneNotFound
from app.infrastructure.routers.calendar import create_calendar_router

GOOGLE = CalendarProvider.GOOGLE


@pytest.fixture
def api():
    user_id, tender_id, milestone_id = uuid4(), uuid4(), uuid4()
    conexiones, iniciar, completar, desconectar = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    conexiones.execute.return_value = [
        CalendarConnectionView(provider=GOOGLE, connected=True, account_email="u@gmail.com", needs_reconnect=False)
    ]
    iniciar.execute.return_value = "https://accounts.google.com/o/oauth2/v2/auth?state=abc"
    completar.execute.return_value = CalendarAuthorizationResult(
        provider=GOOGLE,
        tender_id=tender_id,
        milestone_ids=[milestone_id],
        default_time=time(9, 0),
        account_email="u@gmail.com",
    )
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=user_id)

    app.include_router(
        create_calendar_router(
            current_user, lambda: conexiones, lambda: iniciar, lambda: completar, lambda: desconectar
        )
    )
    return SimpleNamespace(
        client=TestClient(app),
        app=app,
        current_user=current_user,
        conexiones=conexiones,
        iniciar=iniciar,
        completar=completar,
        desconectar=desconectar,
        user_id=user_id,
        tender_id=tender_id,
        milestone_id=milestone_id,
    )


def _autorizar(api, **cambios):
    cuerpo = {"tender_id": str(api.tender_id), "milestone_ids": [str(api.milestone_id)], "default_time": "09:00"}
    cuerpo.update(cambios)
    return api.client.post("/calendar/google/authorize", json=cuerpo)


def test_lista_las_conexiones_sin_exponer_tokens(api):
    respuesta = api.client.get("/calendar/connections")

    assert respuesta.status_code == 200
    assert respuesta.json() == [
        {"provider": "google", "connected": True, "account_email": "u@gmail.com", "needs_reconnect": False}
    ]


def test_iniciar_la_autorizacion_devuelve_la_url_de_google(api):
    respuesta = _autorizar(api)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?state=abc"}
    api.iniciar.execute.assert_awaited_once_with(
        api.user_id, GOOGLE, api.tender_id, [api.milestone_id], time(9, 0)
    )


def test_la_hora_por_defecto_es_opcional(api):
    assert _autorizar(api, default_time=None).status_code == 200


@pytest.mark.parametrize(
    "cambios",
    [{"milestone_ids": []}, {"default_time": "9am"}, {"default_time": "25:00"}],
)
def test_valida_el_cuerpo(api, cambios):
    assert _autorizar(api, **cambios).status_code == 422
    api.iniciar.execute.assert_not_awaited()


def test_un_proveedor_desconocido_es_422(api):
    respuesta = api.client.post("/calendar/yahoo/authorize", json={"tender_id": str(api.tender_id), "milestone_ids": [str(api.milestone_id)]})

    assert respuesta.status_code == 422


def test_completar_devuelve_la_sincronizacion_pendiente(api):
    respuesta = api.client.post("/calendar/google/callback", json={"code": "c", "state": "s"})

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "provider": "google",
        "tender_id": str(api.tender_id),
        "milestone_ids": [str(api.milestone_id)],
        "default_time": "09:00",
        "account_email": "u@gmail.com",
    }
    api.completar.execute.assert_awaited_once_with(api.user_id, GOOGLE, "c", "s")


@pytest.mark.parametrize(
    ("error", "estado"),
    [
        (InvalidOAuthState(), 400),
        (CalendarPermissionMissing(), 403),
        (CalendarAuthExpired(), 409),
        (CalendarProviderUnavailable(), 502),
        (CalendarNotConfigured(GOOGLE), 503),
    ],
)
def test_errores_del_callback(api, error, estado):
    api.completar.execute.side_effect = error

    respuesta = api.client.post("/calendar/google/callback", json={"code": "c", "state": "s"})

    assert respuesta.status_code == estado
    assert respuesta.json()["detail"] == str(error)


@pytest.mark.parametrize(
    ("error", "estado"),
    [(MilestoneNotFound(), 404), (CalendarNotConfigured(GOOGLE), 503)],
)
def test_errores_al_iniciar(api, error, estado):
    api.iniciar.execute.side_effect = error

    assert _autorizar(api).status_code == estado


def test_desconectar(api):
    respuesta = api.client.delete("/calendar/connections/google")

    assert respuesta.status_code == 204
    api.desconectar.execute.assert_awaited_once_with(api.user_id, GOOGLE)


def test_sin_sesion_es_401(api):
    def denegado():
        raise HTTPException(401, "No autenticado")

    api.app.dependency_overrides[api.current_user] = denegado

    assert api.client.get("/calendar/connections").status_code == 401
    assert _autorizar(api).status_code == 401
    assert api.client.post("/calendar/google/callback", json={"code": "c", "state": "s"}).status_code == 401
    assert api.client.delete("/calendar/connections/google").status_code == 401
    api.completar.execute.assert_not_awaited()
