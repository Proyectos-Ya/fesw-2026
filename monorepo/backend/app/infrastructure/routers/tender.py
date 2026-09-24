from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from qdrant_client.http.exceptions import UnexpectedResponse as QdrantException
from sqlalchemy.exc import SQLAlchemyError

from app.application.schemas.notification_schema import TenderDetailResponse
from app.application.schemas.tender_schema import (
    TenderFilterCriteria,
    TenderSearchResult,
)
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.matching.score_tender_on_demand import (
    ScoreTenderOnDemandUseCase,
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
from app.domain.errors.matching_errors import ScoreCalculationError
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


class DeepAnalysisResponse(DeepAnalysis):
    """El análisis más si dejó de estar al día.

    La ficha lo consulta sin generar, así que necesita distinguir "vigente" de
    "escrito con datos anteriores" para ofrecer el botón de actualizar.
    """

    is_outdated: bool = False


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

    dummy_workspace = lambda: None
    actual_get_workspace = get_current_workspace_context or dummy_workspace

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
        use_case: Annotated[SearchTendersUseCase, Depends(get_search_tenders_use_case)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(actual_get_workspace)
        ],
        q: Annotated[
            str | None,
            Query(
                max_length=200,
                description="Texto libre. Se busca por significado, no por "
                "coincidencia literal. Vacío ordena por afinidad con la empresa.",
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
            Query(description="Estados: publicada, cerrada, desierta, adjudicada..."),
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
            supplier_id = (
                workspace_context.active_supplier_id if workspace_context else None
            )
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
        response_model=list[MatchingResult],
        responses={
            404: {
                "description": "No se encontró el perfil de proveedor o su vector asociado"
            },
        },
    )
    async def get_recommended_tenders(
        request: Request,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[RankTendersUseCase, Depends(get_rank_tenders_use_case)],
        workspace_context: Annotated[
            WorkspaceContext | None, Depends(actual_get_workspace)
        ],
        force_refresh: bool = False,
    ):
        """Licitaciones recomendadas para la empresa del usuario autenticado."""
        try:
            supplier_id = (
                workspace_context.active_supplier_id if workspace_context else None
            )
            return await use_case.execute(
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
    ):
        """Calcula la compatibilidad de una licitación que el usuario eligió.

        El ranking solo puntúa su top-N, así que lo que llega del buscador o de
        las guardadas no tiene porcentaje. Este endpoint lo calcula cuando
        alguien lo pide —nunca solo— y lo deja guardado.
        """
        try:
            resultado = await use_case.execute(
                user_id=current_user.id, tender_id=tender_id
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
            409: {
                "description": "La licitación ya cerró y no tiene análisis generado"
            },
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
    ):
        """Ficha de una licitación, incluidas las ya cerradas.

        `/recommended` filtra por `closing_at > now`, así que no sirve para
        abrir el enlace de una alerta enviada hace días. Acá la licitación se
        devuelve igual, marcada con `is_closed`, para que la interfaz pueda
        avisar que ya cerró en vez de decir que no existe.
        """
        try:
            detalle = await use_case.execute(
                user_id=current_user.id, tender_id=tender_id
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
