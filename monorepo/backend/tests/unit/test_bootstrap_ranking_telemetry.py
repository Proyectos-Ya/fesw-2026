"""El cableado de la telemetría del ranking en el composition root (plan 233, decisión 8)."""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI

from app import bootstrap
from app.application.services.recent_ranking_registry import RecentRankingRegistry
from app.domain.entities.matching_result import MatchingResult
from tests.unit.application.fakes import FakeEmbeddingService, FakeRerankerService


class SesionRota:
    """Una sesión cuya apertura falla, como una base caída."""

    async def __aenter__(self):
        raise OSError("la base no responde")

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_registrar_impresiones_nunca_lanza_aunque_la_base_falle(monkeypatch):
    # Corre como tarea en segundo plano: un fallo de telemetría no puede
    # convertirse en un error para el usuario.
    monkeypatch.setattr(bootstrap, "async_session_maker", lambda: SesionRota())
    resultados = [
        MatchingResult(supplier_id=uuid4(), tender_id=uuid4(), model_version="m1")
    ]

    await bootstrap.registrar_impresiones_de_ranking(
        uuid4(), uuid4(), resultados, datetime(2026, 10, 3, 12, 0)
    )


def test_bootstrap_registra_el_registro_de_rankings_y_la_ruta_de_interacciones(
    monkeypatch,
):
    monkeypatch.setattr(bootstrap, "build_embedding_service", FakeEmbeddingService)
    monkeypatch.setattr(bootstrap, "build_reranker_service", FakeRerankerService)
    app = FastAPI()

    bootstrap.bootstrap(app)

    assert isinstance(app.state.ranking_registry, RecentRankingRegistry)
    rutas = {
        (ruta.path, metodo)
        for ruta in app.routes
        for metodo in getattr(ruta, "methods", None) or ()
    }
    assert ("/tenders/{tender_id}/interactions", "POST") in rutas


def test_el_getter_del_registro_lee_app_state():
    registro = RecentRankingRegistry()

    class Peticion:
        class app:  # noqa: N801
            class state:  # noqa: N801
                ranking_registry = registro

    assert bootstrap.get_ranking_registry(Peticion()) is registro  # type: ignore[arg-type]


def test_el_registrador_inyectado_es_la_funcion_de_segundo_plano():
    assert bootstrap.get_ranking_impression_logger() is (
        bootstrap.registrar_impresiones_de_ranking
    )
