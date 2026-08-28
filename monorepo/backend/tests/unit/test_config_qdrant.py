"""La conexión a Qdrant tiene que poder apuntar a un servicio gestionado.

El bug que estos tests previenen: `qdrant_url` se armaba siempre como
`http://{host}:{port}` y no existía forma de pasar una API key. Contra Qdrant
Cloud —que exige `https://` y el header `api-key`— eso no es un error de
configuración visible, sino una conexión que se rechaza en tiempo de arranque.

Los `QDRANT_HOST`/`QDRANT_HTTP_PORT` siguen sirviendo para el compose local, así
que el override tiene que convivir con ellos, no reemplazarlos.
"""

from app.config import Settings

BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "jwt_secret_key": "K" * 32,
}

URL_CLOUD = "https://abc-123.eu-central-1-0.aws.cloud.qdrant.io:6333"


def _construir(**extra) -> Settings:
    """Construye Settings aislado del `.env` del desarrollador."""
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


class TestUrlDeQdrant:
    def test_sin_override_arma_la_url_desde_host_y_puerto(self):
        s = _construir(qdrant_host="qdrant", qdrant_http_port=6333)
        assert s.qdrant_url == "http://qdrant:6333"

    def test_el_override_tiene_prioridad_sobre_host_y_puerto(self):
        s = _construir(
            qdrant_host="qdrant", qdrant_http_port=6333, qdrant_url_override=URL_CLOUD
        )
        assert s.qdrant_url == URL_CLOUD

    def test_el_override_se_lee_desde_la_variable_qdrant_url(self, monkeypatch):
        """El nombre de la variable de entorno es QDRANT_URL, no el del campo."""
        monkeypatch.setenv("QDRANT_URL", URL_CLOUD)
        assert Settings(_env_file=None, **BASE).qdrant_url == URL_CLOUD  # type: ignore[arg-type]

    def test_descarta_la_barra_final(self):
        """Un `/` al final concatenado con la ruta del cliente da `//`.

        Los paneles de Qdrant Cloud entregan la URL con barra final tanto como
        sin ella, y copiarla tal cual no debería cambiar el comportamiento.
        """
        assert _construir(qdrant_url_override=URL_CLOUD + "/").qdrant_url == URL_CLOUD

    def test_ignora_un_override_vacio(self):
        """Una variable declarada pero vacía es ausencia, no una URL válida."""
        s = _construir(qdrant_host="qdrant", qdrant_url_override="")
        assert s.qdrant_url == "http://qdrant:6333"


class TestApiKeyDeQdrant:
    def test_por_defecto_no_hay_api_key(self):
        """El Qdrant del compose local no la pide, y mandarla vacía es un error."""
        assert _construir().qdrant_api_key is None

    def test_se_lee_desde_la_variable_qdrant_api_key(self, monkeypatch):
        monkeypatch.setenv("QDRANT_API_KEY", "secreto")
        assert Settings(_env_file=None, **BASE).qdrant_api_key == "secreto"  # type: ignore[arg-type]

    def test_una_api_key_vacia_equivale_a_no_tenerla(self):
        assert _construir(qdrant_api_key="") is not None
        assert _construir(qdrant_api_key="").qdrant_api_key is None
