import logging
from uuid import UUID

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.attachment_extraction import EXTRACTION_PROMPT_VERSION
from app.domain.entities.matching_result import MatchingResult
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForScoring, TenderNotFound
from app.domain.services.digest_consolidation import consolidar

logger = logging.getLogger(__name__)


class ScoreTenderOnDemandUseCase:
    """Calcula la compatibilidad de una licitación que el usuario eligió.

    El ranking solo puntúa su top-N, así que todo lo que llega del buscador, de
    las guardadas o de un enlace queda sin porcentaje. Este caso de uso cubre
    ese hueco, pero nunca por su cuenta: se ejecuta cuando alguien lo pide, y
    deja el resultado guardado para que la siguiente visita no vuelva a pagar la
    inferencia ni vea un número distinto.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        matching_result_repo: IMatchingResultRepository,
        scorer: CompatibilityScorer,
        digest_repo: ITenderDigestRepository | None = None,
        extraction_repo: IAttachmentExtractionRepository | None = None,
    ) -> None:
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.matching_result_repo = matching_result_repo
        self.scorer = scorer
        self.digest_repo = digest_repo
        self.extraction_repo = extraction_repo

    async def execute(
        self,
        user_id: UUID,
        tender_id: UUID,
        supplier_id: UUID | None = None,
        force: bool = False,
    ) -> MatchingResult:
        supplier = await resolver_empresa(self.supplier_repo, user_id, supplier_id)
        if not supplier:
            raise SupplierNotFoundForUser(user_id)

        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        tender = tenders[0]

        if tender.esta_cerrada():
            raise TenderClosedForScoring(tender_id)

        # 1. Obtener digest si existe (privado de la empresa o compartido)
        digest: object | None = None
        if self.digest_repo is not None:
            if supplier.id is not None:
                digest = await self.digest_repo.get_current(tender_id, supplier.id)
            if digest is None:
                digest = await self.digest_repo.get_current(tender_id, None)

        # 2. Si no hay digest persistido, intentar consolidar en vivo si hay extracciones
        if digest is None and self.extraction_repo is not None:
            panel_sources = []
            if supplier.id is not None:
                panel_sources = await self.extraction_repo.list_sources(
                    tender_id=tender_id,
                    workspace_id=supplier.id,
                    prompt_version=EXTRACTION_PROMPT_VERSION,
                )
            if not panel_sources:
                panel_sources = await self.extraction_repo.list_sources(
                    tender_id=tender_id,
                    workspace_id=None,
                    prompt_version=EXTRACTION_PROMPT_VERSION,
                )
            if panel_sources:
                try:
                    digest_data = consolidar(panel_sources, tender)
                    digest = type("LiveTenderDigest", (), {"data": digest_data})()
                except Exception as e:
                    logger.warning("No se pudo consolidar el resumen para el score: %s", e)

        fila = await self.matching_result_repo.get_by_proveedor_and_licitacion(
            proveedor_id=supplier.id, licitacion_id=tender_id
        )

        # Si no se fuerza recálculo, no hay anexos/digest, y ya es una recomendación del ranking:
        if not force and digest is None and fila is not None and fila.source == "ranking":
            return fila

        # Si ya existía un cálculo, preservamos el `source` ("ranking" u "on_demand")
        # para no sacar la licitación de las recomendaciones del ranking al recalcular.
        source = fila.source if fila is not None else "on_demand"

        return await self.scorer.score_and_persist(
            supplier=supplier,
            tender=tender,
            digest=digest,
            source=source,
        )
