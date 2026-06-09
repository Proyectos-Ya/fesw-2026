from uuid import uuid4

from app.application.repositories.tender_repository import ITenderRepository as ILicitacionRepository
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.mercado_publico_service import IMercadoPublicoService
from app.application.services.text_builder import TextBuilder
from app.application.services.vector_store_service import IVectorStoreService
from app.domain.entities.tender import Tender as Licitacion
from app.domain.models.tender_schema import IngestRequest, IngestResult


class IngestLicitacionesUseCase:

    def __init__(
        self,
        mercado_publico: IMercadoPublicoService,
        licitacion_repo: ILicitacionRepository,
        embedding_service: IEmbeddingService,
        vector_store: IVectorStoreService,
        text_builder: TextBuilder,
        version_modelo: str,
    ) -> None:
        self._mercado_publico = mercado_publico
        self._licitacion_repo = licitacion_repo
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._text_builder = text_builder
        self._version_modelo = version_modelo

    async def execute(self, request: IngestRequest) -> IngestResult:
        await self._vector_store.ensure_collection()

        lista = await self._mercado_publico.fetch_licitaciones(
            request.estado, request.limit, request.offset
        )

        if not lista:
            return IngestResult(
                procesadas=0, duplicadas=0, errores=0,
                version_modelo=self._version_modelo,
            )

        nuevas: list[Licitacion] = []
        duplicadas_count = 0

        for licitacion in lista:
            existente = await self._licitacion_repo.get_by_codigo_externo(
                licitacion.codigo_externo
            )
            if existente:
                duplicadas_count += 1
            else:
                nuevas.append(licitacion)

        if not nuevas:
            return IngestResult(
                procesadas=0, duplicadas=duplicadas_count, errores=0,
                version_modelo=self._version_modelo,
            )

        texts = [self._text_builder.build_from_licitacion(lic) for lic in nuevas]

        try:
            vectors = await self._embedding_service.embed(texts)
        except Exception:
            return IngestResult(
                procesadas=0, duplicadas=duplicadas_count, errores=len(nuevas),
                version_modelo=self._version_modelo,
            )

        procesadas = 0
        errores = 0

        for licitacion, vector in zip(nuevas, vectors, strict=True):
            try:
                vector_id = uuid4()
                payload: dict[str, str | float | None] = {
                    "licitacion_id": str(licitacion.id),
                    "estado": licitacion.estado,
                    "region": licitacion.region,
                    "fecha_cierre": licitacion.fecha_cierre.timestamp(),
                    "monto_estimado": licitacion.monto_estimado,
                }
                await self._vector_store.upsert(vector_id, vector, payload)
                licitacion_indexada = licitacion.model_copy(
                    update={
                        "qdrant_vector_id": vector_id,
                        "version_modelo": self._version_modelo,
                    }
                )
                await self._licitacion_repo.save(licitacion_indexada)
                procesadas += 1
            except Exception:
                errores += 1

        return IngestResult(
            procesadas=procesadas,
            duplicadas=duplicadas_count,
            errores=errores,
            version_modelo=self._version_modelo,
        )
