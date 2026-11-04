import pytest
from httpx import AsyncClient

from tests.support.api_auth import autenticar

pytestmark = pytest.mark.asyncio


class TestOnboardingEndpoint:
    async def test_sin_sesion_devuelve_401(self, api: AsyncClient):
        res = await api.patch("/api/v1/users/me/onboarding", json={"tour_name": "home"})
        assert res.status_code == 401

    async def test_marcar_onboarding_completado_actualiza_estado_independiente(self, api: AsyncClient):
        user_id = await autenticar(api, email="onboarding@ejemplo.cl")

        me_antes = await api.get("/auth/me")
        assert me_antes.status_code == 200
        assert me_antes.json()["tour_home_completed"] is False
        assert me_antes.json()["tour_detail_completed"] is False
        assert me_antes.json()["tour_draft_completed"] is False

        # PATCH /api/v1/users/me/onboarding para tour 'home'
        res_home = await api.patch("/api/v1/users/me/onboarding", json={"tour_name": "home"})
        assert res_home.status_code == 200
        data_home = res_home.json()
        assert data_home["tour_home_completed"] is True
        assert data_home["tour_detail_completed"] is False
        assert data_home["tour_draft_completed"] is False

        # PATCH para tour 'detail'
        res_detail = await api.patch("/api/v1/users/me/onboarding", json={"tour_name": "detail"})
        assert res_detail.status_code == 200
        data_detail = res_detail.json()
        assert data_detail["tour_home_completed"] is True
        assert data_detail["tour_detail_completed"] is True
        assert data_detail["tour_draft_completed"] is False

        # PATCH para tour 'draft'
        res_draft = await api.patch("/api/v1/users/me/onboarding", json={"tour_name": "draft"})
        assert res_draft.status_code == 200
        data_draft = res_draft.json()
        assert data_draft["tour_home_completed"] is True
        assert data_draft["tour_detail_completed"] is True
        assert data_draft["tour_draft_completed"] is True

        # Verificar persistencia en el repositorio y en /auth/me
        usuario_db = await api.usuarios.get_by_id(user_id)
        assert usuario_db is not None
        assert usuario_db.tour_home_completed is True
        assert usuario_db.tour_detail_completed is True
        assert usuario_db.tour_draft_completed is True

        me_despues = await api.get("/auth/me")
        assert me_despues.status_code == 200
        assert me_despues.json()["tour_home_completed"] is True
        assert me_despues.json()["tour_detail_completed"] is True
        assert me_despues.json()["tour_draft_completed"] is True

    async def test_marcar_onboarding_alias_users_y_auth(self, api: AsyncClient):
        await autenticar(api, email="alias@ejemplo.cl")

        res_users = await api.patch("/users/me/onboarding", json={"tour_name": "home"})
        assert res_users.status_code == 200
        assert res_users.json()["tour_home_completed"] is True

        res_auth = await api.patch("/auth/me/onboarding", json={"tour_name": "detail"})
        assert res_auth.status_code == 200
        assert res_auth.json()["tour_detail_completed"] is True
