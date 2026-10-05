from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field
from qdrant_client.http.exceptions import UnexpectedResponse as QdrantException
from sqlalchemy.exc import SQLAlchemyError

from app.application.schemas.notification_schema import TenderDetailResponse
from app.application.schemas.ranking_telemetry_schema import (
    RecommendedTenderResponse,
    TenderInteractionRequest,
    TenderInteractionResponse,
)
from app.application.schemas.tender_schema import (
    TenderFilterCriteria,
    TenderSearchResult,
)
from app.application.services.recent_ranking_registry import RecentRankingRegistry
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.matching.score_tender_on_demand import (
    ScoreTenderOnDemandUseCase,
)
from app.application.use_cases.ranking_telemetry.log_ranking_impressions import (
    RankingImpressionLogger,
)
from app.application.use_cases.ranking_telemetry.record_tender_interaction import (
    RecordTenderInteractionUseCase,
)
from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.application.use_cases.tender.get_tender_detail import (
    GetTenderDetailUseCase,
)
from app.application.use_cases.tender.search_tenders import (
    DEFAULT_RESULT_LIMIT,
    MAX_RESULT_LIMIT,
    SearchTendersUseCase,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.saved_tender import SavedTender
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.deep_analysis_errors import (
    DeepAnalysisServiceError,
    InvalidPromptInstruction,
)
from app.domain.errors.matching_errors import (
    RecommendationsSaveError,
    ScoreCalculationError,
)
from app.domain.errors.saved_tender_errors import SavedTenderNotFound
from app.domain.errors.supplier_errors import (
    SupplierNotFoundForUser,
    SupplierVectorNotFound,
)
from app.domain.errors.tender_errors import (
    InvalidSearchCriteria,
    TenderClosedForAnalysis,
    TenderClosedForScoring,
    TenderNotFound,
)
from app.shared.datetime_utils import utc_now_naive
from app.shared.regions import region_id_by_name


def _resolve_region_ids(regions: list[str] | None) -> list[int] | None:
    """Traduce nombres de región a ids en el borde HTTP.

    El frontend filtra por nombre —es lo que muestra al usuario— y el criterio de
    búsqueda usa ids, que es lo que guarda el payload de Qdrant. Un nombre
    desconocido se rechaza en vez de ignorarse: ignorarlo ensancharía la búsqueda
    en silencio y el usuario vería resultados de regiones que no pidió.
    """
    if not regions:
        return None
    ids = []
    for name in regions:
        region_id = region_id_by_name(name)
        if region_id is None:
            raise InvalidSearchCriteria(f"Región desconocida: {name!r}.")
        ids.append(region_id)
    return ids


class DeepAnalysisRequest(BaseModel):
    """Cuerpo de la petición para generar o actualizar un análisis profundo."""

    prompt_instruction: str | None = Field(
        default=None,
        max_length=1000,
        description="Instrucción adicional para personalizar el análisis.",
    )
    force_regenerate: bool = Field(
        default=False,
        description="Indica si se debe forzar una nueva generación de análisis ignorando el caché.",
    )
    only_if_exists: bool = Field(
        default=False,
        description="Si es True, no genera el análisis si no existe y en su lugar retorna un error 404.",
    )


from app.application.schemas.deep_analysis_schema import DeepAnalysisResponse  # noqa: E402


class TenderScoreResponse(BaseModel):
    """Resultado de un cálculo de compatibilidad pedido por el usuario."""

    score_pct: int = Field(description="Compatibilidad en porcentaje (0-100).")
    calculated_at: datetime


def create_tender_router(
    get_rank_tenders_use_case: Callable,
    get_current_user: Callable,
    get_get_or_create_deep_analysis_use_case: Callable,
    get_list_saved_tenders_use_case: Callable,
    get_save_tender_use_case: Callable,
    get_unsave_tender_use_case: Callable,
    get_search_tenders_use_case: Callable,
    get_tender_detail_use_case: Callable,
    get_score_tender_on_demand_use_case: Callable,
    get_current_workspace_context: Callable | None = None,
    get_ranking_impression_logger: Callable | None = None,
    get_ranking_registry: Callable | None = None,
    get_record_tender_interaction_use_case: Callable | None = None,
) -> APIRouter:
    """
    Fábrica del router de licitaciones (tenders).
    Todas las rutas requieren sesión de usuario activa.
    """
    router = APIRouter(
        prefix="/tenders",
        tags=["Tenders"],
        dependencies=[Depends(get_current_user)],
    )

    def dummy_workspace() -> None:
        return None

    def dummy_none() -> None:
        return None

    actual_get_workspace = get_current_workspace_context or dummy_workspace
    # Sin telemetría cableada (tests de otros routers) `/recommended` no registra.
    actual_get_impression_logger = get_ranking_impression_logger or dummy_none
    actual_get_ranking_registry = get_ranking_registry or dummy_none

    def _empresa_activa(workspace_context: WorkspaceContext | None) -> UUID | None:
        return workspace_context.active_supplier_id if workspace_context else None

    # `/search` va antes que cualquier ruta con parámetro de path: declarada
    # después de un `/{tender_id}`, FastAPI intentaría interpretar "search" como
    # UUID. Hoy no hay conflicto, pero lo habrá al agregar el detalle (HdU 17).
    @router.get(
        "/search",
        response_model=TenderSearchResult,
        responses={
            422: {"description": "Criterios de búsqueda inválidos"},
            503: {
                "description": "No se pudo completar la búsqueda: el motor de "
                "búsqueda o la base de datos no están disponibles"
            },
        },
    )
    async def search_tenders(
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(actual_get_workspace)
        ],
        use_case: Annotated[SearchTendersUseCase, Depends(get_search_tenders_use_case)],
        q: Annotated[
            str | None,
            Query(
                max_length=200,
                description="Texto libre. Se busca por coincidencia de palabras "
                "(con sus variantes en español) en nombre y descripción. Vacío, "
                "y con solo estados vigentes, ordena por afinidad con la empresa.",
            ),
        ] = None,
        regions: Annotated[
            list[str] | None,
            Query(description="Nombres de región, tal como los expone la API."),
        ] = None,
        province_id: Annotated[
            int | None,
            Query(
                description="Id de provincia, tal como lo expone "
                "GET /catalogs/locations. Selección única, a diferencia de región."
            ),
        ] = None,
        commune_id: Annotated[
            int | None,
            Query(
                description="Id de comuna, tal como lo expone "
                "GET /catalogs/locations. Selección única, a diferencia de región."
            ),
        ] = None,
        status_codes: Annotated[
            list[str] | None,
            Query(
                description="Estados: publicada, cerrada, desierta o cancelada. "
                "Sin estado entran todos. Solo `publicada` sin texto ordena por "
                "afinidad con la empresa; con cualquier otro estado se ordena por "
                "fecha de cierre, la más reciente primero. Un estado desconocido "
                "responde 422."
            ),
        ] = None,
        closing_from: Annotated[datetime | None, Query()] = None,
        closing_to: Annotated[datetime | None, Query()] = None,
        published_from: Annotated[datetime | None, Query()] = None,
        published_to: Annotated[datetime | None, Query()] = None,
        min_amount: Annotated[float | None, Query(ge=0)] = None,
        max_amount: Annotated[float | None, Query(ge=0)] = None,
        limit: Annotated[
            int,
            Query(
                ge=1,
                le=MAX_RESULT_LIMIT,
                description=f"Tope de resultados por petición. Por defecto {DEFAULT_RESULT_LIMIT}, máximo {MAX_RESULT_LIMIT}.",
            ),
        ] = DEFAULT_RESULT_LIMIT,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        """Búsqueda manual de licitaciones con filtros por ubicación, estado, fechas y montos."""
        try:
            region_ids = _resolve_region_ids(regions)
            criteria = TenderFilterCriteria(
                region_ids=region_ids,
                province_id=province_id,
                commune_id=commune_id,
                status_codes=status_codes,
                closing_from=closing_from,
                closing_to=closing_to,
                published_from=published_from,
                published_to=published_to,
                min_amount=min_amount,
                max_amount=max_amount,
            )
            supplier_id = _empresa_activa(workspace_context)
            return await use_case.execute(
                user_id=current_user.id,
                supplier_id=supplier_id,
                q=q,
                criteria=criteria,
                limit=limit,
                offset=offset,
            )
        except InvalidSearchCriteria as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
            ) from e
        except (SQLAlchemyError, QdrantException, OSError) as e:
            # El criterio pide avisar que la búsqueda no se pudo completar, sin
            # bloquear el resto de la plataforma. Un 503 acotado a este endpoint
            # deja el resto de la navegación intacta.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "No se pudo completar la búsqueda en este momento. "
                    "Inténtalo nuevamente en unos minutos."
                ),
            ) from e

    @router.get(
        "/recommended",
        response_model=list[RecommendedTenderResponse],
        summary="Licitaciones recomendadas para la empresa activa",
        responses={
            404: {
                "description": "No se encontró el perfil de proveedor o su vector asociado"
            },
            503: {
                "description": "No se pudo guardar el ranking calculado; se puede reintentar"
            },
        },
    )
    async def get_recommended_tenders(
        request: Request,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(get_current_user)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(actual_get_workspace)
        ],
        use_case: Annotated[RankTendersUseCase, Depends(get_rank_tenders_use_case)],
        impression_logger: Annotated[
            RankingImpressionLogger | None, Depends(actual_get_impression_logger)
        ],
        ranking_registry: Annotated[
            RecentRankingRegistry | None, Depends(actual_get_ranking_registry)
        ],
        force_refresh: bool = False,
        track: Annotated[
            bool,
            Query(
                description="False para no registrar el ranking: lo usa la ficha, "
                "que pide la lista solo para encontrar una licitación."
            ),
        ] = True,
    ):
        """Licitaciones recomendadas para la empresa del usuario autenticado.

        Cada ítem trae `ranking_id` y su posición servida; las posiciones se
        guardan en segundo plano para medir el NDCG en producción.
        """
        try:
            supplier_id = _empresa_activa(workspace_context)
            resultados = await use_case.execute(
                user_id=current_user.id,
                supplier_id=supplier_id,
                force_refresh=force_refresh,
                request=request,
            )
        except SupplierNotFoundForUser as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except SupplierVectorNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except RecommendationsSaveError as e:
            # Transitorio: 503 para que el cliente sepa que puede reintentar.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
            ) from e

        ranking_id: UUID | None = None
        if (
            track
            and resultados
            and impression_logger is not None
            and ranking_registry is not None
        ):
            servido_en = utc_now_naive()
            ranking_id, es_nuevo = ranking_registry.resolve(
                user_id=current_user.id,
                supplier_id=resultados[0].supplier_id,
                model_version=resultados[0].model_version,
                tender_ids=[r.tender_id for r in resultados],
                now=servido_en,
            )
            # Se escribe después de responder: no cambia el orden ni la latencia.
            if es_nuevo:
                background_tasks.add_task(
                    impression_logger,
                    ranking_id,
                    current_user.id,
                    list(resultados),
                    servido_en,
                )
        # `dict(resultado)` y no `model_dump()`: deja el `Tender` anidado como
        # instancia y no lo vuelve a validar.
        return [
            RecommendedTenderResponse(
                **dict(resultado), ranking_id=ranking_id, ranking_position=posicion
            )
            for posicion, resultado in enumerate(resultados, start=1)
        ]

    # Declarada antes que las rutas con `{tender_id}` para que el segmento
    # estático "saved" nunca sea capturado como parámetro de path.
    @router.get("/saved", response_model=list[MatchingResult])
    async def get_saved_tenders(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ListSavedTendersUseCase, Depends(get_list_saved_tenders_use_case)
        ],
    ):
        """
        Retorna únicamente las licitaciones que el usuario autenticado marcó como de interés.
        """
        return await use_case.execute(user_id=current_user.id)

    @router.post(
        "/{tender_id}/saved",
        response_model=SavedTender,
        status_code=status.HTTP_201_CREATED,
        responses={
            404: {"description": "La licitación no existe"},
        },
    )
    async def save_tender(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[SaveTenderUseCase, Depends(get_save_tender_use_case)],
    ):
        """
        Marca una licitación como de interés para el usuario autenticado.

        Es idempotente: repetir la llamada no duplica la licitación en la lista.
        """
        try:
            return await use_case.execute(user_id=current_user.id, tender_id=tender_id)
        except TenderNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    @router.delete(
        "/{tender_id}/saved",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            404: {"description": "La licitación no está en la lista de guardadas"},
        },
    )
    async def unsave_tender(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[UnsaveTenderUseCase, Depends(get_unsave_tender_use_case)],
    ):
        """
        Retira una licitación de la lista de guardadas del usuario autenticado.
        """
        try:
            await use_case.execute(user_id=current_user.id, tender_id=tender_id)
        except SavedTenderNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e

    @router.post(
        "/{tender_id}/score",
        response_model=TenderScoreResponse,
        responses={
            404: {"description": "Licitación o proveedor no encontrado"},
            409: {"description": "La licitación ya cerró"},
            502: {"description": "No se pudo calcular la compatibilidad"},
        },
    )
    async def score_tender(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ScoreTenderOnDemandUseCase,
            Depends(get_score_tender_on_demand_use_case),
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(actual_get_workspace)
        ],
    ):
        """Calcula la compatibilidad de una licitación que el usuario eligió.

        El ranking solo puntúa su top-N, así que lo que llega del buscador o de
        las guardadas no tiene porcentaje. Este endpoint lo calcula cuando
        alguien lo pide —nunca solo— y lo deja guardado.
        """
        try:
            resultado = await use_case.execute(
                user_id=current_user.id,
                tender_id=tender_id,
                supplier_id=_empresa_activa(workspace_context),
            )
        except (SupplierNotFoundForUser, TenderNotFound) as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except TenderClosedForScoring as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except ScoreCalculationError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e

        # `final_score` viene del cálculo recién hecho, nunca en nulo.
        return TenderScoreResponse(
            score_pct=round((resultado.final_score or 0.0) * 100),
            calculated_at=resultado.calculated_at,
        )

    @router.post(
        "/{tender_id}/analysis",
        response_model=DeepAnalysisResponse,
        responses={
            400: {
                "description": "Instrucción de prompt inválida o detección de prompt injection"
            },
            404: {"description": "Licitación, proveedor o análisis no encontrado"},
            409: {"description": "La licitación ya cerró y no tiene análisis generado"},
            422: {"description": "Error de validación de entradas"},
            502: {
                "description": "Error de comunicación con el servicio de IA (Gemini) "
                "o al calcular la compatibilidad"
            },
        },
    )
    async def analyze_tender_compatibility(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            GetOrCreateDeepAnalysisUseCase,
            Depends(get_get_or_create_deep_analysis_use_case),
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(actual_get_workspace)
        ],
        request_body: DeepAnalysisRequest | None = None,
        # current_user: User = Depends(get_current_user),
        # use_case: GetOrCreateDeepAnalysisUseCase = Depends(
        #     get_get_or_create_deep_analysis_use_case
        # ),
    ):
        """
        Genera u obtiene el análisis profundo de compatibilidad IA para una licitación.

        Permite personalizar las instrucciones de análisis (opcional, máx 1000 caracteres) y forzar la regeneración.
        """
        prompt_instruction = request_body.prompt_instruction if request_body else None
        force_regenerate = request_body.force_regenerate if request_body else False
        only_if_exists = request_body.only_if_exists if request_body else False

        try:
            resultado = await use_case.execute(
                tender_id=tender_id,
                user_id=current_user.id,
                force_regenerate=force_regenerate,
                prompt_instruction=prompt_instruction,
                only_if_exists=only_if_exists,
                supplier_id=_empresa_activa(workspace_context),
            )
            if resultado.analysis is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El análisis de compatibilidad aún no ha sido generado.",
                )
            return DeepAnalysisResponse(
                **resultado.analysis.model_dump(),
                is_outdated=resultado.is_outdated,
            )
        except SupplierNotFoundForUser as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except TenderNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except TenderClosedForAnalysis as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except InvalidPromptInstruction as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except (DeepAnalysisServiceError, ScoreCalculationError) as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e

    if get_record_tender_interaction_use_case is not None:

        @router.post(
            "/{tender_id}/interactions",
            response_model=TenderInteractionResponse,
            status_code=status.HTTP_202_ACCEPTED,
            summary="Registra una interacción con una licitación (telemetría del ranking)",
            responses={
                404: {"description": "La licitación no existe"},
                422: {"description": "Tipo u origen desconocido"},
            },
        )
        async def record_tender_interaction(
            tender_id: UUID,
            body: TenderInteractionRequest,
            current_user: Annotated[User, Depends(get_current_user)],
            workspace_context: Annotated[
                WorkspaceContext | None, Depends(actual_get_workspace)
            ],
            use_case: Annotated[
                RecordTenderInteractionUseCase,
                Depends(get_record_tender_interaction_use_case),
            ],
        ):
            """Impresiones, clics y acciones sobre una licitación.

            Si `ranking_id` es de este usuario y empresa y la licitación estaba en
            él, cuenta para el NDCG; si no, se guarda sin atribuir.
            """
            try:
                resultado = await use_case.execute(
                    user_id=current_user.id,
                    supplier_id=_empresa_activa(workspace_context),
                    tender_id=tender_id,
                    kind=body.kind,
                    source=body.source,
                    ranking_id=body.ranking_id,
                    position=body.position,
                )
            except TenderNotFound as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
                ) from e
            return TenderInteractionResponse(
                recorded=resultado.recorded, attributed=resultado.attributed
            )

    # Va al final, después de `/search`, `/recommended` y `/saved`: es la ruta
    # más genérica y capturaría esos segmentos como si fueran un UUID.
    @router.get(
        "/{tender_id}",
        response_model=TenderDetailResponse,
        responses={404: {"description": "La licitación no existe"}},
    )
    async def get_tender_detail(
        tender_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            GetTenderDetailUseCase, Depends(get_tender_detail_use_case)
        ],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(actual_get_workspace)
        ],
    ):
        """Ficha de una licitación, incluidas las ya cerradas.

        `/recommended` filtra por `closing_at > now`, así que no sirve para
        abrir el enlace de una alerta enviada hace días. Acá la licitación se
        devuelve igual, marcada con `is_closed`, para que la interfaz pueda
        avisar que ya cerró en vez de decir que no existe.
        """
        try:
            detalle = await use_case.execute(
                user_id=current_user.id,
                tender_id=tender_id,
                supplier_id=_empresa_activa(workspace_context),
            )
        except TenderNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        return TenderDetailResponse(
            tender=detalle.tender,
            score_pct=(
                round(detalle.final_score * 100)
                if detalle.final_score is not None
                else None
            ),
            is_closed=detalle.is_closed,
        )

    return router
