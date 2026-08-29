"""`POSTGRES_PASSWORD` no debería ser obligatoria cuando ya hay `DATABASE_URL`.

Los proveedores gestionados (Supabase, Neon, RDS) entregan la cadena completa, y
con el pooler el usuario viene como `postgres.<project-ref>`. En ese escenario los
`POSTGRES_*` no se usan para nada: `database_url` devuelve el override tal cual.

Aun así la aplicación no arrancaba sin `POSTGRES_PASSWORD`, así que había que
inventar un valor en las variables de Railway. Quien configure el despliegue sin
conocer el código no tiene forma de saber que ese valor da igual, y lo razonable
es que suponga lo contrario: que ahí va algo real.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "jwt_secret_key": "K" * 32,
}

URL_GESTIONADA = (
    "postgresql://postgres.abc123:clave@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
)


def _construir(**extra) -> Settings:
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


class TestCredencialDePostgres:
    def test_con_database_url_no_hace_falta_la_contrasena_suelta(self):
        s = _construir(database_url_override=URL_GESTIONADA)

        assert s.postgres_password is None
        assert s.database_url.startswith("postgresql+asyncpg://postgres.abc123:")

    def test_sin_database_url_sigue_siendo_obligatoria(self):
        """El compose local arma la conexión por piezas y sí la necesita."""
        with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
            _construir()

    def test_el_mensaje_explica_las_dos_salidas(self):
        """Un error de configuración debería decir cómo resolverlo."""
        with pytest.raises(ValidationError, match="DATABASE_URL"):
            _construir()

    def test_sin_override_la_contrasena_se_usa_para_armar_la_url(self):
        s = _construir(postgres_password="secreta", postgres_host="db")

        assert "secreta@db" in s.database_url

    def test_una_contrasena_vacia_no_cuenta(self):
        with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
            _construir(postgres_password="   ")
