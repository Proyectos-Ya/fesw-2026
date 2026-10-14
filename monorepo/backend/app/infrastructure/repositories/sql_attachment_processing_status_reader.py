"""Implementación SQL del lector de estado de procesamiento de anexos (plan 233, decisión 4)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_processing_status_reader import (
    IAttachmentProcessingStatusReader,
)
from app.domain.entities.attachment_processing import EstadoDeExtraccion
from app.infrastructure.repositories.attachment_file_model import (
    AttachmentFileModel as F,
)
from app.infrastructure.repositories.attachment_processing_model import (
    AttachmentExtractionModel as E,
    AttachmentProcessingJobModel as J,
)


class SqlAttachmentProcessingStatusReader(IAttachmentProcessingStatusReader):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def extraction_states(
        self, file_ids: Sequence[UUID], *, prompt_version: str
    ) -> dict[UUID, EstadoDeExtraccion]:
        if not file_ids:
            return {}

        # 1. Extraídas para la versión dada
        stmt_ext = select(E.attachment_file_id).where(
            col(E.attachment_file_id).in_(file_ids),
            E.prompt_version == prompt_version,
        )
        extraidas_ids = set((await self.session.exec(stmt_ext)).all())

        # 2. Jobs de extracción para esos archivos
        stmt_jobs = select(J.attachment_file_id, J.status).where(
            col(J.attachment_file_id).in_(file_ids),
            J.kind == "extract",
        )
        filas_jobs = (await self.session.exec(stmt_jobs)).all()
        activos_por_fid: set[UUID] = set()
        fallidos_por_fid: set[UUID] = set()
        for fid, status in filas_jobs:
            if status in ("pending", "running"):
                activos_por_fid.add(fid)
            elif status == "failed":
                fallidos_por_fid.add(fid)

        res: dict[UUID, EstadoDeExtraccion] = {}
        for fid in file_ids:
            extraida = fid in extraidas_ids
            fallida = (fid in fallidos_por_fid) and (fid not in activos_por_fid)
            res[fid] = EstadoDeExtraccion(extraida=extraida, fallida=fallida)
        return res

    async def pending_count(
        self, *, tender_id: UUID, workspace_id: UUID | None, prompt_version: str
    ) -> int:
        cond_digest_ws = (
            J.workspace_id == workspace_id
            if workspace_id is not None
            else J.workspace_id.is_(None)
        )
        stmt_digest = select(func.count(J.id)).where(
            J.tender_id == tender_id,
            J.kind == "digest",
            cond_digest_ws,
            col(J.status).in_(["pending", "running"]),
        )
        count_digest = (await self.session.exec(stmt_digest)).one()

        compartido = and_(
            F.visibility == "shared",
            col(F.trust).notin_(["conflict", "rejected"]),
        )
        if workspace_id is not None:
            visibilidad = or_(
                compartido,
                and_(
                    F.workspace_id == workspace_id,
                    F.visibility == "private",
                ),
            )
        else:
            visibilidad = compartido

        stmt_extract = (
            select(func.count(J.id))
            .join(F, F.id == J.attachment_file_id)
            .where(
                J.tender_id == tender_id,
                J.kind == "extract",
                col(J.status).in_(["pending", "running"]),
                visibilidad,
            )
        )
        count_extract = (await self.session.exec(stmt_extract)).one()
        return count_digest + count_extract
