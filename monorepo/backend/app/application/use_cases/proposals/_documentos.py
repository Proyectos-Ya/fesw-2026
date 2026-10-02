from uuid import UUID

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.application.services.tender_assistant_ai_service import DocumentContextDTO


async def adjuntos_del_usuario(
    chat_repo: ITenderChatRepository,
    validator: IDocumentValidatorService | None,
    user_id: UUID,
    tender_id: UUID,
) -> list[DocumentContextDTO]:
    """Los adjuntos que el usuario subió en el asistente para esta licitación.

    Son por usuario, no por empresa (plan 230, §5 punto 7). Un archivo que no se
    puede leer va marcado como dañado en vez de hacer fallar el análisis.
    """
    documentos: list[DocumentContextDTO] = []
    for doc in await chat_repo.get_documents_by_chat(
        user_id=user_id, tender_id=tender_id
    ):
        datos = await chat_repo.get_document_bytes(doc.id, user_id)
        daniado = not datos
        if datos and validator is not None:
            daniado = not validator.validate_integrity(
                file_bytes=datos, file_name=doc.file_name, declared_type=doc.file_type
            ).is_valid
        documentos.append(
            DocumentContextDTO(
                document_name=doc.file_name,
                file_type=doc.file_type,
                file_bytes=b"" if daniado or not datos else datos,
                is_corrupted=daniado,
            )
        )
    return documentos
