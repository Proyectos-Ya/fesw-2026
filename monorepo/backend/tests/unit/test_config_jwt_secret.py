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


def _construir(secreto: str) -> Settings:
    return Settings(jwt_secret_key=secreto, **BASE)  # type: ignore[arg-type]


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
