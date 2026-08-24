"""El fallback del reranker no debe ser silencioso.

`MockRerankerService` devuelve 1.0 para todas las candidatas, así que si el
reranker real no se construye la aplicación sigue respondiendo, pero el orden
de las recomendaciones pasa a ser arbitrario. Antes eso ocurría sin dejar
rastro en los logs: un `except Exception` desnudo se tragaba el error.

Estos tests fijan las dos mitades de la corrección: en desarrollo el fallback
sigue existiendo pero deja constancia del error real, y fuera de desarrollo
deja de ser un fallback y pasa a ser un fallo de arranque.
"""

import logging

import pytest

from app import bootstrap as bootstrap_module
from app.bootstrap import MockRerankerService, build_reranker_service
from app.config import settings


class _RerankerRoto:
    """Ocupa el lugar de BgeRerankerService y falla al construirse."""

    def __init__(self):
        raise RuntimeError("onnxruntime no pudo reservar memoria")


@pytest.fixture
def reranker_roto(monkeypatch):
    monkeypatch.setattr(bootstrap_module, "BgeRerankerService", _RerankerRoto)


def test_desactivado_por_configuracion_usa_el_mock(monkeypatch):
    monkeypatch.setattr(settings, "disable_reranker", True)

    assert isinstance(build_reranker_service(), MockRerankerService)


def test_en_desarrollo_el_fallo_cae_al_mock(monkeypatch, reranker_roto):
    monkeypatch.setattr(settings, "disable_reranker", False)
    monkeypatch.setattr(settings, "is_dev", True)

    assert isinstance(build_reranker_service(), MockRerankerService)


def test_en_desarrollo_el_fallo_queda_registrado(monkeypatch, reranker_roto, caplog):
    """Lo que costó una sesión de diagnóstico: que el error real fuera visible."""
    monkeypatch.setattr(settings, "disable_reranker", False)
    monkeypatch.setattr(settings, "is_dev", True)

    with caplog.at_level(logging.ERROR):
        build_reranker_service()

    registro = "\n".join(r.getMessage() for r in caplog.records)
    # El motivo original, no solo un "falló el reranker" genérico.
    assert "onnxruntime no pudo reservar memoria" in registro
    # Y la consecuencia, que es lo que nadie deducía del silencio.
    assert "MockRerankerService" in registro
    # Con traza: sin ella no se sabe en qué punto reventó la construcción.
    assert any(r.exc_info for r in caplog.records)


def test_fuera_de_desarrollo_el_fallo_impide_arrancar(monkeypatch, reranker_roto):
    """En producción, degradarse en silencio es peor que no arrancar."""
    monkeypatch.setattr(settings, "disable_reranker", False)
    monkeypatch.setattr(settings, "is_dev", False)

    with pytest.raises(RuntimeError, match="onnxruntime no pudo reservar memoria"):
        build_reranker_service()
