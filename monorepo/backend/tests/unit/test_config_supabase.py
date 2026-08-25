"""Configuración de Supabase Auth: de dónde salen las claves y a quién se le cree.

El backend ya no emite sesiones: las verifica. Para eso necesita saber tres
cosas —dónde está el JWKS, qué emisor acepta y para qué audiencia— y las tres
tienen un modo de fallar en silencio que estos tests cierran.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

# Valores mínimos para construir Settings sin depender del `.env` del desarrollador.
BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "jwt_secret_key": "K" * 32,
}

URL_NUBE = "https://abcdefghijklm.supabase.co"


def _construir(**extra) -> Settings:
    """Construye Settings aislado del `.env` del desarrollador."""
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


class TestUrlDeSupabase:
    def test_no_hay_valor_por_defecto(self, monkeypatch: pytest.MonkeyPatch):
        """Sin URL no hay dónde buscar las claves, y conviene saberlo al arrancar.

        Un default apuntando a localhost haría que un despliegue mal configurado
        arranque bien y rechace todas las sesiones, que es mucho más difícil de
        diagnosticar que no arrancar.
        """
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        with pytest.raises(ValidationError, match="supabase_url"):
            Settings(_env_file=None, **BASE)  # type: ignore[arg-type,call-arg]

    def test_se_acepta_tal_cual_viene(self):
        assert _construir(supabase_url=URL_NUBE).supabase_url == URL_NUBE


class TestEmisorAceptado:
    def test_se_deriva_de_la_url(self):
        s = _construir(supabase_url=URL_NUBE)
        assert s.jwt_issuer == f"{URL_NUBE}/auth/v1"

    def test_la_barra_final_no_duplica_la_del_path(self):
        """`https://x.supabase.co//auth/v1` no coincide con el `iss` del token."""
        s = _construir(supabase_url=f"{URL_NUBE}/")
        assert s.jwt_issuer == f"{URL_NUBE}/auth/v1"

    def test_se_puede_declarar_explicitamente(self):
        """Dentro de Docker, el host que alcanza a Supabase no es el que firma.

        El contenedor llega por `host.docker.internal`, pero GoTrue emite
        `iss: http://127.0.0.1:54321/auth/v1`. Sin poder separarlos, o falla la
        descarga del JWKS o falla la validación del emisor.
        """
        s = _construir(
            supabase_url="http://host.docker.internal:54321",
            supabase_jwt_issuer="http://127.0.0.1:54321/auth/v1",
            is_dev=True,
        )
        assert s.jwt_issuer == "http://127.0.0.1:54321/auth/v1"
        assert "host.docker.internal" in s.jwks_url


class TestUrlDelJwks:
    def test_apunta_al_descubrimiento_estandar(self):
        s = _construir(supabase_url=URL_NUBE)
        assert s.jwks_url == f"{URL_NUBE}/auth/v1/.well-known/jwks.json"


class TestAudiencia:
    def test_por_defecto_es_la_de_un_usuario_conectado(self):
        assert (
            _construir(supabase_url=URL_NUBE).supabase_jwt_audience == "authenticated"
        )


class TestExigeHttpsFueraDeDesarrollo:
    """El JWKS viaja por esa conexión: sobre HTTP es sustituible.

    Quien esté en la red puede responder con su propia clave pública y firmar
    sesiones de cualquier usuario. Es el mismo tipo de agujero silencioso que la
    clave de firma publicada, y merece la misma defensa en el arranque.
    """

    def test_en_desarrollo_http_es_valido(self):
        s = _construir(supabase_url="http://127.0.0.1:54321", is_dev=True)
        assert s.supabase_url.startswith("http://")

    def test_fuera_de_desarrollo_http_no_arranca(self):
        with pytest.raises(ValidationError, match="https"):
            _construir(supabase_url="http://127.0.0.1:54321", is_dev=False)

    def test_fuera_de_desarrollo_https_es_valido(self):
        assert _construir(supabase_url=URL_NUBE, is_dev=False).supabase_url == URL_NUBE
