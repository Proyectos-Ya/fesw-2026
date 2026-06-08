from unittest.mock import MagicMock
from uuid import uuid4

from app.domain.entities.resultado_matching import ResultadoMatching
from app.infrastructure.repositories.resultado_matching_repository import (
    ResultadoMatchingRepository,
)


def _make_repo() -> ResultadoMatchingRepository:
    return ResultadoMatchingRepository(session=MagicMock())


def _make_resultado(**kwargs) -> ResultadoMatching:
    defaults = dict(
        proveedor_id=uuid4(),
        licitacion_id=uuid4(),
        score_similitud=0.91,
        score_final=0.91,
        version_modelo="bge-m3-v1",
    )
    defaults.update(kwargs)
    return ResultadoMatching(**defaults)


# ---------------------------------------------------------------------------
# _to_model
# ---------------------------------------------------------------------------


def test_to_model_mapea_scores() -> None:
    resultado = _make_resultado(score_similitud=0.88, score_final=0.88)
    repo = _make_repo()

    model = repo._to_model(resultado)

    assert model.id == resultado.id
    assert model.score_similitud == 0.88
    assert model.score_final == 0.88
    assert model.score_reranker is None
    assert model.version_modelo == "bge-m3-v1"


def test_to_model_mapea_score_reranker_cuando_existe() -> None:
    resultado = _make_resultado(score_reranker=0.75, score_final=0.80)
    repo = _make_repo()

    model = repo._to_model(resultado)

    assert model.score_reranker == 0.75
    assert model.score_final == 0.80


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


def test_roundtrip_resultado_matching_sin_reranker() -> None:
    resultado = _make_resultado()
    repo = _make_repo()

    assert repo._to_entity(repo._to_model(resultado)) == resultado


def test_roundtrip_resultado_matching_con_reranker() -> None:
    resultado = _make_resultado(score_reranker=0.73, score_final=0.82)
    repo = _make_repo()

    assert repo._to_entity(repo._to_model(resultado)) == resultado


def test_roundtrip_preserva_ids() -> None:
    proveedor_id = uuid4()
    licitacion_id = uuid4()
    resultado = _make_resultado(
        proveedor_id=proveedor_id, licitacion_id=licitacion_id
    )
    repo = _make_repo()

    entity = repo._to_entity(repo._to_model(resultado))

    assert entity.proveedor_id == proveedor_id
    assert entity.licitacion_id == licitacion_id
