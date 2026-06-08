from app.application.repositories.proveedor_repository import IProveedorRepository
from app.application.repositories.resultado_matching_repository import (
    IResultadoMatchingRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.text_builder import TextBuilder
from app.application.services.vector_store_service import (
    FiltrosVectoriales,
    IVectorStoreService,
)
from app.domain.entities.resultado_matching import ResultadoMatching
from app.domain.errors.proveedor_errors import ProveedorNoEncontrado
from app.domain.models.matching_schema import MatchRequest, MatchResult


class MatchLicitacionesUseCase:

    def __init__(
        self,
        proveedor_repo: IProveedorRepository,
        embedding_service: IEmbeddingService,
        vector_store: IVectorStoreService,
        resultado_matching_repo: IResultadoMatchingRepository,
        text_builder: TextBuilder,
        version_modelo: str,
    ) -> None:
        self._proveedor_repo = proveedor_repo
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._resultado_matching_repo = resultado_matching_repo
        self._text_builder = text_builder
        self._version_modelo = version_modelo

    async def execute(self, request: MatchRequest) -> MatchResult:
        proveedor = await self._proveedor_repo.get_by_id(request.proveedor_id)
        if proveedor is None:
            raise ProveedorNoEncontrado(str(request.proveedor_id))

        texto = self._text_builder.build_from_proveedor(proveedor)
        vectors = await self._embedding_service.embed([texto])
        query_vector = vectors[0]

        filtros = FiltrosVectoriales(
            region=request.region,
            monto_min=request.monto_min,
        )
        search_results = await self._vector_store.search(
            query_vector=query_vector,
            top_k=request.top_k,
            filtros=filtros,
        )

        if not search_results:
            return MatchResult(resultados=[], version_modelo=self._version_modelo)

        resultados = [
            ResultadoMatching(
                proveedor_id=request.proveedor_id,
                licitacion_id=sr.licitacion_id,
                score_similitud=sr.score,
                score_final=sr.score,
                version_modelo=self._version_modelo,
            )
            for sr in search_results
        ]

        await self._resultado_matching_repo.save_bulk(resultados)

        return MatchResult(resultados=resultados, version_modelo=self._version_modelo)
