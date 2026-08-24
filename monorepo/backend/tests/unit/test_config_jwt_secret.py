"""La clave de firma de sesiones no puede ser débil ni la de ejemplo.

El bug que estos tests previenen: `jwt_secret_key` tenía como valor por defecto
la cadena `"dev-insecure-secret-change-me"`, publicada en el repositorio. Como la
variable tampoco estaba en el `.env`, la aplicación firmaba las sesiones reales
con ella y cualquiera podía falsificar un token de cualquier usuario, sin que
nada fallara ni lo advirtiera.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

# Valores mínimos para construir Settings sin depender del .env del desarrollador.
BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
}

CLAVE_VALIDA = "K" * 32


def _construir(secreto: str, **extra) -> Settings:
    """Construye Settings aislado del `.env` del desarrollador."""
    return Settings(_env_file=None, jwt_secret_key=secreto, **BASE, **extra)  # type: ignore[arg-type,call-arg]


class TestClaveDeFirma:
    def test_acepta_una_clave_de_32_bytes(self):
        assert _construir(CLAVE_VALIDA).jwt_secret_key == CLAVE_VALIDA

    def test_rechaza_la_clave_de_ejemplo_del_repositorio(self):
        with pytest.raises(ValidationError, match="publicada en el repositorio"):
            _construir("dev-insecure-secret-change-me")

    def test_rechaza_claves_de_menos_de_32_bytes(self):
        with pytest.raises(ValidationError, match="al menos 32"):
            _construir("K" * 31)

    def test_cuenta_bytes_y_no_caracteres(self):
        """31 caracteres acentuados son más de 32 bytes en UTF-8 y sí sirven.

        Al revés importa más: contar caracteres dejaría pasar claves que en
        bytes —que es lo que consume HMAC— quedan por debajo del mínimo.
        """
        clave = "ñ" * 16  # 32 bytes exactos, 16 caracteres
        assert len(clave) == 16
        assert _construir(clave).jwt_secret_key == clave

    def test_no_hay_valor_por_defecto(self, monkeypatch: pytest.MonkeyPatch):
        """Sin clave, la aplicación no arranca en vez de arrancar insegura.

        Hay que aislarlo de las dos fuentes que sí la tienen: el `.env` del
        desarrollador (de ahí `_env_file=None`) y la variable de entorno real,
        que en pydantic-settings tiene prioridad sobre el archivo.
        """
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        with pytest.raises(ValidationError, match="jwt_secret_key"):
            Settings(_env_file=None, **BASE)  # type: ignore[arg-type,call-arg]


class TestCookieDeSesion:
    """`auth_cookie_secure` tenía `False` fijo y viajaba así a cualquier despliegue.

    Ahora se deriva de `is_dev`, para que el caso peligroso —desplegar sin
    declarar la variable— caiga del lado seguro.
    """

    def test_en_desarrollo_secure_queda_apagado(self):
        assert _construir(CLAVE_VALIDA, is_dev=True).auth_cookie_secure is False

    def test_fuera_de_desarrollo_secure_queda_encendido(self):
        assert _construir(CLAVE_VALIDA, is_dev=False).auth_cookie_secure is True

    def test_se_puede_declarar_explicitamente(self):
        """Un despliegue tras un proxy que termina TLS puede necesitar forzarlo."""
        s = _construir(CLAVE_VALIDA, is_dev=False, auth_cookie_secure=False)
        assert s.auth_cookie_secure is False

    def test_samesite_none_exige_secure(self):
        """El navegador descarta SameSite=None sin Secure y la sesión no viaja."""
        with pytest.raises(ValidationError, match="AUTH_COOKIE_SAMESITE=none"):
            _construir(
                CLAVE_VALIDA,
                is_dev=True,
                auth_cookie_samesite="none",
                auth_cookie_secure=False,
            )


class TestCorsOrigins:
    def test_por_defecto_solo_el_front_local(self):
        assert _construir(CLAVE_VALIDA).cors_origins_list == ["http://localhost:3000"]

    def test_acepta_varios_separados_por_coma_y_recorta_espacios(self):
        s = _construir(CLAVE_VALIDA, cors_origins="https://a.cl, https://b.cl ")
        assert s.cors_origins_list == ["https://a.cl", "https://b.cl"]

    def test_ignora_entradas_vacias(self):
        """Una coma sobrante no debe producir un origen vacío en la lista."""
        s = _construir(CLAVE_VALIDA, cors_origins="https://a.cl,,")
        assert s.cors_origins_list == ["https://a.cl"]


class TestUrlDeBaseDeDatos:
    """`DATABASE_URL` gana sobre los POSTGRES_* y llega siempre con driver async.

    Los proveedores gestionados entregan la URL con esquema `postgresql://`, que
    SQLAlchemy resuelve al driver SÍNCRONO. Pegarla tal cual produce un error
    confuso sobre greenlets en la primera consulta, no al configurar.
    """

    def test_sin_override_se_compone_desde_las_piezas(self):
        url = _construir(CLAVE_VALIDA, postgres_host="db", postgres_db="x").database_url
        assert url == "postgresql+asyncpg://postgres:x@db:5432/x"

    def test_el_override_gana_sobre_las_piezas(self):
        s = _construir(
            CLAVE_VALIDA,
            postgres_host="ignorado",
            database_url_override="postgresql+asyncpg://u:p@real:5432/d",
        )
        assert "real" in s.database_url and "ignorado" not in s.database_url

    @pytest.mark.parametrize(
        "entrada",
        [
            "postgresql://u:p@db.abc.supabase.co:5432/postgres",
            "postgres://u:p@db.abc.supabase.co:5432/postgres",
            "postgresql+asyncpg://u:p@db.abc.supabase.co:5432/postgres",
        ],
    )
    def test_siempre_termina_en_asyncpg(self, entrada: str):
        s = _construir(CLAVE_VALIDA, database_url_override=entrada)
        assert s.database_url.startswith("postgresql+asyncpg://")
        # La contraseña y el host tienen que sobrevivir a la normalización.
        assert "u:p@db.abc.supabase.co:5432/postgres" in s.database_url


class TestSentenciasPreparadas:
    def test_por_defecto_no_se_tocan(self):
        assert _construir(CLAVE_VALIDA).db_disable_prepared_statements is False

    def test_desactivarlas_apaga_los_dos_caches_de_asyncpg(self, monkeypatch):
        """Apagar solo statement_cache_size deja el problema a medias."""
        import app.infrastructure.db as db

        monkeypatch.setattr(
            db.settings, "db_disable_prepared_statements", True, raising=False
        )
        args = db._connect_args()
        assert args["statement_cache_size"] == 0
        assert args["prepared_statement_cache_size"] == 0
