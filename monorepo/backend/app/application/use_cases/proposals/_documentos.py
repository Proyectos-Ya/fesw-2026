import logging
from uuid import UUID

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.services.anexos_visibles import anexos_visibles
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.application.services.tender_assistant_ai_service import DocumentContextDTO

logger = logging.getLogger(__name__)


async def anexos_de_la_empresa(
    files: IAttachmentFileRepository,
    attachments: ITenderAttachmentRepository,
    storage: IAttachmentStorage | None,
    validator: IDocumentValidatorService | None,
    *,
    tender_id: UUID,
    workspace_id: UUID,
) -> list[DocumentContextDTO]:
    """Los anexos de la licitación que ve la empresa: los propios y los compartidos.

    Son los mismos que leen los hitos y el análisis (plan 233, parte 2). Antes
    eran los adjuntos del asistente, por usuario; los anexos son por empresa.
    Un archivo que no se puede leer va marcado como dañado en vez de hacer fallar
    el análisis. Los tipos que la IA no lee se pasan igual: los filtra el servicio.
    """
    documentos: list[DocumentContextDTO] = []
    for anexo in await anexos_visibles(
        files, attachments, tender_id=tender_id, workspace_id=workspace_id
    ):
        datos = await _contenido(storage, anexo.archivo.storage_key)
        daniado = not datos
        if datos and validator is not None:
            daniado = not validator.validate_integrity(
                file_bytes=datos, file_name=anexo.nombre, declared_type=anexo.tipo
            ).is_valid
        documentos.append(
            DocumentContextDTO(
                document_name=anexo.nombre,
                file_type=anexo.tipo,
                file_bytes=b"" if daniado or not datos else datos,
                is_corrupted=daniado,
            )
        )
    return documentos


async def _contenido(storage: IAttachmentStorage | None, key: str) -> bytes | None:
    if storage is None:
        return None
    try:
        return await storage.get_bytes(key)
    except Exception:
        logger.warning("No se pudo leer el anexo %s para la postulación.", key, exc_info=True)
        return None
