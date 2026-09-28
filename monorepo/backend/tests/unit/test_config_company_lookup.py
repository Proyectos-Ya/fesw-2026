"""Fuente de datos de empresas para importar el perfil por RUT (HdU 16).

Se elige una sola fuente por variable de entorno. Sin configurar, la importación
queda apagada y el wizard funciona como antes; con una fuente elegida y sin
credencial, la aplicación no arranca —el error aparecería recién cuando un
usuario apriete el botón.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "supabase_url": "http://127.0.0.1:54321",
}


def _construir(**extra) -> Settings:
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


def test_por_defecto_no_hay_fuente_configurada():
    assert _construir().company_lookup_provider == "none"


def test_solo_acepta_las_fuentes_conocidas():
    with pytest.raises(ValidationError):
        _construir(company_lookup_provider="ruts-info")


@pytest.mark.parametrize("proveedor", ["sre", "web-empresario"])
def test_una_fuente_sin_credencial_impide_arrancar(proveedor):
    with pytest.raises(ValidationError, match="COMPANY_LOOKUP_API_KEY"):
        _construir(company_lookup_provider=proveedor)


def test_credencial_en_blanco_cuenta_como_ausente():
    with pytest.raises(ValidationError, match="COMPANY_LOOKUP_API_KEY"):
        _construir(company_lookup_provider="sre", company_lookup_api_key="   ")


@pytest.mark.parametrize(
    "proveedor,url",
    [
        ("sre", "https://sre.cl"),
        ("web-empresario", "https://api-sii-chile.webempresario.com"),
    ],
)
def test_cada_fuente_tiene_su_host_por_defecto(proveedor, url):
    s = _construir(company_lookup_provider=proveedor, company_lookup_api_key="k")
    assert s.company_lookup_url == url


def test_el_host_se_puede_sobrescribir_sin_barra_final():
    s = _construir(
        company_lookup_provider="sre",
        company_lookup_api_key="k",
        company_lookup_base_url="https://proxy.local/",
    )
    assert s.company_lookup_url == "https://proxy.local"
