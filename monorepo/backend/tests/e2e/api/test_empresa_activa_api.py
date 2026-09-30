"""Las rutas de una licitación operan sobre la empresa activa, no la propia (#260).

Con varias empresas, la ficha, el puntaje a pedido y la cotización resolvían la
empresa con `get_by_user_id`: siempre la primera de la que el usuario es dueño.
Un miembro invitado, sin empresa propia, directamente no tenía empresa ahí.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app import bootstrap
from app.application.use_cases.matching.score_tender_on_demand import (
    ScoreTenderOnDemandUseCase,
)
from app.application.use_cases.quotation import QuotationUseCase
from app.application.use_cases.tender.get_tender_detail import GetTenderDetailUseCase
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.quotation import Quotation, QuotationInput
from app.main import app
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemoryTenderRepository,
    armar_scorer,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion

SUB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
SUB_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


class InMemoryQuotationRepository:
    def __init__(self) -> None:
        self.quotations: dict[tuple[UUID, UUID], Quotation] = {}

    async def get(self, supplier_id: UUID, tender_id: UUID) -> Quotation | None:
        return self.quotations.get((supplier_id, tender_id))

    async def save(
        self, supplier_id: UUID, tender_id: UUID, data: QuotationInput
    ) -> Quotation:
        quotation = Quotation(
            # Sin los totales: son campos calculados y el modelo los rechaza.
            **data.model_dump(exclude={"total": True, "items": {"__all__": {"subtotal"}}}),
            id=uuid4(),
            supplier_id=supplier_id,
            tender_id=tender_id,
            updated_at=utc_now_naive(),
        )
        self.quotations[(supplier_id, tender_id)] = quotation
        return quotation


def _headers(api: AsyncClient, sub: str, email: str) -> dict[str, str]:
    api.directorio_de_identidad.confirmar(sub)
    token = api.claves.token(
        sub=sub, email=email, user_metadata={"full_name": email.split("@")[0]}
    )
    return {"Authorization": f"Bearer {token}"}


async def _crear_empresa(
    api: AsyncClient, headers: dict[str, str], rut: str, nombre: str
) -> str:
    resp = await api.post(
        "/suppliers",
        json={
            "rut": rut,
            "legal_name": nombre,
            "description": "Empresa de servicios generales para el sector público.",
            "regions": ["Metropolitana"],
            "sectors": ["Servicios"],
            "years_experience": 5,
            "num_employees": 10,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _unir(
    api: AsyncClient,
    admin: dict[str, str],
    invitado: dict[str, str],
    email: str,
    empresa_id: str,
    role: str = "member",
) -> None:
    inv = await api.post(
        "/workspaces/invitations",
        json={"supplier_id": empresa_id, "email": email, "role": role},
        headers=admin,
    )
    assert inv.status_code == 201, inv.text
    acc = await api.post(
        "/workspaces/invitations/accept",
        json={"token": inv.json()["token"]},
        headers=invitado,
    )
    assert acc.status_code == 200, acc.text


async def _cambiar(api: AsyncClient, headers: dict[str, str], empresa_id: str) -> None:
    resp = await api.post(
        "/workspaces/switch", json={"supplier_id": empresa_id}, headers=headers
    )
    assert resp.status_code == 200, resp.text


@pytest.fixture
def licitaciones(api: AsyncClient):
    """Casos de uso reales sobre dobles en memoria, compartiendo las empresas del cliente."""
    tenders = InMemoryTenderRepository()
    matching = InMemoryMatchingResultRepository()
    quotations = InMemoryQuotationRepository()
    suppliers = api.proveedores

    app.dependency_overrides[bootstrap.get_tender_detail_use_case] = lambda: (
        GetTenderDetailUseCase(
            tender_repo=tenders, supplier_repo=suppliers, matching_result_repo=matching
        )
    )
    app.dependency_overrides[bootstrap.get_score_tender_on_demand_use_case] = lambda: (
        ScoreTenderOnDemandUseCase(
            supplier_repo=suppliers,
            tender_repo=tenders,
            matching_result_repo=matching,
            scorer=armar_scorer(matching_result_repo=matching),
        )
    )
    app.dependency_overrides[bootstrap.get_quotation_use_case] = lambda: (
        QuotationUseCase(quotations, suppliers, tenders)
    )

    tender_id = uuid4()
    tenders.tenders[tender_id] = crear_licitacion(tender_id)
    return tender_id, matching, quotations


@pytest.fixture
async def dos_empresas(api: AsyncClient):
    """A es dueño de la Empresa 1 y miembro de la 2, con la 2 activa."""
    headers_a = _headers(api, SUB_A, "user_a@test.cl")
    headers_b = _headers(api, SUB_B, "user_b@test.cl")
    empresa_1 = await _crear_empresa(api, headers_a, "76.123.456-0", "Empresa Uno SpA")
    empresa_2 = await _crear_empresa(api, headers_b, "77.654.321-7", "Empresa Dos Ltda")
    await _unir(api, headers_b, headers_a, "user_a@test.cl", empresa_2)
    await _cambiar(api, headers_a, empresa_2)
    return headers_a, headers_b, UUID(empresa_1), UUID(empresa_2)


def _resultado(supplier_id: UUID, tender_id: UUID, score: float) -> MatchingResult:
    return MatchingResult(
        supplier_id=supplier_id,
        tender_id=tender_id,
        final_score=score,
        model_version="test",
    )


@pytest.mark.asyncio
async def test_ficha_muestra_el_puntaje_de_la_empresa_activa(
    api: AsyncClient, licitaciones, dos_empresas
):
    tender_id, matching, _ = licitaciones
    headers_a, _, empresa_1, empresa_2 = dos_empresas
    await matching.save_bulk([_resultado(empresa_1, tender_id, 0.2)])
    await matching.save_bulk([_resultado(empresa_2, tender_id, 0.9)])

    resp = await api.get(f"/tenders/{tender_id}", headers=headers_a)

    assert resp.status_code == 200, resp.text
    assert resp.json()["score_pct"] == 90


@pytest.mark.asyncio
async def test_puntaje_a_pedido_se_guarda_en_la_empresa_activa(
    api: AsyncClient, licitaciones, dos_empresas
):
    tender_id, matching, _ = licitaciones
    headers_a, _, empresa_1, empresa_2 = dos_empresas

    resp = await api.post(f"/tenders/{tender_id}/score", headers=headers_a)

    assert resp.status_code == 200, resp.text
    assert await matching.get_by_proveedor_and_licitacion(empresa_2, tender_id)
    assert not await matching.get_by_proveedor_and_licitacion(empresa_1, tender_id)


@pytest.mark.asyncio
async def test_cotizacion_se_guarda_en_la_empresa_activa(
    api: AsyncClient, licitaciones, dos_empresas
):
    tender_id, _, quotations = licitaciones
    headers_a, _, _, empresa_2 = dos_empresas
    body = {
        "items": [
            {"description": "Cemento", "unit": "saco", "quantity": "2", "unit_price": "100"}
        ]
    }

    guardada = await api.put(f"/tenders/{tender_id}/quotation", json=body, headers=headers_a)
    leida = await api.get(f"/tenders/{tender_id}/quotation", headers=headers_a)

    assert guardada.status_code == 200, guardada.text
    assert guardada.json()["supplier_id"] == str(empresa_2)
    assert leida.status_code == 200, leida.text
    assert list(quotations.quotations) == [(empresa_2, tender_id)]


@pytest.mark.asyncio
async def test_miembro_sin_empresa_propia_puede_pedir_el_puntaje(
    api: AsyncClient, licitaciones
):
    tender_id, matching, _ = licitaciones
    headers_b = _headers(api, SUB_B, "user_b@test.cl")
    headers_c = _headers(api, SUB_C, "user_c@test.cl")
    empresa_2 = await _crear_empresa(api, headers_b, "77.654.321-7", "Empresa Dos Ltda")
    await _unir(api, headers_b, headers_c, "user_c@test.cl", empresa_2)
    await _cambiar(api, headers_c, empresa_2)

    resp = await api.post(f"/tenders/{tender_id}/score", headers=headers_c)

    assert resp.status_code == 200, resp.text
    assert await matching.get_by_proveedor_and_licitacion(UUID(empresa_2), tender_id)


@pytest.mark.asyncio
async def test_editar_perfil_sin_permiso_en_la_empresa_activa_es_403(
    api: AsyncClient, dos_empresas
):
    headers_a, _, empresa_1, _ = dos_empresas

    resp = await api.patch(
        "/suppliers/me", json={"trade_name": "Intento"}, headers=headers_a
    )

    assert resp.status_code == 403, resp.text
    propia = await api.proveedores.get_by_id(empresa_1)
    assert propia.trade_name != "Intento"


@pytest.mark.asyncio
async def test_editar_perfil_edita_la_empresa_activa(api: AsyncClient):
    headers_a = _headers(api, SUB_A, "user_a@test.cl")
    headers_b = _headers(api, SUB_B, "user_b@test.cl")
    empresa_1 = await _crear_empresa(api, headers_a, "76.123.456-0", "Empresa Uno SpA")
    empresa_2 = await _crear_empresa(api, headers_b, "77.654.321-7", "Empresa Dos Ltda")
    await _unir(api, headers_b, headers_a, "user_a@test.cl", empresa_2, role="admin")
    await _cambiar(api, headers_a, empresa_2)

    resp = await api.patch(
        "/suppliers/me", json={"trade_name": "Dos Renovada"}, headers=headers_a
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == empresa_2
    assert (await api.proveedores.get_by_id(UUID(empresa_2))).trade_name == "Dos Renovada"
    assert (await api.proveedores.get_by_id(UUID(empresa_1))).trade_name != "Dos Renovada"
