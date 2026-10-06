"""Flujo completo del enlace compartido contra la aplicación real (HdU 19).

La autenticación y la resolución de la empresa activa son las de verdad; solo
los repositorios son dobles en memoria.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.bootstrap.repositories import (
    get_matching_result_repo,
    get_tender_repo,
    get_tender_share_link_repo,
)
from app.domain.entities.tender import Tender
from app.main import app
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.sharing_fakes import InMemoryTenderShareLinkRepository

EMPRESA = {
    "rut": "76.123.456-0",
    "legal_name": "Constructora Andes SpA",
    "trade_name": "Constructora Andes",
    "description": "Empresa de mantención de áreas verdes y obras menores.",
    "regions": ["Metropolitana"],
    "sectors": ["Construcción"],
    "years_experience": 6,
    "num_employees": 20,
}


@pytest.fixture
def repos():
    tenders = InMemoryTenderRepository()
    links = InMemoryTenderShareLinkRepository()
    app.dependency_overrides[get_tender_repo] = lambda: tenders
    app.dependency_overrides[get_tender_share_link_repo] = lambda: links
    app.dependency_overrides[get_matching_result_repo] = (
        InMemoryMatchingResultRepository
    )
    tender = Tender(
        code="1057539-228-COT26",
        name="Mantención de áreas verdes",
        status_id=1,
        status_code="publicada",
        published_at=utc_now_naive() - timedelta(days=1),
        closing_at=utc_now_naive() + timedelta(days=10),
        last_change_at=utc_now_naive(),
        buyer_rut="61.980.170-9",
        buyer_name="Municipalidad de Providencia",
        buyer_unit="Operaciones",
    )
    tenders.tenders[tender.id] = tender
    return tender


async def _representante(api: AsyncClient) -> dict[str, str]:
    sub = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    api.directorio_de_identidad.confirmar(sub)
    token = api.claves.token(
        sub=sub, email="rep@andes.cl", user_metadata={"full_name": "Representante"}
    )
    headers = {"Authorization": f"Bearer {token}"}
    creada = await api.post("/suppliers", json=EMPRESA, headers=headers)
    assert creada.status_code == 201
    return headers


async def test_compartir_abrir_sin_sesion_y_revocar(api: AsyncClient, repos):
    headers = await _representante(api)
    ruta = f"/tenders/{repos.id}/share-links"

    # Criterio 1: la URL es única y vence en 7 días.
    creado = await api.post(ruta, headers=headers)
    assert creado.status_code == 201
    enlace = creado.json()
    token = enlace["url"].rsplit("/compartido/", 1)[1]
    otro = (await api.post(ruta, headers=headers)).json()
    assert otro["url"] != enlace["url"]

    # Criterio 2: un tercero la abre sin sesión.
    api.cookies.clear()
    publico = await api.get(f"/shared/{token}")
    assert publico.status_code == 200
    assert publico.json()["name"] == "Mantención de áreas verdes"
    assert publico.json()["supplier_name"] == "Constructora Andes"

    # Criterio 7: revocado, deja de funcionar al instante.
    revocado = await api.delete(f"{ruta}/{enlace['id']}", headers=headers)
    assert revocado.status_code == 204
    despues = await api.get(f"/shared/{token}")
    assert despues.status_code == 410
    assert despues.json()["code"] == "share_link_revoked"

    # El revocado ya no aparece en la lista; el otro sigue vigente.
    vigentes = (await api.get(ruta, headers=headers)).json()
    assert [e["id"] for e in vigentes] == [otro["id"]]


async def test_compartir_exige_sesion(api: AsyncClient, repos):
    assert (await api.post(f"/tenders/{repos.id}/share-links")).status_code == 401


async def test_un_token_inventado_es_404(api: AsyncClient, repos):
    assert (await api.get("/shared/token-inventado")).status_code == 404
