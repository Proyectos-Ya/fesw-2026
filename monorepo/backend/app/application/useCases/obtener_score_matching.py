from app.application.repositories.resultado_matching_repository import (
    IResultadoMatchingRepository,
)
from app.domain.entities.resultado_matching import ResultadoMatching
from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado
from app.domain.models.matching_schema import ObtenerScoreRequest


class ObtenerScoreMatchingUseCase:

    def __init__(self, resultado_matching_repo: IResultadoMatchingRepository) -> None:
        self._resultado_matching_repo = resultado_matching_repo

    async def execute(self, request: ObtenerScoreRequest) -> ResultadoMatching:
        resultado = await self._resultado_matching_repo.get_by_proveedor_and_licitacion(
            request.proveedor_id,
            request.licitacion_id,
        )
        if resultado is None:
            raise ScoreMatchingNoEncontrado(
                str(request.proveedor_id),
                str(request.licitacion_id),
            )
        return resultado
