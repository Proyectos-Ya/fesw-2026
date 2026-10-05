"""Router FastAPI para los contratos de la extensión de navegador (Plan 233, Decisión 7)."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.application.repositories.extension_repository import (
    IExtensionInstallationRepository,
)
from app.application.schemas.extension_schema import (
    ExtensionAttachmentCheckRequest,
    ExtensionAttachmentCheckResponse,
    ExtensionCapabilitiesResponse,
    ExtensionHeartbeatRequest,
    ExtensionHeartbeatResponse,
    ExtensionJobLeaseRequest,
    ExtensionJobLeaseResponse,
    ExtensionJobResultRequest,
    ExtensionJobResultResponse,
    ExtensionPairingConfirmRequest,
    ExtensionPairingConfirmResponse,
    ExtensionPairingStartRequest,
    ExtensionPairingStartResponse,
)
from app.application.use_cases.extension.check_extension_attachments import (
    CheckExtensionAttachmentsUseCase,
)
from app.application.use_cases.extension.get_extension_capabilities import (
    GetExtensionCapabilitiesUseCase,
)
from app.application.use_cases.extension.lease_fetch_jobs import (
    LeaseFetchJobsUseCase,
)
from app.application.use_cases.extension.pair_extension import (
    PairExtensionUseCase,
)
from app.application.use_cases.extension.report_job_result import (
    ReportJobResultUseCase,
)
from app.domain.entities.user import User
from app.domain.errors.extension_errors import (
    DailyFetchQuotaExceeded,
    ExtensionInstallationNotFound,
    ExtensionJobNotFound,
    InvalidPairingTicketError,
    PairingTicketExpiredError,
)
from app.shared.datetime_utils import utc_now_naive


def _to_dep(dep_or_instance: Any) -> Callable:
    """Convierte una instancia o un callable a una dependencia válida para FastAPI."""
    if callable(dep_or_instance) and not hasattr(dep_or_instance, "execute"):
        return dep_or_instance
    return lambda: dep_or_instance


def create_extension_router(
    capabilities_use_case: GetExtensionCapabilitiesUseCase | Callable,
    pair_extension_use_case: PairExtensionUseCase | Callable,
    check_attachments_use_case: CheckExtensionAttachmentsUseCase | Callable,
    lease_jobs_use_case: LeaseFetchJobsUseCase | Callable,
    report_job_result_use_case: ReportJobResultUseCase | Callable,
    installation_repo: IExtensionInstallationRepository | Callable,
    get_current_user: Callable | None = None,
    get_optional_workspace_context: Callable | None = None,
) -> APIRouter:
    """Fábrica del router de la extensión de navegador."""
    router = APIRouter(prefix="/extension", tags=["Extension"])

    dep_capabilities = _to_dep(capabilities_use_case)
    dep_pair = _to_dep(pair_extension_use_case)
    dep_check = _to_dep(check_attachments_use_case)
    dep_lease = _to_dep(lease_jobs_use_case)
    dep_report = _to_dep(report_job_result_use_case)
    dep_installation_repo = _to_dep(installation_repo)

    @router.get(
        "/capabilities",
        summary="Consultar capacidades operativas y banderas de la extensión",
        response_model=ExtensionCapabilitiesResponse,
    )
    def get_capabilities(
        use_case: Annotated[GetExtensionCapabilitiesUseCase, Depends(dep_capabilities)],
    ) -> ExtensionCapabilitiesResponse:
        """Entrega flags operativos, límites y hosts soportados de Mercado Público."""
        return use_case.execute()

    if get_current_user:
        @router.post(
            "/pairing/start",
            summary="Iniciar emparejamiento web-extensión para usuario autenticado",
            response_model=ExtensionPairingStartResponse,
        )
        def start_pairing(
            body: ExtensionPairingStartRequest,
            current_user: Annotated[User, Depends(get_current_user)],
            workspace: Annotated[
                object,
                Depends(get_optional_workspace_context or (lambda: None)),
            ],
            use_case: Annotated[PairExtensionUseCase, Depends(dep_pair)],
        ) -> ExtensionPairingStartResponse:
            """Genera un ticket efímero de vinculación con TTL de 300 segundos."""
            workspace_id = getattr(workspace, "workspace_id", None)
            return use_case.start_pairing(
                user_id=current_user.id,
                workspace_id=workspace_id,
            )

    @router.post(
        "/pairing/confirm",
        summary="Confirmar emparejamiento con ticket efímero desde la extensión",
        response_model=ExtensionPairingConfirmResponse,
    )
    async def confirm_pairing(
        body: ExtensionPairingConfirmRequest,
        use_case: Annotated[PairExtensionUseCase, Depends(dep_pair)],
    ) -> ExtensionPairingConfirmResponse:
        """Valida el ticket entregado por el Content Script bridge y registra la instalación."""
        try:
            return await use_case.confirm_pairing(body)
        except InvalidPairingTicketError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.message
            ) from e
        except PairingTicketExpiredError as e:
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail=e.message
            ) from e

    @router.post(
        "/installations/heartbeat",
        summary="Actualizar latido de la instalación",
        response_model=ExtensionHeartbeatResponse,
    )
    async def heartbeat(
        body: ExtensionHeartbeatRequest,
        repo: Annotated[IExtensionInstallationRepository, Depends(dep_installation_repo)],
        cap_uc: Annotated[GetExtensionCapabilitiesUseCase, Depends(dep_capabilities)],
    ) -> ExtensionHeartbeatResponse:
        """Registra actividad periódica del navegador para mantener viva la instalación."""
        now = utc_now_naive()
        updated = await repo.update_heartbeat(body.installation_id, now)
        cap = cap_uc.execute()
        return ExtensionHeartbeatResponse(acknowledged=updated, capabilities=cap)

    @router.post(
        "/attachments/check",
        summary="Comprobar existencia e indexación de anexos en Mercado Público",
        response_model=ExtensionAttachmentCheckResponse,
    )
    async def check_attachments(
        body: ExtensionAttachmentCheckRequest,
        use_case: Annotated[CheckExtensionAttachmentsUseCase, Depends(dep_check)],
    ) -> ExtensionAttachmentCheckResponse:
        """Cruza los IDs y nombres de documentos de una ficha MP con los ya guardados en el sistema."""
        return await use_case.execute(body)

    @router.post(
        "/jobs/lease",
        summary="Arrendar tarea de extracción comunitaria",
        response_model=ExtensionJobLeaseResponse,
        responses={204: {"description": "No hay tareas pendientes disponibles"}},
    )
    async def lease_job(
        body: ExtensionJobLeaseRequest,
        use_case: Annotated[LeaseFetchJobsUseCase, Depends(dep_lease)],
    ) -> ExtensionJobLeaseResponse | Response:
        """Entrega una licitación pendiente con arrendamiento temporal mediante SKIP LOCKED."""
        try:
            job = await use_case.execute(body.installation_id)
            if not job:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            return job
        except ExtensionInstallationNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=e.message
            ) from e
        except DailyFetchQuotaExceeded as e:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=e.message
            ) from e

    @router.post(
        "/jobs/{job_id}/result",
        summary="Reportar resultado de ejecución de una tarea",
        response_model=ExtensionJobResultResponse,
    )
    async def report_job_result(
        job_id: UUID,
        body: ExtensionJobResultRequest,
        use_case: Annotated[ReportJobResultUseCase, Depends(dep_report)],
    ) -> ExtensionJobResultResponse:
        """Marca la tarea como completada o fallida para actualizar la cola."""
        try:
            return await use_case.execute(job_id, body)
        except ExtensionJobNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=e.message
            ) from e

    return router
