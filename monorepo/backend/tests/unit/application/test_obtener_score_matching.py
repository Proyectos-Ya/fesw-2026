from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.repositories.resultado_matching_repository import (
    IResultadoMatchingRepository,
)
from app.application.useCases.obtener_score_matching import ObtenerScoreMatchingUseCase
from app.domain.entities.resultado_matching import ResultadoMatching
from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado
from app.domain.models.matching_schema import ObtenerScoreRequest

PROVEEDOR_ID = uuid4()
LICITACION_ID = uuid4()


def _make_resultado() -> ResultadoMatching:
    return ResultadoMatching(
        proveedor_id=PROVEEDOR_ID,
        licitacion_id=LICITACION_ID,
        score_similitud=0.91,
        score_final=0.91,
        version_modelo="bge-m3-v1",
    )


@pytest.fixture
def repo() -> AsyncMock:
    return AsyncMock(spec=IResultadoMatchingRepository)


@pytest.fixture
def use_case(repo: AsyncMock) -> ObtenerScoreMatchingUseCase:
    return ObtenerScoreMatchingUseCase(resultado_matching_repo=repo)


@pytest.fixture
def request_default() -> ObtenerScoreRequest:
    return ObtenerScoreRequest(proveedor_id=PROVEEDOR_ID, licitacion_id=LICITACION_ID)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_score_encontrado_retorna_resultado_matching(
    use_case: ObtenerScoreMatchingUseCase,
    repo: AsyncMock,
    request_default: ObtenerScoreRequest,
) -> None:
    repo.get_by_proveedor_and_licitacion.return_value = _make_resultado()

    resultado = await use_case.execute(request_default)

    assert isinstance(resultado, ResultadoMatching)
    assert resultado.proveedor_id == PROVEEDOR_ID
    assert resultado.licitacion_id == LICITACION_ID
    assert resultado.score_similitud == 0.91


# ---------------------------------------------------------------------------
# Score no encontrado
# ---------------------------------------------------------------------------


async def test_score_no_encontrado_lanza_excepcion(
    use_case: ObtenerScoreMatchingUseCase,
    repo: AsyncMock,
    request_default: ObtenerScoreRequest,
) -> None:
    repo.get_by_proveedor_and_licitacion.return_value = None

    with pytest.raises(ScoreMatchingNoEncontrado):
        await use_case.execute(request_default)


async def test_error_contiene_proveedor_id(
    use_case: ObtenerScoreMatchingUseCase,
    repo: AsyncMock,
    request_default: ObtenerScoreRequest,
) -> None:
    repo.get_by_proveedor_and_licitacion.return_value = None

    with pytest.raises(ScoreMatchingNoEncontrado) as exc_info:
        await use_case.execute(request_default)

    assert exc_info.value.proveedor_id == str(PROVEEDOR_ID)


async def test_error_contiene_licitacion_id(
    use_case: ObtenerScoreMatchingUseCase,
    repo: AsyncMock,
    request_default: ObtenerScoreRequest,
) -> None:
    repo.get_by_proveedor_and_licitacion.return_value = None

    with pytest.raises(ScoreMatchingNoEncontrado) as exc_info:
        await use_case.execute(request_default)

    assert exc_info.value.licitacion_id == str(LICITACION_ID)


# ---------------------------------------------------------------------------
# Delegación al repositorio
# ---------------------------------------------------------------------------


async def test_ids_correctos_pasados_al_repositorio(
    use_case: ObtenerScoreMatchingUseCase,
    repo: AsyncMock,
    request_default: ObtenerScoreRequest,
) -> None:
    repo.get_by_proveedor_and_licitacion.return_value = _make_resultado()

    await use_case.execute(request_default)

    repo.get_by_proveedor_and_licitacion.assert_called_once_with(
        PROVEEDOR_ID, LICITACION_ID
    )
