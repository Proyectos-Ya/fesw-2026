from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from app.application.schemas.document_processing_schema import (
    DocumentJobAccepted,
    DocumentJobStatus,
    DocumentUploadCreated,
    DocumentUploadRequest,
)
from app.application.services.document_processing_service import (
    DocumentJobNotFound,
    DocumentNotFound,
    DocumentNotUploaded,
    DocumentUploadInvalid,
    IDocumentProcessingService,
)
from app.domain.entities.user import User


def create_document_processing_mock_router(
    get_document_processing_service: Callable,
    get_current_user: Callable,
) -> APIRouter:
    router = APIRouter(tags=["Document processing mock"])

    @router.post(
        "/document-uploads",
        response_model=DocumentUploadCreated,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_upload(
        payload: DocumentUploadRequest,
        current_user: Annotated[User, Depends(get_current_user)],
        service: Annotated[
            IDocumentProcessingService, Depends(get_document_processing_service)
        ],
    ) -> DocumentUploadCreated:
        return await service.create_upload(current_user.id, payload)

    @router.put(
        "/document-uploads/{document_id}/content",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def upload_content(
        document_id: UUID,
        request: Request,
        current_user: Annotated[User, Depends(get_current_user)],
        service: Annotated[
            IDocumentProcessingService, Depends(get_document_processing_service)
        ],
    ) -> Response:
        try:
            await service.store_content(
                current_user.id, document_id, await request.body()
            )
        except DocumentNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DocumentUploadInvalid as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/documents/{document_id}/process",
        response_model=DocumentJobAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def process_document(
        document_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        service: Annotated[
            IDocumentProcessingService, Depends(get_document_processing_service)
        ],
        mock_outcome: Annotated[
            Literal["completed", "failed"], Header(alias="X-Mock-Outcome")
        ] = "completed",
    ) -> DocumentJobAccepted:
        try:
            return await service.start_processing(
                current_user.id, document_id, mock_outcome
            )
        except DocumentNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DocumentNotUploaded as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get(
        "/document-jobs/{job_id}",
        response_model=DocumentJobStatus,
    )
    async def get_job(
        job_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        service: Annotated[
            IDocumentProcessingService, Depends(get_document_processing_service)
        ],
    ) -> DocumentJobStatus:
        try:
            return await service.get_job(current_user.id, job_id)
        except DocumentJobNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
