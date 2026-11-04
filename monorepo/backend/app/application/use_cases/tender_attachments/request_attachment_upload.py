"""Pedir la URL para subir un anexo (plan 233, decisión 2).

Primer paso de la subida: el navegador declara qué archivo va a subir (nombre,
tamaño y huella) y recibe una URL firmada para mandarlo directo al
almacenamiento. Acá se valida todo lo que se puede saber **antes** de recibir un
solo byte, y se decide si hay algo que subir.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.attachment_stored_listener import (
    IAttachmentStoredListener,
)
from app.domain.entities.attachment_file import (
    PLAZO_DE_SUBIDA_INCOMPLETA,
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from app.domain.errors.attachment_errors import (
    AttachmentAlreadyUploaded,
    AttachmentNotFound,
    AttachmentStorageUnavailable,
    AttachmentTooLarge,
)
from app.domain.services.attachment_files import (
    MAX_ATTACHMENT_SIZE_BYTES,
    clave_privada,
    mes_de_cuota,
    tiene_archivo,
    tipo_de_contenido,
    validar_archivo_para_anexo,
)
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)

UPLOAD_URL_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class UploadRequest:
    tender_id: UUID
    attachment_id: UUID
    workspace_id: UUID
    user_id: UUID
    file_name: str
    size_bytes: int
    mime: str
    sha256: str  # hex en minúsculas


@dataclass(frozen=True)
class UploadTicket:
    upload_id: UUID  # es el id del archivo: `complete` y `DELETE` usan el mismo
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class UploadDeduplicated:
    """Ya existe ese archivo para la empresa: no hay nada que subir."""

    file: AttachmentFile


class RequestAttachmentUploadUseCase:
    def __init__(
        self,
        *,
        attachments: ITenderAttachmentRepository,
        files: IAttachmentFileRepository,
        storage: IAttachmentStorage | None,
        listener: IAttachmentStoredListener,
        uploads_per_month: int,
        clock: Callable[[], datetime] = utc_now_naive,
        new_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self.attachments = attachments
        self.files = files
        self.storage = storage
        self.listener = listener
        self.uploads_per_month = uploads_per_month
        self.clock = clock
        self.new_id = new_id

    async def execute(self, req: UploadRequest) -> UploadTicket | UploadDeduplicated:
        # El orden fija los códigos de error y qué cuesta cupo: nada se cobra
        # hasta que el archivo calzó con el anexo oficial.
        if self.storage is None:
            raise AttachmentStorageUnavailable()

        anexo = await self.attachments.get_official_attachment(req.tender_id, req.attachment_id)
        if anexo is None:
            existente = await self.attachments.get_attachment(req.attachment_id)
            if existente is not None:
                raise AttachmentNotFound()
            lista = await self.attachments.get_official_list(req.tender_id)
            if lista is None:
                raise AttachmentNotFound()
            anexo = await self.attachments.create_attachment(
                tender_id=req.tender_id,
                attachment_id=req.attachment_id,
                name=req.file_name,
            )

        if req.size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
            raise AttachmentTooLarge(MAX_ATTACHMENT_SIZE_BYTES)

        validar_archivo_para_anexo(anexo, req.file_name)

        propio = await self.files.find_for_workspace(
            tender_attachment_id=anexo.id, sha256=req.sha256, workspace_id=req.workspace_id
        )
        if propio is not None and tiene_archivo(propio):
            return UploadDeduplicated(propio)

        # Camino de la decisión 6: hoy ningún archivo es compartido, así que no
        # encuentra nada. Nunca deduplica contra el privado de otra empresa.
        compartido = await self.files.find_shared_stored(
            tender_attachment_id=anexo.id, sha256=req.sha256
        )
        if compartido is not None:
            return UploadDeduplicated(compartido)

        # Un archivo vigente por (anexo, empresa): evita versiones dobles del
        # mismo documento oficial. Hay que borrar antes de subir otro.
        de_la_empresa = await self.files.list_for_workspace_attachment(
            tender_attachment_id=anexo.id, workspace_id=req.workspace_id
        )
        if any(tiene_archivo(a) and a.sha256 != req.sha256 for a in de_la_empresa):
            raise AttachmentAlreadyUploaded()

        ahora = self.clock()
        mime_declarado = req.mime.strip() or None
        clave = clave_privada(req.workspace_id, req.sha256, anexo.ext)

        # La clave del objeto depende de la empresa y del contenido, no del anexo.
        existente = await self.files.find_stored_by_storage_key(clave)
        if existente is not None:
            # Los mismos bytes ya están verificados para otro anexo de la empresa:
            # no se sube nada ni se gasta cupo (y no se emite una URL que podría
            # sobrescribir un objeto ya verificado).
            if propio is not None:
                archivo = await self.files.update(
                    propio.como_subiendo(
                        size_bytes=req.size_bytes,
                        mime_declared=mime_declarado,
                        uploader_user_id=req.user_id,
                        ahora=ahora,
                    ).como_guardado(ahora=ahora)
                )
            else:
                archivo = await self.files.create(
                    self._fila_nueva(req, anexo.id, anexo.tender_id, clave, mime_declarado, ahora)
                    .como_guardado(ahora=ahora)
                )
            await self._avisar(archivo)
            return UploadDeduplicated(archivo)

        if propio is not None:
            # Reintento de una subida `uploading`, `rejected` o `purged`: misma
            # fila, sin cobrar de nuevo.
            archivo = await self.files.update(
                propio.como_subiendo(
                    size_bytes=req.size_bytes,
                    mime_declared=mime_declarado,
                    uploader_user_id=req.user_id,
                    ahora=ahora,
                )
            )
        else:
            archivo = await self.files.create_consuming_quota(
                self._fila_nueva(req, anexo.id, anexo.tender_id, clave, mime_declarado, ahora),
                month=mes_de_cuota(ahora),
                limit=self.uploads_per_month,
            )

        firmada = self.storage.presign_put(
            key=clave,
            size_bytes=req.size_bytes,
            sha256_hex=req.sha256,
            content_type=tipo_de_contenido(req.mime),
            expires_in_seconds=UPLOAD_URL_TTL_SECONDS,
            now=ahora,
        )
        return UploadTicket(
            upload_id=archivo.id,
            url=firmada.url,
            method=firmada.method,
            headers=firmada.headers,
            expires_at=firmada.expires_at,
        )

    def _fila_nueva(
        self,
        req: UploadRequest,
        attachment_id: UUID,
        tender_id: UUID,
        clave: str,
        mime_declarado: str | None,
        ahora: datetime,
    ) -> AttachmentFile:
        return AttachmentFile(
            id=self.new_id(),
            tender_attachment_id=attachment_id,
            tender_id=tender_id,
            sha256=req.sha256,
            size_bytes=req.size_bytes,
            mime_declared=mime_declarado,
            storage_key=clave,
            source=AttachmentFileSource.MANUAL,
            uploader_user_id=req.user_id,
            workspace_id=req.workspace_id,
            status=AttachmentFileStatus.UPLOADING,
            created_at=ahora,
            purge_after=ahora + PLAZO_DE_SUBIDA_INCOMPLETA,
        )

    async def _avisar(self, archivo: AttachmentFile) -> None:
        # El archivo ya está guardado: que falle un trabajo posterior no cambia la respuesta.
        try:
            await self.listener.on_stored(archivo)
        except Exception:
            logger.exception("El listener de archivos guardados falló (archivo %s).", archivo.id)
