from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_trust_repository import (
    IAttachmentTrustRepository,
    TrustSnapshot,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileStatus,
    AttachmentVisibility,
)
from app.infrastructure.repositories.attachment_file_model import AttachmentFileModel
from app.infrastructure.repositories.sql_attachment_file_repository import (
    _a_entidad,
    _columnas,
)
from app.infrastructure.repositories.sql_tender_attachment_repository import (
    _a_entidad as _anexo_a_entidad,
)
from app.infrastructure.repositories.supplier_member_model import SupplierMemberModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_attachment_model import (
    TenderAttachmentModel,
)


class SqlAttachmentTrustRepository(IAttachmentTrustRepository):
    """La promoción de anexos compartidos sobre Postgres (plan 233, decisión 6).

    Una instancia = una transacción: `lock_for_promotion` la abre y `save_promotion`
    o `release` la cierran. Por eso se crea con una sesión propia, no la de la
    petición.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_for_promotion(self, tender_attachment_id: UUID) -> TrustSnapshot | None:
        # FOR NO KEY UPDATE y no FOR UPDATE: dos promociones del mismo anexo piden
        # este candado y se ordenan, pero el INSERT de una subida nueva (su FK pide
        # FOR KEY SHARE sobre esta fila) no espera. Funciona detrás del pooler en
        # modo transacción, que no admite los advisory locks de sesión.
        fila = (
            await self.session.exec(
                select(TenderAttachmentModel)
                .where(col(TenderAttachmentModel.id) == tender_attachment_id)
                .with_for_update(key_share=True)
            )
        ).first()
        if fila is None:
            return None
        anexo = _anexo_a_entidad(fila)
        # Sentencia aparte y DESPUÉS del candado: en READ COMMITTED ve lo que otra
        # subida confirmó mientras esta esperaba. Leer antes, o en REPEATABLE READ,
        # perdería esa fila y nadie promovería.
        modelos = (
            await self.session.exec(
                select(AttachmentFileModel).where(
                    col(AttachmentFileModel.tender_attachment_id) == tender_attachment_id,
                    col(AttachmentFileModel.status) != AttachmentFileStatus.PURGED.value,
                )
            )
        ).all()
        archivos = [_a_entidad(m) for m in modelos]
        empresas = {a.workspace_id for a in archivos if a.workspace_id is not None}
        return TrustSnapshot(
            attachment=anexo, files=archivos, people=await self._personas(empresas)
        )

    async def _personas(self, empresas: set[UUID]) -> dict[UUID, frozenset[UUID]]:
        if not empresas:
            return {}
        personas: dict[UUID, set[UUID]] = defaultdict(set)
        duenos = await self.session.exec(
            select(SupplierModel.id, SupplierModel.user_id).where(
                col(SupplierModel.id).in_(empresas),
                col(SupplierModel.user_id).is_not(None),
            )
        )
        for empresa, usuario in duenos.all():
            if usuario is not None:
                personas[empresa].add(usuario)
        # Todas las membresías, también las revocadas: quien tuvo acceso a los
        # privados de una empresa no sirve para corroborarla desde otra.
        miembros = await self.session.exec(
            select(SupplierMemberModel.supplier_id, SupplierMemberModel.user_id).where(
                col(SupplierMemberModel.supplier_id).in_(empresas)
            )
        )
        for empresa, usuario in miembros.all():
            personas[empresa].add(usuario)
        return {e: frozenset(personas.get(e, set())) for e in empresas}

    async def save_promotion(
        self, *, updated: Sequence[AttachmentFile], created: Sequence[AttachmentFile]
    ) -> None:
        # Primero lo que se oculta, después lo que se muestra y al final lo nuevo: el
        # índice "una versión compartida por anexo" se verifica en cada sentencia y
        # no es diferible.
        for archivo in sorted(updated, key=lambda a: a.visibility == AttachmentVisibility.SHARED):
            await self.session.exec(  # type: ignore[call-overload]
                update(AttachmentFileModel)
                .where(col(AttachmentFileModel.id) == archivo.id)
                # Solo confianza y visibilidad: el `status` lo puede estar cambiando
                # la extracción de la decisión 4.
                .values(trust=archivo.trust.value, visibility=archivo.visibility.value)
            )
        for archivo in created:
            self.session.add(AttachmentFileModel(**_columnas(archivo)))
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise

    async def release(self) -> None:
        await self.session.rollback()
