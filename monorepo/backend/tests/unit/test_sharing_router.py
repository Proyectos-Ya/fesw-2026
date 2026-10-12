from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.application.use_cases.sharing.tender_sharing import (
    CreatedShareLink,
    SharedTender,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.supplier_member import MemberRole, WorkspaceContext
from app.domain.entities.tender import Tender
from app.domain.entities.tender_share_link import TenderShareLink
from app.domain.errors.sharing_errors import (
    ShareLinkExpired,
    ShareLinkForbidden,
    ShareLinkNotFound,
    ShareLinkRevoked,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.routers.sharing import (
    create_public_sharing_router,
    create_sharing_router,
)

AHORA = datetime(2026, 9, 28, 12, 0, 0)


@pytest.fixture
def api():
    contexto = WorkspaceContext(
        user_id=uuid4(),
        active_supplier_id=uuid4(),
        active_supplier_name="Constructora Andes",
        role=MemberRole.MEMBER,
        permissions=["view_matches"],
    )
    tender_id = uuid4()
    enlace, _ = TenderShareLink.emitir(
        tender_id=tender_id,
        supplier_id=contexto.active_supplier_id,
        created_by=contexto.user_id,
        now=AHORA,
    )
    crear, listar, revocar, abrir = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    crear.execute.return_value = CreatedShareLink(
        link=enlace, url="https://app.test/compartido/abc"
    )
    listar.execute.return_value = [enlace]
    revocar.execute.return_value = None

    app = FastAPI()

    def workspace():
        return contexto

    app.include_router(
        create_sharing_router(workspace, lambda: crear, lambda: listar, lambda: revocar)
    )
    app.include_router(create_public_sharing_router(lambda: abrir))
    return SimpleNamespace(
        client=TestClient(app),
        app=app,
        workspace=workspace,
        contexto=contexto,
        tender_id=tender_id,
        enlace=enlace,
        crear=crear,
        listar=listar,
        revocar=revocar,
        abrir=abrir,
        path=f"/tenders/{tender_id}/share-links",
    )


class TestCompartir:
    def test_crea_el_enlace_y_devuelve_la_url_con_su_vencimiento(self, api):
        respuesta = api.client.post(api.path)

        assert respuesta.status_code == 201
        assert respuesta.json() == {
            "id": str(api.enlace.id),
            "url": "https://app.test/compartido/abc",
            "created_at": "2026-09-28T12:00:00Z",
            "expires_at": "2026-10-05T12:00:00Z",
        }
        api.crear.execute.assert_awaited_once_with(api.contexto, api.tender_id)

    def test_la_lista_no_expone_la_url_ni_el_hash(self, api):
        cuerpo = api.client.get(api.path).json()

        assert set(cuerpo[0]) == {"id", "created_at", "expires_at"}

    def test_revocar_responde_204(self, api):
        respuesta = api.client.delete(f"{api.path}/{api.enlace.id}")

        assert respuesta.status_code == 204
        api.revocar.execute.assert_awaited_once_with(
            api.contexto, api.tender_id, api.enlace.id
        )

    def test_revocar_uno_ajeno_es_404(self, api):
        api.revocar.execute.side_effect = ShareLinkNotFound()

        assert api.client.delete(f"{api.path}/{uuid4()}").status_code == 404

    def test_licitacion_inexistente_es_404(self, api):
        api.crear.execute.side_effect = TenderNotFound(api.tender_id)

        assert api.client.post(api.path).status_code == 404

    def test_sin_permiso_es_403(self, api):
        api.crear.execute.side_effect = ShareLinkForbidden()

        assert api.client.post(api.path).status_code == 403

    def test_sin_sesion_es_401(self, api):
        def denegado():
            raise HTTPException(401, "No autenticado")

        api.app.dependency_overrides[api.workspace] = denegado

        assert api.client.post(api.path).status_code == 401
        assert api.client.get(api.path).status_code == 401
        assert api.client.delete(f"{api.path}/{uuid4()}").status_code == 401
        api.crear.execute.assert_not_awaited()


def _compartido(**cambios: object) -> SharedTender:
    tender = Tender(
        code="1057539-228-COT26",
        name="Mantención de áreas verdes",
        status_id=1,
        status_code="publicada",
        published_at=AHORA - timedelta(days=2),
        closing_at=datetime(2099, 1, 1),
        last_change_at=AHORA,
        buyer_rut="61.980.170-9",
        buyer_name="Municipalidad de Providencia",
        buyer_unit="Operaciones",
        available_amount_clp=5_000_000,
    )
    datos: dict[str, object] = {
        "tender": tender,
        "supplier_name": "Constructora Andes",
        "score_pct": 84,
        "analysis": DeepAnalysis(
            tender_id=tender.id,
            supplier_id=uuid4(),
            compatibility_score=84,
            recommendation="Postular",
            justification="El rubro coincide.",
        ),
        "expires_at": AHORA + timedelta(days=7),
    }
    datos.update(cambios)
    return SharedTender(**datos)  # type: ignore[arg-type]


class TestVistaPublica:
    def test_muestra_el_detalle_sin_pedir_sesion(self, api):
        # Criterio 2: el cliente no manda ninguna cabecera de autenticación.
        api.abrir.execute.return_value = _compartido()

        respuesta = api.client.get("/shared/token-valido")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["name"] == "Mantención de áreas verdes"
        assert cuerpo["score_pct"] == 84
        assert cuerpo["analysis"]["recommendation"] == "Postular"
        assert cuerpo["supplier_name"] == "Constructora Andes"
        api.abrir.execute.assert_awaited_once_with("token-valido")

    def test_no_expone_ids_internos(self, api):
        api.abrir.execute.return_value = _compartido()

        cuerpo = api.client.get("/shared/token-valido").json()

        assert "id" not in cuerpo
        assert "supplier_id" not in cuerpo["analysis"]
        assert "buyer_rut" not in cuerpo

    def test_sin_analisis_lo_informa_como_nulo(self, api):
        api.abrir.execute.return_value = _compartido(analysis=None, score_pct=None)

        cuerpo = api.client.get("/shared/token-valido").json()

        assert cuerpo["analysis"] is None
        assert cuerpo["score_pct"] is None

    def test_no_se_guarda_en_cache_ni_se_indexa(self, api):
        api.abrir.execute.return_value = _compartido()

        respuesta = api.client.get("/shared/token-valido")

        assert respuesta.headers["cache-control"] == "no-store"
        assert respuesta.headers["x-robots-tag"] == "noindex"

    def test_caducado_es_410_con_su_codigo(self, api):
        # Criterio 6.
        api.abrir.execute.side_effect = ShareLinkExpired()

        respuesta = api.client.get("/shared/token-vencido")

        assert respuesta.status_code == 410
        assert respuesta.json()["code"] == "share_link_expired"
        assert respuesta.headers["cache-control"] == "no-store"

    def test_revocado_es_410_con_otro_codigo(self, api):
        # Criterio 7.
        api.abrir.execute.side_effect = ShareLinkRevoked()

        respuesta = api.client.get("/shared/token-revocado")

        assert respuesta.status_code == 410
        assert respuesta.json()["code"] == "share_link_revoked"

    def test_token_desconocido_es_404(self, api):
        api.abrir.execute.side_effect = ShareLinkNotFound()

        assert api.client.get("/shared/inventado").status_code == 404
