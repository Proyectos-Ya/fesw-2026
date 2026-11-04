"""Implementación SQL de la cola de procesamiento de anexos (plan 233, decisión 4)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case, exists, func, select, update
from sqlalchemy import delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.domain.entities.attachment_processing import (
    MAX_INTENTOS,
    AttachmentProcessingJob,
    ProcessingJobKind,
    ProcessingJobStatus,
)
from app.infrastructure.repositories.attachment_file_model import (
    AttachmentFileModel,
)
from app.infrastructure.repositories.attachment_processing_model import (
    AttachmentExtractionModel,
    AttachmentProcessingJobModel,
)

J = AttachmentProcessingJobModel
F = AttachmentFileModel
E = AttachmentExtractionModel


def _a_entidad(fila: Any) -> AttachmentProcessingJob:
    return AttachmentProcessingJob(
        id=fila.id,
        kind=ProcessingJobKind(fila.kind),
        status=ProcessingJobStatus(fila.status),
        priority=fila.priority,
        attempts=fila.attempts,
        last_error=fila.last_error,
        not_before=fila.not_before,
        locked_at=fila.locked_at,
        attachment_file_id=fila.attachment_file_id,
        tender_id=fila.tender_id,
        workspace_id=fila.workspace_id,
        created_at=fila.created_at,
        updated_at=fila.updated_at,
    )


class SqlAttachmentProcessingJobRepository(IAttachmentProcessingJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue_extract(
        self,
        *,
        attachment_file_id: UUID,
        tender_id: UUID,
        priority: int,
        now: datetime,
    ) -> bool:
        stmt = (
            pg_insert(J)
            .values(
                id=uuid4(),
                kind="extract",
                status="pending",
                priority=priority,
                attempts=0,
                not_before=now,
                attachment_file_id=attachment_file_id,
                tender_id=tender_id,
                workspace_id=None,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing()
            .returning(J.id)
        )
        filas = (await self.session.exec(stmt)).all()  # type: ignore[call-overload]
        await self.session.commit()
        return bool(filas)

    async def enqueue_digest(
        self,
        *,
        tender_id: UUID,
        workspace_id: UUID | None,
        priority: int,
        now: datetime,
    ) -> bool:
        stmt = (
            pg_insert(J)
            .values(
                id=uuid4(),
                kind="digest",
                status="pending",
                priority=priority,
                attempts=0,
                not_before=now,
                attachment_file_id=None,
                tender_id=tender_id,
                workspace_id=workspace_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing()
            .returning(J.id)
        )
        filas = (await self.session.exec(stmt)).all()  # type: ignore[call-overload]
        await self.session.commit()
        return bool(filas)

    async def claim_next(
        self, *, now: datetime, kinds: Sequence[ProcessingJobKind]
    ) -> AttachmentProcessingJob | None:
        siguiente = (
            select(J.id)
            .where(
                J.status == "pending",
                J.not_before <= now,
                col(J.kind).in_([k.value for k in kinds]),
            )
            .order_by(
                col(J.priority).desc(),
                col(J.not_before).asc(),
                col(J.created_at).asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(J)
            .where(col(J.id) == siguiente)
            .values(
                status="running",
                locked_at=now,
                attempts=J.attempts + 1,
                updated_at=now,
            )
            .returning(*J.__table__.c)
        )
        fila = (await self.session.exec(stmt)).first()  # type: ignore[call-overload]
        await self.session.commit()
        return None if fila is None else _a_entidad(fila)

    async def complete(self, job_id: UUID, *, now: datetime) -> None:
        stmt = (
            update(J)
            .where(col(J.id) == job_id)
            .values(status="done", locked_at=None, updated_at=now)
        )
        await self.session.exec(stmt)
        await self.session.commit()

    async def retry(
        self, job_id: UUID, *, not_before: datetime, error: str, now: datetime
    ) -> None:
        stmt = (
            update(J)
            .where(col(J.id) == job_id)
            .values(
                status="pending",
                not_before=not_before,
                last_error=error[:500],
                locked_at=None,
                updated_at=now,
            )
        )
        try:
            await self.session.exec(stmt)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            stmt_replace = (
                update(J)
                .where(col(J.id) == job_id)
                .values(
                    status="done",
                    last_error="reemplazado por otro pendiente",
                    locked_at=None,
                    updated_at=now,
                )
            )
            await self.session.exec(stmt_replace)
            await self.session.commit()

    async def defer(
        self, job_id: UUID, *, not_before: datetime, reason: str, now: datetime
    ) -> None:
        stmt = (
            update(J)
            .where(col(J.id) == job_id)
            .values(
                status="pending",
                attempts=func.greatest(J.attempts - 1, 0),
                not_before=not_before,
                last_error=reason[:500],
                locked_at=None,
                updated_at=now,
            )
        )
        try:
            await self.session.exec(stmt)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            stmt_replace = (
                update(J)
                .where(col(J.id) == job_id)
                .values(
                    status="done",
                    last_error="reemplazado por otro pendiente",
                    locked_at=None,
                    updated_at=now,
                )
            )
            await self.session.exec(stmt_replace)
            await self.session.commit()

    async def fail(self, job_id: UUID, *, error: str, now: datetime) -> None:
        stmt = (
            update(J)
            .where(col(J.id) == job_id)
            .values(
                status="failed",
                last_error=error[:500],
                locked_at=None,
                updated_at=now,
            )
        )
        await self.session.exec(stmt)
        await self.session.commit()

    async def recover_stale(
        self, *, locked_before: datetime, now: datetime
    ) -> int:
        limite_intentos = case(
            (col(J.kind) == "extract", MAX_INTENTOS[ProcessingJobKind.EXTRACT]),
            (col(J.kind) == "digest", MAX_INTENTOS[ProcessingJobKind.DIGEST]),
            else_=3,
        )
        # 1. Agotaron intentos -> failed
        stmt_failed = (
            update(J)
            .where(
                J.status == "running",
                J.locked_at < locked_before,
                J.attempts >= limite_intentos,
            )
            .values(
                status="failed",
                last_error="abandonado: el proceso se cortó durante el trabajo",
                locked_at=None,
                updated_at=now,
            )
        )
        res1 = await self.session.exec(stmt_failed)

        # 2. Con gemelo pendiente -> done (reemplazado)
        P = AttachmentProcessingJobModel
        gemelo_pendiente = select(1).where(
            P.id != J.id,
            P.status == "pending",
            P.kind == J.kind,
            P.tender_id == J.tender_id,
            P.attachment_file_id.is_not_distinct_from(J.attachment_file_id),
            P.workspace_id.is_not_distinct_from(J.workspace_id),
        )
        stmt_gemelo = (
            update(J)
            .where(
                J.status == "running",
                J.locked_at < locked_before,
                exists(gemelo_pendiente),
            )
            .values(
                status="done",
                last_error="reemplazado por otro pendiente",
                locked_at=None,
                updated_at=now,
            )
        )
        res2 = await self.session.exec(stmt_gemelo)

        # 3. El resto -> pending para reintentar
        stmt_pending = (
            update(J)
            .where(
                J.status == "running",
                J.locked_at < locked_before,
            )
            .values(
                status="pending",
                not_before=now,
                locked_at=None,
                updated_at=now,
            )
        )
        res3 = await self.session.exec(stmt_pending)
        await self.session.commit()

        return (
            (res1.rowcount or 0)
            + (res2.rowcount or 0)
            + (res3.rowcount or 0)
        )

    async def files_missing_extraction(
        self, *, prompt_version: str, limit: int
    ) -> list[tuple[UUID, UUID]]:
        extraccion_existe = select(1).where(
            E.attachment_file_id == F.id,
            E.prompt_version == prompt_version,
        )
        trabajo_activo = select(1).where(
            J.attachment_file_id == F.id,
            J.kind == "extract",
            col(J.status).in_(["pending", "running", "failed"]),
        )
        stmt = (
            select(F.id, F.tender_id)
            .where(
                F.status == "stored",
                ~exists(extraccion_existe),
                ~exists(trabajo_activo),
            )
            .order_by(col(F.completed_at).nulls_last())
            .limit(limit)
        )
        filas = (await self.session.exec(stmt)).all()
        return [(fila[0], fila[1]) for fila in filas]

    async def purge_finished(self, *, before: datetime) -> int:
        stmt = sa_delete(J).where(J.status == "done", J.updated_at < before)
        res = await self.session.exec(stmt)
        await self.session.commit()
        return res.rowcount or 0
