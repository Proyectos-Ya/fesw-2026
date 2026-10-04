from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.application.schemas.tender_attachment_schema import (
    AttachmentErrorResponse,
    AttachmentFileResponse,
    AttachmentUploadDeduplicatedResponse,
    AttachmentUploadTicketResponse,
    AttachmentUploadUrlRequest,
    OfficialAttachmentResponse,
    TenderAttachmentsResponse,
    UploadQuotaResponse,
)
from app.application.services.attachment_storage import AttachmentStorageError
from app.application.use_cases.tender_attachments.complete_attachment_upload import (
    CompleteAttachmentUploadUseCase,
)
from app.application.use_cases.tender_attachments.delete_attachment_file import (
    DeleteAttachmentFileUseCase,
)
from app.application.use_cases.tender_attachments.get_tender_attachments import (
    GetTenderAttachmentsUseCase,
    TenderAttachmentsResult,
    WorkspaceAccess,
)
from app.application.use_cases.tender_attachments.request_attachment_upload import (
    RequestAttachmentUploadUseCase,
    UploadDeduplicated,
    UploadRequest,
)
from app.domain.entities.attachment_file import AttachmentFile
from app.domain.entities.supplier_member import UPLOAD_ATTACHMENTS, WorkspaceContext
from app.domain.errors.attachment_errors import (
    AttachmentAlreadyUploaded,
    AttachmentExtensionMismatch,
    AttachmentFileIsShared,
    AttachmentFileNotFound,
    AttachmentNameMismatch,
    AttachmentNotFound,
    AttachmentStorageUnavailable,
    AttachmentTooLarge,
    AttachmentUploadError,
    ConcurrentUploadConflict,
    NotAttachmentFileOwner,
    UploadedObjectMissing,
    UploadNotFound,
    UploadNotInProgress,
    UploadQuotaExceeded,
    UploadVerificationFailed,
)
from app.domain.errors.tender_errors import TenderNotFound

# Código HTTP de cada error de la subida. El `code` y el mensaje salen del propio error.
_ESTADO_HTTP: dict[type[AttachmentUploadError], int] = {
    AttachmentNotFound: status.HTTP_404_NOT_FOUND,
    AttachmentTooLarge: 413,
    AttachmentExtensionMismatch: 422,
    AttachmentNameMismatch: 422,
    AttachmentAlreadyUploaded: status.HTTP_409_CONFLICT,
    ConcurrentUploadConflict: status.HTTP_409_CONFLICT,
    UploadQuotaExceeded: status.HTTP_403_FORBIDDEN,
    AttachmentStorageUnavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
    UploadNotFound: status.HTTP_404_NOT_FOUND,
    UploadNotInProgress: status.HTTP_409_CONFLICT,
    UploadedObjectMissing: status.HTTP_409_CONFLICT,
    UploadVerificationFailed: 422,
    AttachmentFileNotFound: status.HTTP_404_NOT_FOUND,
    NotAttachmentFileOwner: status.HTTP_403_FORBIDDEN,
    AttachmentFileIsShared: status.HTTP_409_CONFLICT,
}


def _error(error: AttachmentUploadError) -> JSONResponse:
    """`{"detail", "code", ...extra}` con un código estable. Los extras nulos se omiten.

    Ningún mensaje de 403 contiene "revocado": el cliente lo trata como cierre de sesión.
    """
    cuerpo = AttachmentErrorResponse(
        detail=error.message, code=error.code, **error.extra  # type: ignore[arg-type]
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=_ESTADO_HTTP.get(type(error), status.HTTP_400_BAD_REQUEST),
        content=cuerpo,
    )


def _error_de_almacenamiento() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=AttachmentErrorResponse(
            detail=(
                "No pudimos comunicarnos con el almacenamiento de archivos. "
                "Inténtalo nuevamente."
            ),
            code="storage_error",
        ).model_dump(exclude_none=True),
    )


def _sin_permiso(workspace: WorkspaceContext) -> JSONResponse | None:
    if UPLOAD_ATTACHMENTS in workspace.permissions:
        return None
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=AttachmentErrorResponse(
            detail="Tu rol en esta empresa no permite subir ni borrar anexos.",
            code="permission_denied",
        ).model_dump(exclude_none=True),
    )


def _archivo(archivo: AttachmentFile, workspace_id: UUID | None) -> AttachmentFileResponse:
    return AttachmentFileResponse(
        id=archivo.id,
        size_bytes=archivo.size_bytes,
        source=archivo.source,
        visibility=archivo.visibility,
        trust=archivo.trust,
        status=archivo.status,
        is_mine=archivo.workspace_id == workspace_id,
        created_at=archivo.created_at,
    )


def _respuesta(resultado: TenderAttachmentsResult) -> TenderAttachmentsResponse:
    return TenderAttachmentsResponse(
        official=[
            OfficialAttachmentResponse(
                id=vista.attachment.id,
                mp_document_id=vista.attachment.mp_document_id,
                name=vista.attachment.name,
                name_normalized=vista.attachment.name_normalized,
                ext=vista.attachment.ext,
                status=vista.status,
                file=(
                    AttachmentFileResponse(
                        id=vista.file.file.id,
                        size_bytes=vista.file.file.size_bytes,
                        source=vista.file.file.source,
                        visibility=vista.file.file.visibility,
                        trust=vista.file.file.trust,
                        status=vista.file.file.status,
                        is_mine=vista.file.is_mine,
                        created_at=vista.file.file.created_at,
                    )
                    if vista.file is not None
                    else None
                ),
            )
            for vista in resultado.official
        ],
        list_synced_at=resultado.list_synced_at,
        quota=(
            UploadQuotaResponse(used=resultado.quota.used, limit=resultado.quota.limit)
            if resultado.quota is not None
            else None
        ),
        can_upload=resultado.can_upload,
        max_upload_size_bytes=resultado.max_upload_size_bytes,
    )


def _sin_empresa() -> None:
    """Dependencia por defecto cuando el router no recibe la de la empresa activa."""
    return None


def create_tender_attachments_router(
    get_current_user: Callable,
    get_tender_attachments_use_case: Callable,
    *,
    get_optional_workspace_context: Callable | None = None,
    get_current_workspace_context: Callable | None = None,
    get_request_upload_use_case: Callable | None = None,
    get_complete_upload_use_case: Callable | None = None,
    get_delete_file_use_case: Callable | None = None,
) -> APIRouter:
    """Fábrica del router de anexos. Todas sus rutas requieren sesión.

    Las rutas de escritura (subir, confirmar, borrar) solo se registran si llegan
    la dependencia de la empresa activa y los tres casos de uso.
    """
    router = APIRouter(
        prefix="/tenders",
        tags=["Tender attachments"],
        dependencies=[Depends(get_current_user)],
    )

    @router.get(
        "/{tender_id}/attachments",
        summary="Listar los anexos oficiales de una licitación",
        response_model=TenderAttachmentsResponse,
        responses={404: {"description": "La licitación no existe"}},
    )
    async def list_tender_attachments(
        tender_id: UUID,
        workspace: Annotated[
            WorkspaceContext | None,
            Depends(get_optional_workspace_context or _sin_empresa),
        ],
        use_case: Annotated[
            GetTenderAttachmentsUseCase, Depends(get_tender_attachments_use_case)
        ],
    ) -> TenderAttachmentsResponse:
        """Los documentos que Mercado Público publica para la licitación.

        La lista sale del listado de Mercado Público, que refrescan la ingesta y
        el cron `sync_estados`; no se pide a la API en cada consulta. No incluye
        los anexos que Mercado Público retiró. `list_synced_at` nulo significa que
        la lista todavía no se sincroniza, que no es lo mismo que "sin anexos".

        `status` es el del archivo que la empresa activa ve para ese anexo:
        `missing` si no hay ninguno, y `uploading`, `stored`, `rejected` o
        `unsupported` según el archivo. `file` es ese archivo (el propio o uno
        compartido; nunca el privado de otra empresa). `quota` y `can_upload` se
        calculan para la empresa activa: puede subir si su rol tiene el permiso
        `upload_attachments` y hay almacenamiento configurado.
        """
        access = (
            WorkspaceAccess(
                workspace_id=workspace.active_supplier_id,
                can_upload=UPLOAD_ATTACHMENTS in workspace.permissions,
            )
            if workspace is not None
            else None
        )
        try:
            resultado = await use_case.execute(tender_id, access=access)
        except TenderNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
            ) from error
        return _respuesta(resultado)

    if not (
        get_current_workspace_context
        and get_request_upload_use_case
        and get_complete_upload_use_case
        and get_delete_file_use_case
    ):
        return router

    @router.post(
        "/{tender_id}/attachments/{attachment_id}/upload-url",
        summary="Pedir una URL para subir un anexo",
        status_code=status.HTTP_201_CREATED,
        response_model=AttachmentUploadTicketResponse | AttachmentUploadDeduplicatedResponse,
        responses={
            200: {
                "model": AttachmentUploadDeduplicatedResponse,
                "description": "Ya existe ese archivo: no hay nada que subir",
            },
            403: {
                "model": AttachmentErrorResponse,
                "description": "`permission_denied` o `quota_exceeded`",
            },
            404: {"model": AttachmentErrorResponse, "description": "`attachment_not_found`"},
            409: {
                "model": AttachmentErrorResponse,
                "description": "`attachment_already_uploaded` o `upload_in_progress`",
            },
            413: {"model": AttachmentErrorResponse, "description": "`file_too_large`"},
            422: {
                "model": AttachmentErrorResponse,
                "description": (
                    "`attachment_extension_mismatch` o `attachment_name_mismatch`, o el "
                    "cuerpo es inválido"
                ),
            },
            502: {"model": AttachmentErrorResponse, "description": "`storage_error`"},
            503: {"model": AttachmentErrorResponse, "description": "`storage_unavailable`"},
        },
    )
    async def request_upload_url(
        tender_id: UUID,
        attachment_id: UUID,
        body: AttachmentUploadUrlRequest,
        response: Response,
        workspace: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
        use_case: Annotated[
            RequestAttachmentUploadUseCase, Depends(get_request_upload_use_case)
        ],
    ):
        """Primer paso de la subida de un anexo oficial.

        Flujo de tres pasos: (1) esta llamada declara el archivo (nombre, tamaño y
        SHA-256 en hex) y devuelve una URL firmada; (2) el navegador hace `PUT`
        del archivo directo a esa URL, con exactamente los `headers` devueltos y
        sin credenciales; (3) `POST .../uploads/{upload_id}/complete` verifica que
        llegó. `upload_id` es el id del archivo y sirve también para borrarlo.

        El archivo tiene que llamarse como el anexo oficial: se tolera el
        " (1)" que agrega el navegador, las mayúsculas y las tildes. Responde 200
        con `deduplicated: true` si la empresa ya tiene ese archivo para el anexo
        (no hay nada que subir). El cupo mensual solo se gasta al crear una
        subida nueva: reintentar o repetir un archivo no vuelve a cobrar.
        """
        if (denegado := _sin_permiso(workspace)) is not None:
            return denegado
        try:
            resultado = await use_case.execute(
                UploadRequest(
                    tender_id=tender_id,
                    attachment_id=attachment_id,
                    workspace_id=workspace.active_supplier_id,
                    user_id=workspace.user_id,
                    file_name=body.file_name,
                    size_bytes=body.size_bytes,
                    mime=body.mime,
                    sha256=body.sha256,
                )
            )
        except AttachmentUploadError as error:
            return _error(error)
        except AttachmentStorageError:
            return _error_de_almacenamiento()
        if isinstance(resultado, UploadDeduplicated):
            response.status_code = status.HTTP_200_OK
            return AttachmentUploadDeduplicatedResponse(
                file=_archivo(resultado.file, workspace.active_supplier_id)
            )
        return AttachmentUploadTicketResponse(
            upload_id=resultado.upload_id,
            url=resultado.url,
            headers=resultado.headers,
            expires_at=resultado.expires_at,
        )

    @router.post(
        "/{tender_id}/attachments/uploads/{upload_id}/complete",
        summary="Confirmar la subida de un anexo",
        response_model=AttachmentFileResponse,
        responses={
            403: {"model": AttachmentErrorResponse, "description": "`permission_denied`"},
            404: {"model": AttachmentErrorResponse, "description": "`upload_not_found`"},
            409: {
                "model": AttachmentErrorResponse,
                "description": "`upload_not_in_progress` u `object_missing`",
            },
            422: {
                "model": AttachmentErrorResponse,
                "description": "`upload_verification_failed`: el archivo quedó rechazado",
            },
            502: {"model": AttachmentErrorResponse, "description": "`storage_error`"},
            503: {"model": AttachmentErrorResponse, "description": "`storage_unavailable`"},
        },
    )
    async def complete_upload(
        tender_id: UUID,
        upload_id: UUID,
        workspace: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
        use_case: Annotated[
            CompleteAttachmentUploadUseCase, Depends(get_complete_upload_use_case)
        ],
    ):
        """Tercer paso de la subida: verifica que el archivo llegó completo.

        Consulta al almacenamiento (un HEAD) y compara el tamaño siempre, y la
        huella SHA-256 cuando el almacenamiento la informa. Si no coinciden,
        borra el objeto, deja el archivo `rejected` y responde 422. Es
        idempotente: confirmar una subida ya guardada devuelve el archivo. No
        extrae texto del documento (decisión 4).
        """
        if (denegado := _sin_permiso(workspace)) is not None:
            return denegado
        try:
            archivo = await use_case.execute(
                tender_id=tender_id,
                upload_id=upload_id,
                workspace_id=workspace.active_supplier_id,
            )
        except AttachmentUploadError as error:
            return _error(error)
        except AttachmentStorageError:
            return _error_de_almacenamiento()
        return _archivo(archivo, workspace.active_supplier_id)

    @router.delete(
        "/{tender_id}/attachments/files/{file_id}",
        summary="Borrar un archivo de anexo de la empresa",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        response_model=None,
        responses={
            403: {
                "model": AttachmentErrorResponse,
                "description": "`permission_denied` o `not_owner`",
            },
            404: {"model": AttachmentErrorResponse, "description": "`file_not_found`"},
            409: {"model": AttachmentErrorResponse, "description": "`file_is_shared`"},
            502: {"model": AttachmentErrorResponse, "description": "`storage_error`"},
            503: {"model": AttachmentErrorResponse, "description": "`storage_unavailable`"},
        },
    )
    async def delete_file(
        tender_id: UUID,
        file_id: UUID,
        workspace: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
        use_case: Annotated[
            DeleteAttachmentFileUseCase, Depends(get_delete_file_use_case)
        ],
    ):
        """Borra un archivo que subió la empresa activa.

        Borra la fila y, si ninguna otra fila usa el mismo objeto, el objeto del
        almacenamiento. El cupo del mes no se devuelve. Un archivo ya compartido
        con otras empresas no se puede borrar (409).
        """
        if (denegado := _sin_permiso(workspace)) is not None:
            return denegado
        try:
            await use_case.execute(
                tender_id=tender_id,
                file_id=file_id,
                workspace_id=workspace.active_supplier_id,
            )
        except AttachmentUploadError as error:
            return _error(error)
        except AttachmentStorageError:
            return _error_de_almacenamiento()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
