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


@pytest.fixture
def sync_api():
    from app.application.use_cases.calendar.sync_milestones import (
        MilestoneSyncResult,
        SyncResult,
    )
    from app.infrastructure.routers.calendar import create_milestone_sync_router

    user_id, tender_id, ok_id, malo_id = uuid4(), uuid4(), uuid4(), uuid4()
    sync = AsyncMock()
    sync.execute.return_value = SyncResult(
        results=[
            MilestoneSyncResult(milestone_id=ok_id, synced=True),
            MilestoneSyncResult(milestone_id=malo_id, synced=False),
        ]
    )
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=user_id)

    app.include_router(create_milestone_sync_router(current_user, lambda: sync))
    return SimpleNamespace(
        client=TestClient(app),
        sync=sync,
        user_id=user_id,
        tender_id=tender_id,
        ok_id=ok_id,
        malo_id=malo_id,
        path=f"/tenders/{tender_id}/milestones/sync",
    )


def _sincronizar(sync_api, **cambios):
    cuerpo = {"provider": "google", "milestone_ids": [str(sync_api.ok_id), str(sync_api.malo_id)]}
    cuerpo.update(cambios)
    return sync_api.client.post(sync_api.path, json=cuerpo)


def test_sincronizar_devuelve_el_resultado_por_hito(sync_api):
    respuesta = _sincronizar(sync_api, default_time="09:00")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "results": [
            {"milestone_id": str(sync_api.ok_id), "synced": True},
            {"milestone_id": str(sync_api.malo_id), "synced": False},
        ],
        "failed_count": 1,
    }
    sync_api.sync.execute.assert_awaited_once_with(
        sync_api.user_id, GOOGLE, sync_api.tender_id, [sync_api.ok_id, sync_api.malo_id], time(9, 0)
    )


@pytest.mark.parametrize(
    ("error", "estado"),
    [
        ("no_conectado", 409),
        ("expirado", 409),
        ("hora", 422),
        ("hito", 404),
        ("configuracion", 503),
    ],
)
def test_errores_de_sincronizacion(sync_api, error, estado):
    from app.domain.errors.calendar_errors import (
        CalendarNotConnected,
        MilestoneTimeRequired,
    )

    sync_api.sync.execute.side_effect = {
        "no_conectado": CalendarNotConnected(),
        "expirado": CalendarAuthExpired(),
        "hora": MilestoneTimeRequired([sync_api.malo_id]),
        "hito": MilestoneNotFound(),
        "configuracion": CalendarNotConfigured(GOOGLE),
    }[error]

    respuesta = _sincronizar(sync_api)

    assert respuesta.status_code == estado
    assert isinstance(respuesta.json()["detail"], str)


def test_sincronizar_valida_el_cuerpo(sync_api):
    assert _sincronizar(sync_api, milestone_ids=[]).status_code == 422
    assert _sincronizar(sync_api, provider="yahoo").status_code == 422
    sync_api.sync.execute.assert_not_awaited()
