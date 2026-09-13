"""El borde donde se decide en quién cree la API.

Los casos negativos pesan más que el positivo: cada token que se acepte de más
es una sesión válida de cualquier usuario. El verificador que corre acá es el
real; lo único sustituido es de dónde salen las claves públicas.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from tests.support.api_auth import SUB_POR_DEFECTO, autenticar

pytestmark = pytest.mark.asyncio


def _autorizar(api: AsyncClient, token: str) -> None:
    api.headers["Authorization"] = f"Bearer {token}"


class TestSinSesion:
    async def test_sin_encabezado_devuelve_401(self, api: AsyncClient):
        assert (await api.get("/auth/me")).status_code == 401

    async def test_un_token_ilegible_devuelve_401(self, api: AsyncClient):
        _autorizar(api, "no-es-un-jwt")
        assert (await api.get("/auth/me")).status_code == 401


class TestTokenRechazado:
    """Cada uno de estos aceptado de más es una suplantación."""

    async def test_expirado(self, api: AsyncClient):
        _autorizar(api, api.claves.token(expira_en=timedelta(hours=-1)))
        assert (await api.get("/auth/me")).status_code == 401

    async def test_de_otro_emisor(self, api: AsyncClient):
        _autorizar(api, api.claves.token(emisor="https://otro-proyecto.supabase.co"))
        assert (await api.get("/auth/me")).status_code == 401

    async def test_para_otra_audiencia(self, api: AsyncClient):
        _autorizar(api, api.claves.token(audiencia="otra-app"))
        assert (await api.get("/auth/me")).status_code == 401

    async def test_firmado_con_hs256_y_la_clave_publica(self, api: AsyncClient):
        """Confusión de algoritmo: el JWKS publica esa clave a quien la pida."""
        _autorizar(api, api.claves.token_hs256())
        assert (await api.get("/auth/me")).status_code == 401

    async def test_de_una_sesion_anonima(self, api: AsyncClient):
        _autorizar(api, api.claves.token(is_anonymous=True))
        assert (await api.get("/auth/me")).status_code == 401

    async def test_con_rol_de_servicio(self, api: AsyncClient):
        _autorizar(api, api.claves.token(rol="service_role"))
        assert (await api.get("/auth/me")).status_code == 401


class TestAprovisionamiento:
    async def test_la_primera_peticion_crea_el_perfil_local(self, api: AsyncClient):
        id_local = await autenticar(api, email="nueva@ejemplo.cl", full_name="Nueva")

        assert (await api.usuarios.get_by_id(id_local)).email == "nueva@ejemplo.cl"

    async def test_el_id_local_no_es_el_sub_de_supabase(self, api: AsyncClient):
        """Las claves foráneas del esquema apuntan al nuestro, no al del proveedor."""
        id_local = await autenticar(api)

        assert str(id_local) != SUB_POR_DEFECTO

    async def test_la_segunda_peticion_devuelve_el_mismo_perfil(self, api: AsyncClient):
        primero = await autenticar(api)

        segundo = (await api.get("/auth/me")).json()["id"]

        assert str(primero) == segundo
        assert len(api.usuarios.users) == 1

    async def test_sin_nombre_en_el_token_usa_la_parte_local_del_correo(
        self, api: AsyncClient
    ):
        api.directorio_de_identidad.confirmar(SUB_POR_DEFECTO)
        _autorizar(api, api.claves.token(email="ana.diaz@ejemplo.cl", user_metadata={}))

        assert (await api.get("/auth/me")).json()["full_name"] == "ana.diaz"


class TestVerificacionDelCorreo:
    """Sale del padrón de GoTrue, nunca del token."""

    async def test_una_cuenta_confirmada_queda_verificada(self, api: AsyncClient):
        await autenticar(api, verificado=True)

        assert (await api.get("/auth/me")).json()["email_verified"] is True

    async def test_una_cuenta_sin_confirmar_igual_puede_entrar(self, api: AsyncClient):
        """No bloquea el acceso: lo que se corta es el correo, y eso vendrá después."""
        await autenticar(api, verificado=False)

        respuesta = await api.get("/auth/me")
        assert respuesta.status_code == 200
        assert respuesta.json()["email_verified"] is False

    async def test_no_se_cree_el_email_verified_del_user_metadata(
        self, api: AsyncClient
    ):
        """`user_metadata` lo escribe el propio usuario: no puede auto-verificarse."""
        _autorizar(
            api,
            api.claves.token(user_metadata={"email_verified": True, "full_name": "A"}),
        )

        assert (await api.get("/auth/me")).json()["email_verified"] is False

    async def test_confirmar_despues_se_refleja_en_la_siguiente_peticion(
        self, api: AsyncClient
    ):
        await autenticar(api, verificado=False)

        api.directorio_de_identidad.confirmar(SUB_POR_DEFECTO)

        assert (await api.get("/auth/me")).json()["email_verified"] is True


class TestCuentaDesactivada:
    async def test_una_cuenta_inactiva_no_entra(self, api: AsyncClient):
        """`active` es decisión nuestra: el token de Supabase sigue siendo válido."""
        id_local = await autenticar(api)
        usuario = await api.usuarios.get_by_id(id_local)
        await api.usuarios.save(usuario.model_copy(update={"active": False}))

        assert (await api.get("/auth/me")).status_code == 401
