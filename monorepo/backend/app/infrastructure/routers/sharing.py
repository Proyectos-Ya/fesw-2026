"""Enlaces para compartir una licitación sin cuenta (HdU 19).

Son dos routers: el de quien comparte, que exige sesión y empresa activa, y el
público, que abre el enlace. Van separados porque el router de `/tenders` exige
sesión para todas sus rutas.
"""

from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.application.use_cases.sharing.tender_sharing import (
    CreateShareLinkUseCase,
    GetSharedTenderUseCase,
    ListShareLinksUseCase,
    RevokeShareLinkUseCase,
    SharedTender,
)
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.tender_share_link import TenderShareLink
from app.domain.errors.sharing_errors import (
    ShareLinkExpired,
    ShareLinkForbidden,
    ShareLinkNotFound,
    ShareLinkRevoked,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.datetime_utils import UtcDateTime


class ShareLinkResponse(BaseModel):
    id: UUID
    created_at: UtcDateTime
    expires_at: UtcDateTime


class CreatedShareLinkResponse(ShareLinkResponse):
    # Solo en la respuesta de creación: después ya no se puede reconstruir.
    url: str


def _enlace(link: TenderShareLink) -> ShareLinkResponse:
    return ShareLinkResponse(id=link.id, created_at=link.created_at, expires_at=link.expires_at)


class SharedItemResponse(BaseModel):
    name: str
    description: str | None
    quantity: float
    unit_of_measure: str


class SharedAnalysisResponse(BaseModel):
    compatibility_score: float
    recommendation: str
    justification: str
    updated_at: UtcDateTime


class SharedTenderResponse(BaseModel):
    """Lo que ve un tercero. Sin ids de la empresa ni de quien compartió."""

    code: str
    name: str
    description: str | None
    status_code: str | None
    is_closed: bool
    published_at: UtcDateTime
    closing_at: UtcDateTime
    buyer_name: str | None
    buyer_unit: str
    region: str | None
    commune: str | None
    available_amount_clp: float | None
    items: list[SharedItemResponse]
    supplier_name: str | None
    score_pct: int | None
    analysis: SharedAnalysisResponse | None
    expires_at: UtcDateTime


def _compartido(data: SharedTender) -> SharedTenderResponse:
    t = data.tender
    a = data.analysis
    return SharedTenderResponse(
        code=t.code,
        name=t.name,
        description=t.description,
        status_code=t.status_code,
        is_closed=t.esta_cerrada(),
        published_at=t.published_at,
        closing_at=t.closing_at,
        buyer_name=t.buyer_name,
        buyer_unit=t.buyer_unit,
        region=t.region,
        commune=t.commune,
        available_amount_clp=t.available_amount_clp,
        items=[
            SharedItemResponse(
                name=i.name,
                description=i.description,
                quantity=i.quantity,
                unit_of_measure=i.unit_of_measure,
            )
            for i in t.items
        ],
        supplier_name=data.supplier_name,
        score_pct=data.score_pct,
        analysis=(
            SharedAnalysisResponse(
                compatibility_score=a.compatibility_score,
                recommendation=a.recommendation,
                justification=a.justification,
                updated_at=a.updated_at,
            )
            if a is not None
            else None
        ),
        expires_at=data.expires_at,
    )


def create_sharing_router(
    get_workspace_context: Callable,
    get_create_share_link_use_case: Callable,
    get_list_share_links_use_case: Callable,
    get_revoke_share_link_use_case: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/tenders", tags=["Sharing"])

    @router.post(
        "/{tender_id}/share-links", response_model=CreatedShareLinkResponse, status_code=201
    )
    async def create_share_link(
        tender_id: UUID,
        ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
        use_case: Annotated[CreateShareLinkUseCase, Depends(get_create_share_link_use_case)],
    ):
        try:
            creado = await use_case.execute(ctx, tender_id)
        except ShareLinkForbidden as error:
            raise HTTPException(403, str(error)) from error
        except TenderNotFound as error:
            raise HTTPException(404, "La licitación no existe.") from error
        return CreatedShareLinkResponse(**_enlace(creado.link).model_dump(), url=creado.url)

    @router.get("/{tender_id}/share-links", response_model=list[ShareLinkResponse])
    async def list_share_links(
        tender_id: UUID,
        ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
        use_case: Annotated[ListShareLinksUseCase, Depends(get_list_share_links_use_case)],
    ):
        return [_enlace(link) for link in await use_case.execute(ctx, tender_id)]

    @router.delete("/{tender_id}/share-links/{link_id}", status_code=204)
    async def revoke_share_link(
        tender_id: UUID,
        link_id: UUID,
        ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
        use_case: Annotated[RevokeShareLinkUseCase, Depends(get_revoke_share_link_use_case)],
    ):
        try:
            await use_case.execute(ctx, tender_id, link_id)
        except ShareLinkNotFound as error:
            raise HTTPException(404, str(error)) from error
        return Response(status_code=204)

    return router


# Cabeceras de la vista pública: que no quede en cachés compartidos ni en
# buscadores, porque la URL es la única llave.
_CABECERAS_PUBLICAS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}

ShareLinkCode = Literal["share_link_expired", "share_link_revoked"]


def _gone(message: str, code: ShareLinkCode) -> JSONResponse:
    # `code` deja que el frontend distinga caducado de revocado sin leer el texto.
    return JSONResponse(
        status_code=410, content={"detail": message, "code": code}, headers=_CABECERAS_PUBLICAS
    )


def create_public_sharing_router(get_shared_tender_use_case: Callable) -> APIRouter:
    router = APIRouter(prefix="/shared", tags=["Sharing"])

    @router.get("/{token}", response_model=SharedTenderResponse)
    async def open_shared_tender(
        token: str,
        response: Response,
        use_case: Annotated[GetSharedTenderUseCase, Depends(get_shared_tender_use_case)],
    ):
        response.headers.update(_CABECERAS_PUBLICAS)
        try:
            data = await use_case.execute(token)
        except ShareLinkExpired as error:
            return _gone(str(error), "share_link_expired")
        except ShareLinkRevoked as error:
            return _gone(str(error), "share_link_revoked")
        except ShareLinkNotFound as error:
            raise HTTPException(404, str(error), headers=_CABECERAS_PUBLICAS) from error
        return _compartido(data)

    return router
