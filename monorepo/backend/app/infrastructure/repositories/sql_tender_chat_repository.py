import os
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.domain.entities.tender_chat import (
    TenderChatMessage,
    TenderChatDocument,
    Citation,
)
from app.infrastructure.repositories.tender_chat_model import (
    TenderChatMessageModel,
    TenderChatDocumentModel,
)


class SQLTenderChatRepository(ITenderChatRepository):
    """Implementación relacional (SQLModel / PostgreSQL) del repositorio de chat y documentos."""

    def __init__(self, session: AsyncSession, storage_dir: Optional[Path] = None):
        self.session = session
        self.storage_dir = storage_dir or Path("storage/chat_uploads")

    # --- Conversiones de Modelos a Entidades ---

    def _message_to_entity(self, model: TenderChatMessageModel) -> TenderChatMessage:
        citations = []
        for c in model.citations or []:
            citations.append(
                Citation(
                    document_name=c.get("document_name", ""),
                    page_or_sheet=c.get("page_or_sheet"),
                    quote=c.get("quote", ""),
                )
            )
        return TenderChatMessage(
            id=model.id,
            tender_id=model.tender_id,
            user_id=model.user_id,
            role=model.role,  # type: ignore[arg-type]
            content=model.content,
            citations=citations,
            created_at=model.created_at,
        )

    def _message_to_model(self, entity: TenderChatMessage) -> TenderChatMessageModel:
        citations_data = [
            {
                "document_name": c.document_name,
                "page_or_sheet": c.page_or_sheet,
                "quote": c.quote,
            }
            for c in entity.citations
        ]
        return TenderChatMessageModel(
            id=entity.id,
            tender_id=entity.tender_id,
            user_id=entity.user_id,
            role=entity.role,
            content=entity.content,
            citations=citations_data,
            created_at=entity.created_at,
        )

    def _doc_to_entity(self, model: TenderChatDocumentModel) -> TenderChatDocument:
        return TenderChatDocument(
            id=model.id,
            tender_id=model.tender_id,
            user_id=model.user_id,
            file_name=model.file_name,
            file_type=model.file_type,  # type: ignore[arg-type]
            file_size_bytes=model.file_size_bytes,
            storage_path=model.storage_path,
            created_at=model.created_at,
        )

    # --- Métodos del Contrato ITenderChatRepository ---

    async def save_message(self, message: TenderChatMessage) -> TenderChatMessage:
        model = self._message_to_model(message)
        self.session.add(model)
        await self.session.commit()
        return message

    async def get_history(self, user_id: UUID, tender_id: UUID, limit: int = 50) -> List[TenderChatMessage]:
        query = (
            select(TenderChatMessageModel)
            .where(
                TenderChatMessageModel.user_id == user_id,
                TenderChatMessageModel.tender_id == tender_id,
            )
            .order_by(col(TenderChatMessageModel.created_at).asc())
            .limit(limit)
        )
        result = await self.session.exec(query)
        models = result.all()
        return [self._message_to_entity(m) for m in models]

    async def save_document(self, doc: TenderChatDocument, file_bytes: bytes) -> TenderChatDocument:
        # 1. Guardar archivo físico en disco
        target_dir = self.storage_dir / str(doc.tender_id) / str(doc.user_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{doc.id}_{doc.file_name}"
        file_path.write_bytes(file_bytes)

        # 2. Actualizar ruta y persistir modelo en BD
        storage_path_str = str(file_path)
        doc_model = TenderChatDocumentModel(
            id=doc.id,
            tender_id=doc.tender_id,
            user_id=doc.user_id,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size_bytes=doc.file_size_bytes,
            storage_path=storage_path_str,
            created_at=doc.created_at,
        )
        self.session.add(doc_model)
        await self.session.commit()

        return TenderChatDocument(
            id=doc.id,
            tender_id=doc.tender_id,
            user_id=doc.user_id,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size_bytes=doc.file_size_bytes,
            storage_path=storage_path_str,
            created_at=doc.created_at,
        )

    async def get_documents_by_chat(self, user_id: UUID, tender_id: UUID) -> List[TenderChatDocument]:
        query = (
            select(TenderChatDocumentModel)
            .where(
                TenderChatDocumentModel.user_id == user_id,
                TenderChatDocumentModel.tender_id == tender_id,
            )
            .order_by(col(TenderChatDocumentModel.created_at).asc())
        )
        result = await self.session.exec(query)
        models = result.all()
        return [self._doc_to_entity(m) for m in models]

    async def get_document_bytes(self, document_id: UUID, user_id: UUID) -> Optional[bytes]:
        query = select(TenderChatDocumentModel).where(
            TenderChatDocumentModel.id == document_id,
            TenderChatDocumentModel.user_id == user_id,
        )
        result = await self.session.exec(query)
        doc_model = result.first()
        if not doc_model or not doc_model.storage_path:
            return None

        file_path = Path(doc_model.storage_path)
        if file_path.exists():
            return file_path.read_bytes()
        return None

    async def delete_document(self, document_id: UUID, user_id: UUID) -> bool:
        query = select(TenderChatDocumentModel).where(
            TenderChatDocumentModel.id == document_id,
            TenderChatDocumentModel.user_id == user_id,
        )
        result = await self.session.exec(query)
        doc_model = result.first()
        if not doc_model:
            return False

        # Eliminar archivo de disco si existe
        if doc_model.storage_path:
            file_path = Path(doc_model.storage_path)
            if file_path.exists():
                try:
                    os.remove(file_path)
                except OSError:
                    pass

        # Eliminar registro de BD
        await self.session.delete(doc_model)
        await self.session.commit()
        return True
