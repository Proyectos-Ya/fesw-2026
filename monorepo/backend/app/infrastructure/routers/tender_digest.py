"""Router para consultar el resumen consolidado de anexos (plan 233, decisión 4)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.schemas.tender_digest_schema import TenderDigestResponse
from app.application.use_cases.attachment_processing.get_tender_digest import (
    GetTenderDigestUseCase,
)
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.errors.tender_errors import TenderNotFound


def create_tender_digest_router(
    get_current_user: Callable,
    get_tender_digest_use_case: Callable,
    *,
    get_optional_workspace_context: Callable,
) -> APIRouter:
    router = APIRouter(
        prefix="/tenders",
        tags=["Tender attachments"],
        dependencies=[Depends(get_current_user)],
    )

    @router.get(
        "/{tender_id}/digest",
        summary="Ver el resumen de los anexos de una licitación",
        response_model=TenderDigestResponse,
        responses={404: {"description": "La licitación no existe"}},
    )
    async def get_tender_digest(
        tender_id: UUID,
        workspace: Annotated[
            WorkspaceContext | None, Depends(get_optional_workspace_context)
        ],
        use_case: Annotated[
            GetTenderDigestUseCase, Depends(get_tender_digest_use_case)
        ],
    ) -> TenderDigestResponse:
        """Resumen generado con IA a partir de los anexos que la empresa activa puede ver.

        Sin anexos privados propios, es el resumen compartido: solo usa archivos compartidos.
        Con privados, suma los de la empresa y nunca los de otra. Cada punto trae sus citas y
        si se pudieron verificar contra el texto del documento. `discrepancias` compara los
        anexos entre sí y contra Mercado Público (presupuesto, publicación y cierres del 1.er y
        2.º llamado; `closing_at` cuando falta la columna del llamado). Si el resumen guardado
        quedó desactualizado se rearma acá, sin llamar a Gemini.
        """
        try:
            vista = await use_case.execute(
                tender_id,
                workspace_id=workspace.active_supplier_id if workspace else None,
            )
        except TenderNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
            ) from error
        return TenderDigestResponse.desde_vista(vista)

    return router
