import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.infrastructure.middleware import register_middleware


@pytest.fixture
def client():
    app = FastAPI()
    register_middleware(app)

    @app.post("/extension/installations/heartbeat")
    def heartbeat():
        return {"ok": True}

    return TestClient(app)


def _preflight(client, origin):
    return client.options(
        "/extension/installations/heartbeat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize(
    "origin",
    [
        "moz-extension://6668cfa5-f7c7-492f-81c7-c5b096ecf036",
        "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
    ],
)
def test_acepta_el_origen_de_la_extension(client, origin):
    response = _preflight(client, origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "moz-extension://x.evil.example",
        "chrome-extension://abc/../evil",
    ],
)
def test_rechaza_otros_origenes(client, origin):
    response = _preflight(client, origin)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
