from datetime import datetime
from uuid import uuid4

from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.domain.entities.tender_milestone import MilestoneKind, MilestoneSource, TenderMilestone


def test_document_context_dto_default_bytes_vacio():
    dto = DocumentContextDTO(document_name="Bases.pdf", file_type="pdf")
    assert dto.file_bytes == b""
    assert dto.text is None
    assert dto.file_ref is None
    assert dto.file_id is None
    assert dto.source == "panel"
    assert dto.is_corrupted is False


def test_document_context_dto_con_texto_y_ref():
    fid = uuid4()
    dto = DocumentContextDTO(
        document_name="Bases.pdf",
        file_type="pdf",
        text="Contenido del documento",
        file_ref="shared/123/bases.pdf",
        file_id=fid,
        source="legacy_chat",
    )
    assert dto.document_name == "Bases.pdf"
    assert dto.text == "Contenido del documento"
    assert dto.file_ref == "shared/123/bases.pdf"
    assert dto.file_id == fid
    assert dto.source == "legacy_chat"


def test_tender_milestone_acepta_source_file_id():
    file_id = uuid4()
    milestone = TenderMilestone(
        user_id=uuid4(),
        tender_id=uuid4(),
        kind=MilestoneKind.PUBLICACION,
        title="Publicación en bases",
        source=MilestoneSource.IA_DOCUMENTO,
        source_file_id=file_id,
        source_document_id=None,
        due_at=datetime(2026, 10, 15, 12, 0),
        has_time=True,
    )
    assert milestone.source_file_id == file_id
    assert milestone.source_document_id is None
