"""La fuente de datos de empresas se elige por configuración, sin tocar código."""

import pytest

from app.bootstrap import build_company_lookup_service
from app.config import settings
from app.infrastructure.services.company_lookup.http_company_lookup_service import (
    SreLookupService,
    WebEmpresarioLookupService,
)


def test_sin_fuente_la_importacion_queda_apagada(monkeypatch):
    monkeypatch.setattr(settings, "company_lookup_provider", "none")

    assert build_company_lookup_service() is None


@pytest.mark.parametrize(
    "proveedor,clase",
    [("sre", SreLookupService), ("web-empresario", WebEmpresarioLookupService)],
)
def test_construye_la_fuente_elegida(monkeypatch, proveedor, clase):
    monkeypatch.setattr(settings, "company_lookup_provider", proveedor)
    monkeypatch.setattr(settings, "company_lookup_api_key", "k")

    assert isinstance(build_company_lookup_service(), clase)
