"""Implementación SQL del repositorio de resúmenes de licitaciones (plan 233, decisión 4)."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.domain.entities.tender_digest import (
    TenderDigest,
    TenderDigestData,
)
from app.infrastructure.repositories.attachment_processing_model import (
    TenderDigestModel,
)


def _a_entidad(m: TenderDigestModel) -> TenderDigest:
    return TenderDigest(
        id=m.id,
        tender_id=m.tender_id,
        workspace_id=m.workspace_id,
        version=m.version,
        extraction_set_hash=m.extraction_set_hash,
        is_current=m.is_current,
        source_count=m.source_count,
        data=TenderDigestData.model_validate(m.data),
        api_snapshot=m.api_snapshot,
        created_at=m.created_at,
    )


class SqlTenderDigestRepository(ITenderDigestRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_current(
        self, tender_id: UUID, workspace_id: UUID | None
    ) -> TenderDigest | None:
        condicion_ws = (
            TenderDigestModel.workspace_id == workspace_id
            if workspace_id is not None
            else TenderDigestModel.workspace_id.is_(None)
        )
        stmt = select(TenderDigestModel).where(
            TenderDigestModel.tender_id == tender_id,
            condicion_ws,
            TenderDigestModel.is_current.is_(True),
        )
        modelo = (await self.session.exec(stmt)).first()
        return _a_entidad(modelo) if modelo is not None else None

    async def replace_current(
        self, digest: TenderDigest, *, previous_id: UUID | None
    ) -> TenderDigest:
        if previous_id is not None:
            stmt_update = (
                update(TenderDigestModel)
                .where(
                    TenderDigestModel.id == previous_id,
                    TenderDigestModel.is_current.is_(True),
                )
                .values(is_current=False)
            )
            await self.session.exec(stmt_update)

        modelo = TenderDigestModel(
            id=digest.id,
            tender_id=digest.tender_id,
            workspace_id=digest.workspace_id,
            version=digest.version,
            extraction_set_hash=digest.extraction_set_hash,
            is_current=True,
            source_count=digest.source_count,
            data=digest.data.model_dump(mode="json"),
            api_snapshot=(
                digest.api_snapshot
                if isinstance(digest.api_snapshot, dict)
                else digest.api_snapshot.model_dump(mode="json")
            ),
            created_at=digest.created_at,
        )
        self.session.add(modelo)
        try:
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            if "uq_tender_digest_current" in str(error):
                actual = await self.get_current(
                    digest.tender_id, digest.workspace_id
                )
                if actual is not None:
                    return actual
            raise
        return digest

    async def retire_current(self, tender_id: UUID, workspace_id: UUID) -> None:
        stmt = (
            update(TenderDigestModel)
            .where(
                TenderDigestModel.tender_id == tender_id,
                TenderDigestModel.workspace_id == workspace_id,
                TenderDigestModel.is_current.is_(True),
            )
            .values(is_current=False)
        )
        await self.session.exec(stmt)
        await self.session.commit()

    async def workspaces_with_current(self, tender_id: UUID) -> list[UUID]:
        stmt = select(TenderDigestModel.workspace_id).where(
            TenderDigestModel.tender_id == tender_id,
            TenderDigestModel.is_current.is_(True),
            TenderDigestModel.workspace_id.is_not(None),
        )
        filas = (await self.session.exec(stmt)).all()
        return [f for f in filas if f is not None]
