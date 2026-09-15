"""
Pruebas e2e del router /suppliers.

Todas las rutas requieren sesión (token de Supabase en `Authorization`).
GET /suppliers/me devuelve la empresa del usuario autenticado o 404.
"""

import pytest
from httpx import AsyncClient

from app import bootstrap
from app.domain.entities.company_profile import CompanyRecord, EconomicActivity
from app.domain.errors.company_lookup_errors import (
    CompanyLookupUnavailable,
    CompanyNotFoundInSource,
)
from app.main import app
from tests.support.api_auth import autenticar
from tests.unit.application.fakes import FakeCompanyLookupService

REGISTER = {
    "email": "dueno@example.com",
    "full_name": "Dueño Empresa",
}

SUPPLIER = {
    "rut": "76086428-5",
    "legal_name": "Constructora Norte SpA",
}


async def _login(api: AsyncClient) -> None:
    """Deja el cliente con una sesión de Supabase válida."""
    await autenticar(api, email=REGISTER["email"], full_name=REGISTER["full_name"])


@pytest.mark.asyncio
async def test_create_supplier_without_session_returns_401(api: AsyncClient):
    resp = await api.post("/suppliers", json=SUPPLIER)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_supplier_me_without_session_returns_401(api: AsyncClient):
    resp = await api.get("/suppliers/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_supplier_associates_logged_user(api: AsyncClient):
    await _login(api)

    resp = await api.post("/suppliers", json=SUPPLIER)
    assert resp.status_code == 201

    me = await api.get("/auth/me")
    assert resp.json()["user_id"] == me.json()["id"]


@pytest.mark.asyncio
async def test_create_second_supplier_for_same_user_returns_409(api: AsyncClient):
    await _login(api)
    first = await api.post("/suppliers", json=SUPPLIER)
    assert first.status_code == 201

    resp = await api.post(
        "/suppliers", json={"rut": "77777777-7", "legal_name": "Otra Empresa SpA"}
    )
    assert resp.status_code == 409
    assert "empresa" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_supplier_me_returns_404_without_company(api: AsyncClient):
    await _login(api)

    resp = await api.get("/suppliers/me")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_supplier_me_without_session_returns_401(api: AsyncClient):
    resp = await api.patch("/suppliers/me", json={"legal_name": "Nueva SpA"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_supplier_me_without_company_returns_404(api: AsyncClient):
    await _login(api)
    resp = await api.patch("/suppliers/me", json={"legal_name": "Nueva SpA"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_supplier_me_edits_own_company(api: AsyncClient):
    await _login(api)
    await api.post("/suppliers", json=SUPPLIER)

    resp = await api.patch(
        "/suppliers/me",
        json={"legal_name": "Constructora Renovada SpA", "num_employees": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["legal_name"] == "Constructora Renovada SpA"
    assert body["num_employees"] == 50
    # El RUT no cambia: no es parte del schema de edición
    assert body["rut"] == SUPPLIER["rut"]


@pytest.mark.asyncio
async def test_rut_exists_without_session_returns_401(api: AsyncClient):
    resp = await api.get("/suppliers/rut-exists", params={"rut": SUPPLIER["rut"]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rut_exists_returns_false_when_not_registered(api: AsyncClient):
    await _login(api)

    resp = await api.get("/suppliers/rut-exists", params={"rut": SUPPLIER["rut"]})
    assert resp.status_code == 200
    assert resp.json() == {"exists": False}


@pytest.mark.asyncio
async def test_rut_exists_returns_true_when_registered(api: AsyncClient):
    await _login(api)
    created = await api.post("/suppliers", json=SUPPLIER)
    assert created.status_code == 201

    resp = await api.get("/suppliers/rut-exists", params={"rut": SUPPLIER["rut"]})
    assert resp.status_code == 200
    assert resp.json() == {"exists": True}


def _fuente(servicio: FakeCompanyLookupService | None) -> None:
    app.dependency_overrides[bootstrap.get_company_lookup_service] = lambda: servicio


IMPORT_RUT = "76.668.304-5"
REGISTRO_WEB_EMPRESARIO = CompanyRecord(
    source="web-empresario",
    rut="76668304-5",
    legal_name="PLANETA LIBRE SOLUCIONES SUSTENTABLES LIMITADA",
    activities=[EconomicActivity(code=433000), EconomicActivity(code=952200)],
    raw_regions=["XIII REGION METROPOLITANA"],
    is_active=True,
)


@pytest.mark.asyncio
async def test_profile_import_without_session_returns_401(api: AsyncClient):
    _fuente(FakeCompanyLookupService(REGISTRO_WEB_EMPRESARIO))
    resp = await api.get("/suppliers/profile-import", params={"rut": IMPORT_RUT})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_profile_import_returns_draft(api: AsyncClient):
    await _login(api)
    _fuente(FakeCompanyLookupService(REGISTRO_WEB_EMPRESARIO))

    resp = await api.get("/suppliers/profile-import", params={"rut": IMPORT_RUT})

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "web-empresario"
    assert body["regions"] == ["Metropolitana"]
    assert body["sectors"] == [
        "Obras de Construcción e Infraestructura",
        "Mantención y Reparación",
    ]
    assert "pintura" in body["keywords"]
    assert isinstance(body["notices"], list)


@pytest.mark.asyncio
async def test_profile_import_invalid_rut_returns_400(api: AsyncClient):
    await _login(api)
    _fuente(FakeCompanyLookupService(REGISTRO_WEB_EMPRESARIO))

    resp = await api.get("/suppliers/profile-import", params={"rut": "76.668.304-0"})

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_profile_import_not_found_returns_404(api: AsyncClient):
    await _login(api)
    _fuente(FakeCompanyLookupService(error=CompanyNotFoundInSource("76668304-5")))

    resp = await api.get("/suppliers/profile-import", params={"rut": IMPORT_RUT})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_import_source_down_returns_502(api: AsyncClient):
    await _login(api)
    _fuente(FakeCompanyLookupService(error=CompanyLookupUnavailable("HTTP 500")))

    resp = await api.get("/suppliers/profile-import", params={"rut": IMPORT_RUT})

    assert resp.status_code == 502
    # El detalle técnico queda en los logs, no en la respuesta.
    assert "HTTP 500" not in resp.json()["detail"]


@pytest.mark.asyncio
async def test_profile_import_without_provider_returns_503(api: AsyncClient):
    await _login(api)
    _fuente(None)

    resp = await api.get("/suppliers/profile-import", params={"rut": IMPORT_RUT})

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_supplier_me_returns_own_company(api: AsyncClient):
    await _login(api)
    created = await api.post("/suppliers", json=SUPPLIER)
    assert created.status_code == 201

    resp = await api.get("/suppliers/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created.json()["id"]
    assert body["rut"] == SUPPLIER["rut"]


@pytest.mark.asyncio
async def test_crear_empresa_sin_barra_final_no_redirige(api: AsyncClient):
    """POST /suppliers (sin barra) crea la empresa en vez de responder un redirect.

    La ruta estaba declarada como "/" bajo el prefijo, así que su forma canónica
    era `/suppliers/`. Cuando el frontend pedía `/suppliers`, FastAPI respondía
    307 con una `Location` **absoluta**, construida con el host y el esquema que
    ve el propio backend. Detrás del proxy de Railway eso es `http://` y el
    dominio del backend, de modo que el navegador —en una página servida por
    HTTPS— bloqueaba el salto por contenido mixto:

        Mixed Content: ... requested an insecure resource
        'http://fesw-2026-production.up.railway.app/suppliers/'

    Y aunque la Location viniera en HTTPS el redirect seguiría siendo dañino:
    sacaría al navegador del dominio del frontend, y la cookie de sesión volvería
    a ser de tercera parte.

    Next quita la barra final antes de aplicar el rewrite, así que al backend
    siempre le llega la forma sin barra: esa tiene que ser la canónica.
    """
    await _login(api)

    resp = await api.post("/suppliers", json=SUPPLIER)

    assert resp.status_code == 201, (
        f"Se esperaba 201 y llegó {resp.status_code}. "
        f"Location: {resp.headers.get('location')!r}"
    )
    assert "location" not in resp.headers
