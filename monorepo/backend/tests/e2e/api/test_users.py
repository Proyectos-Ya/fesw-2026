import pytest
from httpx import AsyncClient

from tests.support.api_auth import autenticar

pytestmark = pytest.mark.asyncio


class TestOnboardingEndpoint:
    async def test_sin_sesion_devuelve_401(self, api: AsyncClient):
        res = await api.patch("/api/v1/users/me/onboarding")
        assert res.status_code == 401

    async def test_marcar_onboarding_completado_actualiza_estado(self, api: AsyncClient):
        user_id = await autenticar(api, email="onboarding@ejemplo.cl")

        me_antes = await api.get("/auth/me")
        assert me_antes.status_code == 200
        assert me_antes.json()["has_completed_onboarding"] is False

        # PATCH /api/v1/users/me/onboarding
        res = await api.patch("/api/v1/users/me/onboarding")
        assert res.status_code == 200
        data = res.json()
        assert data["has_completed_onboarding"] is True
        assert data["email"] == "onboarding@ejemplo.cl"

        # Verificar persistencia en el repositorio y en /auth/me
        usuario_db = await api.usuarios.get_by_id(user_id)
        assert usuario_db is not None
        assert usuario_db.has_completed_onboarding is True

        me_despues = await api.get("/auth/me")
        assert me_despues.status_code == 200
        assert me_despues.json()["has_completed_onboarding"] is True

    async def test_marcar_onboarding_alias_users_y_auth(self, api: AsyncClient):
        await autenticar(api, email="alias@ejemplo.cl")

        res_users = await api.patch("/users/me/onboarding")
        assert res_users.status_code == 200
        assert res_users.json()["has_completed_onboarding"] is True

        res_auth = await api.patch("/auth/me/onboarding")
        assert res_auth.status_code == 200
        assert res_auth.json()["has_completed_onboarding"] is True
