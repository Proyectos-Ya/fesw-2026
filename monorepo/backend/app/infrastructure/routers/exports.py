"""Exportar el detalle de una licitación a PDF o Excel (HdU 19)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.application.use_cases.exports.export_jobs import (
    DownloadExportFileUseCase,
    GetExportJobUseCase,
)
from app.application.use_cases.exports.export_snapshot import ExportSection
from app.application.use_cases.exports.export_tender import (
    ExportFile,
    ExportTenderUseCase,
)
from app.domain.entities.export_job import ExportFormat, ExportJobStatus
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.user import User
from app.domain.errors.export_errors import (
    ExportFileUnavailable,
    ExportForbidden,
    ExportGenerationFailed,
    ExportJobNotFound,
    ExportSectionsRequired,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.datetime_utils import UtcDateTime


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: ExportFormat
    # Solo aplica al Excel (criterio 5). Si no se indica, van todas.
    sections: list[ExportSection] = Field(default_factory=lambda: list(ExportSection))


class ExportQueuedResponse(BaseModel):
    job_id: UUID
    status: ExportJobStatus
    message: str


class ExportJobResponse(BaseModel):
    id: UUID
    status: ExportJobStatus
    format: ExportFormat
    file_name: str
    created_at: UtcDateTime
    finished_at: UtcDateTime | None
    expires_at: UtcDateTime


_AVISO_SEGUNDO_PLANO = (
    "Tu archivo se está generando en segundo plano. "
    "Te avisaremos por correo cuando esté listo para descargar."
)

_NO_DISPONIBLE = {
    "processing": (409, "export_processing"),
    "failed": (410, "export_failed"),
    "expired": (410, "export_expired"),
}


def _archivo(archivo: ExportFile) -> Response:
    return Response(
        content=archivo.content,
        media_type=archivo.media_type,
        headers={
            # El nombre ya viene saneado: solo letras, números, "-", "_" y ".".
            "Content-Disposition": f'attachment; filename="{archivo.file_name}"',
            "Cache-Control": "no-store",
        },
    )


def create_exports_router(
    get_workspace_context: Callable,
    get_current_user: Callable,
    get_export_tender_use_case: Callable,
    get_export_job_use_case: Callable,
    get_download_export_file_use_case: Callable,
) -> APIRouter:
    router = APIRouter(tags=["Exports"])

    @router.post(
        "/tenders/{tender_id}/exports",
        responses={
            200: {"content": {"application/pdf": {}, ExportFormat.XLSX.media_type: {}}},
            202: {"model": ExportQueuedResponse},
        },
    )
    async def export_tender(
        tender_id: UUID,
        body: ExportRequest,
        ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[ExportTenderUseCase, Depends(get_export_tender_use_case)],
    ):
        try:
            resultado = await use_case.execute(
                ctx, user.email, tender_id, body.format, body.sections
            )
        except ExportSectionsRequired as error:
            raise HTTPException(422, str(error)) from error
        except ExportForbidden as error:
            raise HTTPException(403, str(error)) from error
        except TenderNotFound as error:
            raise HTTPException(404, "La licitación no existe.") from error
        except ExportGenerationFailed as error:
            raise HTTPException(500, str(error)) from error

        if isinstance(resultado, ExportFile):
            return _archivo(resultado)
        # Criterios 8 y 9: tardó más de lo que se espera en la misma respuesta.
        return JSONResponse(
            status_code=202,
            content=ExportQueuedResponse(
                job_id=resultado.job.id,
                status=resultado.job.status,
                message=_AVISO_SEGUNDO_PLANO,
            ).model_dump(mode="json"),
        )

    @router.get("/exports/{job_id}", response_model=ExportJobResponse)
    async def get_export_job(
        job_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[GetExportJobUseCase, Depends(get_export_job_use_case)],
    ):
        try:
            job = await use_case.execute(user.id, job_id)
        except ExportJobNotFound as error:
            raise HTTPException(404, str(error)) from error
        return ExportJobResponse(
            id=job.id,
            status=job.status,
            format=job.format,
            file_name=job.file_name,
            created_at=job.created_at,
            finished_at=job.finished_at,
            expires_at=job.expires_at,
        )

    @router.get("/exports/{job_id}/file")
    async def download_export_file(
        job_id: UUID,
        user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[DownloadExportFileUseCase, Depends(get_download_export_file_use_case)],
    ):
        try:
            return _archivo(await use_case.execute(user.id, job_id))
        except ExportJobNotFound as error:
            raise HTTPException(404, str(error)) from error
        except ExportFileUnavailable as error:
            status, code = _NO_DISPONIBLE[error.reason]
            return JSONResponse(status_code=status, content={"detail": str(error), "code": code})

    return router
