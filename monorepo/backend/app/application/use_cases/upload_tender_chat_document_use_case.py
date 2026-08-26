import os
from typing import Optional
from uuid import UUID, uuid4

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.errors.tender_chat_errors import (
    UnsupportedDocumentTypeError,
    MaxDocumentsExceededError,
)


class UploadTenderChatDocumentUseCase:
    """Caso de uso para subir y validar documentos adjuntos al chat de una licitación."""

    ALLOWED_EXTENSIONS = {"pdf", "xlsx", "png"}
    MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
    MAX_DOCUMENTS_PER_CHAT = 5

    def __init__(self, chat_repo: ITenderChatRepository):
        self.chat_repo = chat_repo

    async def execute(
        self,
        tender_id: UUID,
        user_id: UUID,
        file_name: str,
        file_bytes: bytes,
        file_type: Optional[str] = None,
    ) -> TenderChatDocument:
        # 1. Validar tamaño del archivo
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("El archivo está vacío.")

        if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"El archivo excede el tamaño máximo permitido de {self.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            )

        # 2. Validar extensión de archivo
        detected_type = file_type
        if not detected_type:
            if "." in file_name:
                detected_type = file_name.rsplit(".", 1)[-1].lower()
            else:
                detected_type = ""

        detected_type = detected_type.lower().strip()
        if detected_type not in self.ALLOWED_EXTENSIONS:
            raise UnsupportedDocumentTypeError()

        # 3. Validar límite de documentos por chat
        existing_docs = await self.chat_repo.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
        if len(existing_docs) >= self.MAX_DOCUMENTS_PER_CHAT:
            raise MaxDocumentsExceededError(
                f"Se ha alcanzado el límite máximo de {self.MAX_DOCUMENTS_PER_CHAT} documentos adjuntos por chat."
            )

        # 4. Construir ruta de almacenamiento y entidad
        doc_id = uuid4()
        safe_name = os.path.basename(file_name)
        storage_path = f"uploads/{tender_id}/{user_id}/{doc_id}_{safe_name}"

        doc = TenderChatDocument(
            id=doc_id,
            tender_id=tender_id,
            user_id=user_id,
            file_name=safe_name,
            file_type=detected_type,  # type: ignore[arg-type]
            file_size_bytes=len(file_bytes),
            storage_path=storage_path,
        )

        # 5. Persistir documento
        saved_doc = await self.chat_repo.save_document(doc=doc, file_bytes=file_bytes)
        return saved_doc
