from sqlmodel import SQLModel

import app.infrastructure.repositories.models  # noqa: F401


def test_tender_chat_tables_are_registered_for_alembic() -> None:
    assert "tender_chat_messages" in SQLModel.metadata.tables
    assert "tender_chat_documents" in SQLModel.metadata.tables


def test_tender_attachment_is_registered_for_alembic() -> None:
    assert "tender_attachment" in SQLModel.metadata.tables
    assert "attachments_synced_at" in SQLModel.metadata.tables["tender"].c
