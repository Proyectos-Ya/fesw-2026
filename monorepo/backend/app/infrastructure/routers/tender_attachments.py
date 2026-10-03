from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.schemas.tender_attachment_schema import (
    OfficialAttachmentResponse,
    TenderAttachmentsResponse,
)
from app.application.use_cases.tender_attachments.get_tender_attachments import (
    GetTenderAttachmentsUseCase,
    TenderAttachmentsResult,
)
from app.domain.errors.tender_errors import TenderNotFound


def _respuesta(resultado: TenderAttachmentsResult) -> TenderAttachmentsResponse:
    return TenderAttachmentsResponse(
        official=[
            OfficialAttachmentResponse(
                id=vista.attachment.id,
                mp_document_id=vista.attachment.mp_document_id,
                name=vista.attachment.name,
                ext=vista.attachment.ext,
                status=vista.status,
            )
            for vista in resultado.official
        ],
        list_synced_at=resultado.list_synced_at,
    )


def create_tender_attachments_router(
    get_current_user: Callable, get_tender_attachments_use_case: Callable
) -> APIRouter:
    """Fábrica del router de anexos. Todas sus rutas requieren sesión."""
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
        use_case: Annotated[
            GetTenderAttachmentsUseCase, Depends(get_tender_attachments_use_case)
        ],
    ) -> TenderAttachmentsResponse:
        """Los documentos que Mercado Público publica para la licitación.

        La lista sale del listado de Mercado Público, que refrescan la ingesta y
        el cron `sync_estados`; no se pide a la API en cada consulta. No incluye
        los anexos que Mercado Público retiró.

        `status` es `missing` mientras no exista la subida de archivos: Chiripa
        conoce la lista, no los archivos. `list_synced_at` nulo significa que la
        lista todavía no se sincroniza, que no es lo mismo que "sin anexos".
        """
        try:
            resultado = await use_case.execute(tender_id)
        except TenderNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
            ) from error
        return _respuesta(resultado)

    return router
