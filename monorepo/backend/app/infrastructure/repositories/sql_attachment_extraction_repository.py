"""Implementación SQL del repositorio de extracciones de anexos (plan 233, decisión 4)."""

from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.domain.entities.attachment_extraction import (
    AttachmentExtraction,
    AttachmentExtractionData,
    ExtractionInputMode,
    FuenteDeExtraccion,
)
from app.domain.entities.attachment_file import (
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.errors.attachment_processing_errors import (
    ExtractionAlreadyExists,
)
from app.infrastructure.repositories.attachment_file_model import (
    AttachmentFileModel as F,
)
from app.infrastructure.repositories.attachment_processing_model import (
    AttachmentExtractionModel as E,
)
from app.infrastructure.repositories.tender_attachment_model import (
    TenderAttachmentModel as A,
)


def _a_entidad(m: E) -> AttachmentExtraction:
    return AttachmentExtraction(
        id=m.id,
        attachment_file_id=m.attachment_file_id,
        tender_attachment_id=m.tender_attachment_id,
        tender_id=m.tender_id,
        sha256=m.sha256,
        prompt_version=m.prompt_version,
        model=m.model,
        input_mode=ExtractionInputMode(m.input_mode),
        data=AttachmentExtractionData.model_validate(m.data),
        citas_total=m.citas_total,
        citas_verificadas=m.citas_verificadas,
        texto_disponible=m.texto_disponible,
        usage_metadata=m.usage_metadata,
        reused_from_id=m.reused_from_id,
        created_at=m.created_at,
    )


class SqlAttachmentExtractionRepository(IAttachmentExtractionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_file(
        self, attachment_file_id: UUID, *, prompt_version: str
    ) -> AttachmentExtraction | None:
        stmt = select(E).where(
            E.attachment_file_id == attachment_file_id,
            E.prompt_version == prompt_version,
        )
        modelo = (await self.session.exec(stmt)).first()
        return _a_entidad(modelo) if modelo is not None else None

    async def find_reusable(
        self,
        *,
        tender_attachment_id: UUID,
        sha256: str,
        prompt_version: str,
        excluding_file_id: UUID,
    ) -> AttachmentExtraction | None:
        stmt = (
            select(E)
            .where(
                E.tender_attachment_id == tender_attachment_id,
                E.sha256 == sha256,
                E.prompt_version == prompt_version,
                E.attachment_file_id != excluding_file_id,
            )
            .order_by(col(E.created_at).desc())
            .limit(1)
        )
        modelo = (await self.session.exec(stmt)).first()
        return _a_entidad(modelo) if modelo is not None else None

    async def create(
        self, extraction: AttachmentExtraction
    ) -> AttachmentExtraction:
        modelo = E(
            id=extraction.id,
            attachment_file_id=extraction.attachment_file_id,
            tender_attachment_id=extraction.tender_attachment_id,
            tender_id=extraction.tender_id,
            sha256=extraction.sha256,
            prompt_version=extraction.prompt_version,
            model=extraction.model,
            input_mode=extraction.input_mode.value,
            data=extraction.data.model_dump(mode="json"),
            citas_total=extraction.citas_total,
            citas_verificadas=extraction.citas_verificadas,
            texto_disponible=extraction.texto_disponible,
            usage_metadata=extraction.usage_metadata,
            reused_from_id=extraction.reused_from_id,
            created_at=extraction.created_at,
        )
        self.session.add(modelo)
        try:
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            if "uq_attachment_extraction_file_prompt" in str(error):
                raise ExtractionAlreadyExists(
                    extraction.attachment_file_id, extraction.prompt_version
                ) from error
            raise
        return extraction

    async def list_sources(
        self,
        *,
        tender_id: UUID,
        workspace_id: UUID | None,
        prompt_version: str,
    ) -> list[FuenteDeExtraccion]:
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

        stmt = (
            select(E, F.visibility, F.trust, F.workspace_id, A.name, A.mp_document_id)
            .join(F, F.id == E.attachment_file_id)
            .join(A, A.id == E.tender_attachment_id)
            .where(
                E.tender_id == tender_id,
                E.prompt_version == prompt_version,
                F.status == "stored",
                A.removed_at.is_(None),
                visibilidad,
            )
            .order_by(col(E.created_at).asc())
        )
        filas = (await self.session.exec(stmt)).all()

        fuentes: list[FuenteDeExtraccion] = []
        for e, f_vis, f_trust, f_ws, a_name, a_mp in filas:
            fuentes.append(
                FuenteDeExtraccion(
                    extraction_id=e.id,
                    attachment_file_id=e.attachment_file_id,
                    tender_attachment_id=e.tender_attachment_id,
                    mp_document_id=a_mp,
                    documento=a_name,
                    sha256=e.sha256,
                    visibility=AttachmentVisibility(f_vis),
                    trust=AttachmentTrust(f_trust),
                    workspace_id=f_ws,
                    data=AttachmentExtractionData.model_validate(e.data),
                    citas_total=e.citas_total,
                    citas_verificadas=e.citas_verificadas,
                    texto_disponible=e.texto_disponible,
                    model=e.model,
                    prompt_version=e.prompt_version,
                    created_at=e.created_at,
                )
            )
        return fuentes
