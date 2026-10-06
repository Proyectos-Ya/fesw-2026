"""Compartir una licitación con un enlace web temporal (HdU 19)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_share_link_repository import (
    ITenderShareLinkRepository,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.supplier_member import WorkspaceContext
from app.domain.entities.tender import Tender
from app.domain.entities.tender_share_link import (
    ShareLinkStatus,
    TenderShareLink,
    hash_share_token,
)
from app.domain.errors.sharing_errors import (
    ShareLinkExpired,
    ShareLinkForbidden,
    ShareLinkNotFound,
    ShareLinkRevoked,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.datetime_utils import utc_now_naive

# Compartir muestra lo mismo que la ficha, así que exige lo mismo que verla.
_PERMISO_COMPARTIR = "view_matches"


@dataclass(frozen=True)
class CreatedShareLink:
    link: TenderShareLink
    # La URL con el token solo existe acá: en la base queda su hash.
    url: str


@dataclass(frozen=True)
class SharedTender:
    tender: Tender
    supplier_name: str | None
    score_pct: int | None
    analysis: DeepAnalysis | None
    expires_at: datetime


class CreateShareLinkUseCase:
    def __init__(
        self,
        links: ITenderShareLinkRepository,
        tenders: ITenderRepository,
        base_url: str,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.links = links
        self.tenders = tenders
        self.base_url = base_url.rstrip("/")
        self.now = now

    async def execute(self, ctx: WorkspaceContext, tender_id: UUID) -> CreatedShareLink:
        if _PERMISO_COMPARTIR not in ctx.permissions:
            raise ShareLinkForbidden()
        if not await self.tenders.get_tenders(TenderFilters(ids=[tender_id])):
            raise TenderNotFound(tender_id)

        link, token = TenderShareLink.emitir(
            tender_id=tender_id,
            supplier_id=ctx.active_supplier_id,
            created_by=ctx.user_id,
            now=self.now(),
        )
        guardado = await self.links.save(link)
        return CreatedShareLink(link=guardado, url=f"{self.base_url}/compartido/{token}")


class ListShareLinksUseCase:
    def __init__(
        self,
        links: ITenderShareLinkRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.links = links
        self.now = now

    async def execute(self, ctx: WorkspaceContext, tender_id: UUID) -> list[TenderShareLink]:
        return await self.links.list_active(tender_id, ctx.active_supplier_id, self.now())


class RevokeShareLinkUseCase:
    def __init__(
        self,
        links: ITenderShareLinkRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.links = links
        self.now = now

    async def execute(self, ctx: WorkspaceContext, tender_id: UUID, link_id: UUID) -> None:
        link = await self.links.get(link_id)
        # Todas las negativas son la misma: a quien no puede revocarlo no le
        # corresponde enterarse de que el enlace existe.
        if (
            link is None
            or link.tender_id != tender_id
            or link.supplier_id != ctx.active_supplier_id
            or (link.created_by != ctx.user_id and not ctx.is_admin)
        ):
            raise ShareLinkNotFound()
        await self.links.save(link.revocar(self.now()))


class GetSharedTenderUseCase:
    """Lo que ve quien abre el enlace, sin sesión (criterio 2).

    Lee el puntaje y el análisis tal como están ahora, y nunca los genera: una
    inferencia pedida desde un enlace público la pagaría alguien que no la pidió.
    """

    def __init__(
        self,
        links: ITenderShareLinkRepository,
        tenders: ITenderRepository,
        suppliers: ISupplierRepository,
        matching_results: IMatchingResultRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.links = links
        self.tenders = tenders
        self.suppliers = suppliers
        self.matching_results = matching_results
        self.now = now

    async def execute(self, token: str) -> SharedTender:
        link = await self.links.get_by_token_hash(hash_share_token(token))
        if link is None:
            raise ShareLinkNotFound()

        estado = link.estado(self.now())
        if estado is ShareLinkStatus.REVOCADO:
            raise ShareLinkRevoked()
        if estado is ShareLinkStatus.CADUCADO:
            raise ShareLinkExpired()

        encontradas = await self.tenders.get_tenders(TenderFilters(ids=[link.tender_id]))
        if not encontradas:
            raise ShareLinkNotFound()

        match = await self.matching_results.get_by_proveedor_and_licitacion(
            link.supplier_id, link.tender_id
        )
        score = match.final_score if match is not None else None
        empresa = await self.suppliers.get_by_id(link.supplier_id)

        return SharedTender(
            tender=encontradas[0],
            supplier_name=(empresa.trade_name or empresa.legal_name) if empresa else None,
            score_pct=round(score * 100) if score is not None else None,
            analysis=await self.tenders.get_deep_analysis(link.tender_id, link.supplier_id),
            expires_at=link.expires_at,
        )
