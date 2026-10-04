from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.errors.attachment_errors import (
    AttachmentFileNotFound,
    ConcurrentUploadConflict,
    UploadQuotaExceeded,
)
from app.infrastructure.repositories.attachment_file_model import (
    AttachmentFileModel,
    AttachmentUploadQuotaModel,
)

_UNICA = "uq_attachment_file_attachment_sha_workspace"
_CON_ARCHIVO = (
    AttachmentFileStatus.STORED.value,
    AttachmentFileStatus.UNSUPPORTED.value,
)


def _columnas(archivo: AttachmentFile) -> dict[str, Any]:
    """Los campos de la entidad como los guarda la tabla: los enums, como texto."""
    return {
        "id": archivo.id,
        "tender_attachment_id": archivo.tender_attachment_id,
        "tender_id": archivo.tender_id,
        "sha256": archivo.sha256,
        "size_bytes": archivo.size_bytes,
        "mime_declared": archivo.mime_declared,
        "storage_key": archivo.storage_key,
        "source": archivo.source.value,
        "uploader_user_id": archivo.uploader_user_id,
        "workspace_id": archivo.workspace_id,
        "visibility": archivo.visibility.value,
        "trust": archivo.trust.value,
        "status": archivo.status.value,
        "created_at": archivo.created_at,
        "completed_at": archivo.completed_at,
        "purge_after": archivo.purge_after,
    }


def _a_entidad(m: AttachmentFileModel) -> AttachmentFile:
    return AttachmentFile(
        id=m.id,
        tender_attachment_id=m.tender_attachment_id,
        tender_id=m.tender_id,
        sha256=m.sha256,
        size_bytes=m.size_bytes,
        mime_declared=m.mime_declared,
        storage_key=m.storage_key,
        source=AttachmentFileSource(m.source),
        uploader_user_id=m.uploader_user_id,
        workspace_id=m.workspace_id,
        visibility=AttachmentVisibility(m.visibility),
        trust=AttachmentTrust(m.trust),
        status=AttachmentFileStatus(m.status),
        created_at=m.created_at,
        completed_at=m.completed_at,
        purge_after=m.purge_after,
    )


class SqlAttachmentFileRepository(IAttachmentFileRepository):
    """Las sesiones de integración expiran los modelos al confirmar: por eso cada
    método devuelve la entidad armada **antes** del `commit`, nunca el modelo después."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, file_id: UUID) -> AttachmentFile | None:
        modelo = await self.session.get(AttachmentFileModel, file_id)
        return _a_entidad(modelo) if modelo is not None else None

    async def _uno(self, *condiciones: Any) -> AttachmentFile | None:
        modelo = (
            await self.session.exec(
                select(AttachmentFileModel)
                .where(*condiciones)
                .order_by(col(AttachmentFileModel.created_at).desc())
                .limit(1)
            )
        ).first()
        return _a_entidad(modelo) if modelo is not None else None

    async def find_for_workspace(
        self, *, tender_attachment_id: UUID, sha256: str, workspace_id: UUID
    ) -> AttachmentFile | None:
        return await self._uno(
            col(AttachmentFileModel.tender_attachment_id) == tender_attachment_id,
            col(AttachmentFileModel.sha256) == sha256,
            col(AttachmentFileModel.workspace_id) == workspace_id,
        )

    async def find_shared_stored(
        self, *, tender_attachment_id: UUID, sha256: str
    ) -> AttachmentFile | None:
        return await self._uno(
            col(AttachmentFileModel.tender_attachment_id) == tender_attachment_id,
            col(AttachmentFileModel.sha256) == sha256,
            col(AttachmentFileModel.visibility) == AttachmentVisibility.SHARED.value,
            col(AttachmentFileModel.status) == AttachmentFileStatus.STORED.value,
        )

    async def find_stored_by_storage_key(self, storage_key: str) -> AttachmentFile | None:
        return await self._uno(
            col(AttachmentFileModel.storage_key) == storage_key,
            col(AttachmentFileModel.status).in_(_CON_ARCHIVO),
        )

    async def list_for_workspace_attachment(
        self, *, tender_attachment_id: UUID, workspace_id: UUID
    ) -> list[AttachmentFile]:
        modelos = (
            await self.session.exec(
                select(AttachmentFileModel).where(
                    col(AttachmentFileModel.tender_attachment_id) == tender_attachment_id,
                    col(AttachmentFileModel.workspace_id) == workspace_id,
                )
            )
        ).all()
        return [_a_entidad(m) for m in modelos]

    async def list_visible_for_tender(
        self, *, tender_id: UUID, workspace_id: UUID | None
    ) -> list[AttachmentFile]:
        # Los compartidos los ve cualquiera; los privados, solo su empresa.
        visibles = col(AttachmentFileModel.visibility) == AttachmentVisibility.SHARED.value
        if workspace_id is not None:
            visibles = or_(visibles, col(AttachmentFileModel.workspace_id) == workspace_id)
        modelos = (
            await self.session.exec(
                select(AttachmentFileModel).where(
                    col(AttachmentFileModel.tender_id) == tender_id,
                    col(AttachmentFileModel.status) != AttachmentFileStatus.PURGED.value,
                    visibles,
                )
            )
        ).all()
        return [_a_entidad(m) for m in modelos]

    async def _confirmar(self) -> None:
        """Confirma; si choca la clave única, deshace todo y avisa que ya hay una subida."""
        try:
            await self.session.commit()
        except IntegrityError as exc:
            # El rollback también deshace el +1 del cupo, si lo hubo.
            await self.session.rollback()
            if _UNICA in str(exc.orig):
                raise ConcurrentUploadConflict() from exc
            raise

    async def create(self, file: AttachmentFile) -> AttachmentFile:
        self.session.add(AttachmentFileModel(**_columnas(file)))
        await self._confirmar()
        return file

    async def create_consuming_quota(
        self, file: AttachmentFile, *, month: date, limit: int
    ) -> AttachmentFile:
        # Un solo statement atómico: inserta el mes en 1, o suma 1 solo mientras
        # no se llegó al tope. Dos subidas simultáneas no pueden pasarse: la
        # segunda espera el lock de la fila y ve el valor ya actualizado.
        tabla = AttachmentUploadQuotaModel.__table__  # type: ignore[attr-defined]
        insercion = pg_insert(AttachmentUploadQuotaModel).values(
            workspace_id=file.workspace_id, month=month, used=1
        )
        stmt = insercion.on_conflict_do_update(
            index_elements=["workspace_id", "month"],
            set_={"used": tabla.c.used + 1},
            where=tabla.c.used < limit,  # sin fila devuelta = tope alcanzado
        ).returning(tabla.c.used)
        filas = (await self.session.exec(stmt)).all()  # type: ignore[call-overload]
        if not filas:
            await self.session.rollback()
            raise UploadQuotaExceeded(used=limit, limit=limit)
        # El cupo y la fila van en la misma transacción.
        self.session.add(AttachmentFileModel(**_columnas(file)))
        await self._confirmar()
        return file

    async def update(self, file: AttachmentFile) -> AttachmentFile:
        modelo = await self.session.get(AttachmentFileModel, file.id)
        if modelo is None:
            raise AttachmentFileNotFound()
        for nombre, valor in _columnas(file).items():
            setattr(modelo, nombre, valor)
        self.session.add(modelo)
        await self.session.commit()
        return file

    async def delete(self, file_id: UUID) -> None:
        await self.session.exec(  # type: ignore[call-overload]
            sa_delete(AttachmentFileModel).where(col(AttachmentFileModel.id) == file_id)
        )
        await self.session.commit()

    async def count_other_references(self, *, storage_key: str, excluding_id: UUID) -> int:
        resultado = await self.session.exec(
            select(func.count())
            .select_from(AttachmentFileModel)
            .where(
                col(AttachmentFileModel.storage_key) == storage_key,
                col(AttachmentFileModel.id) != excluding_id,
                col(AttachmentFileModel.status) != AttachmentFileStatus.PURGED.value,
            )
        )
        return resultado.one()

    async def get_quota_used(self, *, workspace_id: UUID, month: date) -> int:
        usado = (
            await self.session.exec(
                select(AttachmentUploadQuotaModel.used).where(
                    col(AttachmentUploadQuotaModel.workspace_id) == workspace_id,
                    col(AttachmentUploadQuotaModel.month) == month,
                )
            )
        ).first()
        return usado or 0
