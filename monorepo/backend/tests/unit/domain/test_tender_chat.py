import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from app.domain.entities.tender_chat import (
    Citation,
    TenderChatMessage,
    TenderChatDocument,
)
from app.domain.errors.tender_chat_errors import (
    TenderChatError,
    TenderChatQueryTooLongError,
    TenderAssistantUnavailableError,
    UnsupportedDocumentTypeError,
    DocumentNotFoundError,
    MaxDocumentsExceededError,
)


def test_create_valid_citation():
    """Verifica que se cree una instancia válida de Citation con todos los campos."""
    citation = Citation(
        document_name="Bases_Administrativas.pdf",
        page_or_sheet="Página 4",
        quote="El plazo máximo de entrega será de 15 días hábiles."
    )
    assert citation.document_name == "Bases_Administrativas.pdf"
    assert citation.page_or_sheet == "Página 4"
    assert citation.quote == "El plazo máximo de entrega será de 15 días hábiles."


def test_create_citation_without_optional_page():
    """Verifica que Citation permita page_or_sheet como None."""
    citation = Citation(
        document_name="Especificaciones.pdf",
        quote="Garantía requerida del 5%."
    )
    assert citation.document_name == "Especificaciones.pdf"
    assert citation.page_or_sheet is None
    assert citation.quote == "Garantía requerida del 5%."


def test_create_valid_user_chat_message():
    """Verifica la creación de un mensaje emitido por el usuario."""
    tender_id = uuid4()
    user_id = uuid4()
    msg = TenderChatMessage(
        tender_id=tender_id,
        user_id=user_id,
        role="user",
        content="¿Cuál es el plazo de entrega exigido?"
    )
    assert msg.tender_id == tender_id
    assert msg.user_id == user_id
    assert msg.role == "user"
    assert msg.content == "¿Cuál es el plazo de entrega exigido?"
    assert msg.citations == []
    assert isinstance(msg.created_at, datetime)
    assert msg.id is not None


def test_create_valid_assistant_chat_message_with_citations():
    """Verifica la creación de un mensaje emitido por el asistente con citas textuales."""
    tender_id = uuid4()
    user_id = uuid4()
    citation = Citation(
        document_name="terminos_referencia.pdf",
        page_or_sheet="Pág 3",
        quote="El plazo de entrega será de 3 días corridos."
    )
    msg = TenderChatMessage(
        tender_id=tender_id,
        user_id=user_id,
        role="assistant",
        content="El plazo de entrega es de 3 días corridos según las bases.",
        citations=[citation]
    )
    assert msg.role == "assistant"
    assert len(msg.citations) == 1
    assert msg.citations[0].document_name == "terminos_referencia.pdf"


@pytest.mark.parametrize("invalid_role", ["admin", "system", "bot", ""])
def test_invalid_chat_role_raises_validation_error(invalid_role: str):
    """Verifica que el rol solo pueda ser 'user' o 'assistant'."""
    with pytest.raises(ValidationError):
        TenderChatMessage(
            tender_id=uuid4(),
            user_id=uuid4(),
            role=invalid_role,
            content="Hola"
        )


def test_empty_content_raises_validation_error():
    """Verifica que el contenido del mensaje no pueda estar vacío o contener solo espacios."""
    with pytest.raises(ValidationError):
        TenderChatMessage(
            tender_id=uuid4(),
            user_id=uuid4(),
            role="user",
            content="   "
        )


def test_create_valid_tender_chat_document():
    """Verifica la creación válida de un documento adjunto al chat."""
    tender_id = uuid4()
    user_id = uuid4()
    doc = TenderChatDocument(
        tender_id=tender_id,
        user_id=user_id,
        file_name="especificaciones_tecnicas.pdf",
        file_type="pdf",
        file_size_bytes=1024 * 500,
        storage_path="uploads/tenders/especificaciones_tecnicas.pdf"
    )
    assert doc.tender_id == tender_id
    assert doc.user_id == user_id
    assert doc.file_name == "especificaciones_tecnicas.pdf"
    assert doc.file_type == "pdf"
    assert doc.file_size_bytes == 512000
    assert doc.storage_path == "uploads/tenders/especificaciones_tecnicas.pdf"
    assert isinstance(doc.created_at, datetime)
    assert doc.id is not None


@pytest.mark.parametrize("valid_type", ["pdf", "xlsx", "png"])
def test_valid_document_types(valid_type: str):
    """Verifica que se permitan tipos pdf, xlsx y png."""
    doc = TenderChatDocument(
        tender_id=uuid4(),
        user_id=uuid4(),
        file_name=f"archivo.{valid_type}",
        file_type=valid_type,
        file_size_bytes=1000,
        storage_path=f"uploads/archivo.{valid_type}"
    )
    assert doc.file_type == valid_type


@pytest.mark.parametrize("invalid_type", ["exe", "zip", "docx", "jpg", "txt", ""])
def test_invalid_document_type_raises_validation_error(invalid_type: str):
    """Verifica que se rechacen extensiones no permitidas."""
    with pytest.raises(ValidationError):
        TenderChatDocument(
            tender_id=uuid4(),
            user_id=uuid4(),
            file_name=f"archivo.{invalid_type}",
            file_type=invalid_type,
            file_size_bytes=1000,
            storage_path="uploads/archivo"
        )


def test_negative_or_zero_file_size_raises_validation_error():
    """Verifica que el tamaño en bytes deba ser estrictamente mayor a 0."""
    with pytest.raises(ValidationError):
        TenderChatDocument(
            tender_id=uuid4(),
            user_id=uuid4(),
            file_name="archivo.pdf",
            file_type="pdf",
            file_size_bytes=0,
            storage_path="uploads/archivo.pdf"
        )


def test_domain_errors_messages_and_hierarchy():
    """Verifica que las excepciones de dominio hereden de TenderChatError y tengan mensajes claros."""
    err_long = TenderChatQueryTooLongError()
    assert isinstance(err_long, TenderChatError)
    assert "1000" in str(err_long)

    err_unavail = TenderAssistantUnavailableError()
    assert isinstance(err_unavail, TenderChatError)
    assert "El asistente virtual se encuentra temporalmente fuera de servicio" in str(err_unavail)

    err_type = UnsupportedDocumentTypeError()
    assert isinstance(err_type, TenderChatError)
    assert "PDF, XLSX y PNG" in str(err_type)

    err_not_found = DocumentNotFoundError()
    assert isinstance(err_not_found, TenderChatError)

    err_max = MaxDocumentsExceededError()
    assert isinstance(err_max, TenderChatError)


def test_create_valid_document_discrepancy():
    """Verifica la creación válida de una discrepancia entre documentos."""
    from app.domain.entities.tender_chat import DocumentDiscrepancy

    citation_a = Citation(
        document_name="Bases_Administrativas.pdf",
        page_or_sheet="Página 12",
        quote="El plazo de ejecución será de 30 días corridos."
    )
    citation_b = Citation(
        document_name="Especificaciones_Tecnicas.pdf",
        page_or_sheet="Página 3",
        quote="El plazo de ejecución será de 45 días corridos."
    )

    discrepancy = DocumentDiscrepancy(
        topic="Plazo de ejecución",
        description="Las bases administrativas indican 30 días mientras que las especificaciones técnicas indican 45 días.",
        conflicting_sources=[citation_a, citation_b]
    )

    assert discrepancy.topic == "Plazo de ejecución"
    assert "30 días" in discrepancy.description
    assert len(discrepancy.conflicting_sources) == 2
    assert discrepancy.conflicting_sources[0].document_name == "Bases_Administrativas.pdf"


def test_document_discrepancy_empty_fields_raises_validation_error():
    """Verifica que DocumentDiscrepancy valide que topic y description no estén vacíos."""
    from app.domain.entities.tender_chat import DocumentDiscrepancy

    with pytest.raises(ValidationError):
        DocumentDiscrepancy(
            topic="   ",
            description="Alguna descripción",
            conflicting_sources=[]
        )

    with pytest.raises(ValidationError):
        DocumentDiscrepancy(
            topic="Tema válido",
            description="",
            conflicting_sources=[]
        )


def test_assistant_chat_message_with_discrepancies_and_warnings():
    """Verifica que TenderChatMessage soporte discrepancias, advertencias y aspectos sin respaldo."""
    from app.domain.entities.tender_chat import DocumentDiscrepancy

    discrepancy = DocumentDiscrepancy(
        topic="Garantía de seriedad",
        description="Inconsistencia en el porcentaje de garantía exigido.",
        conflicting_sources=[
            Citation(document_name="Doc1.pdf", quote="5%"),
            Citation(document_name="Doc2.pdf", quote="10%"),
        ]
    )

    msg = TenderChatMessage(
        tender_id=uuid4(),
        user_id=uuid4(),
        role="assistant",
        content="Se detectaron discrepancias entre los documentos de la licitación.",
        discrepancies=[discrepancy],
        warnings=["El archivo anexo_3.pdf está corrupto y no pudo ser analizado."],
        unbacked_aspects=["Presupuesto disponible estimado"],
        has_sufficient_info=False
    )

    assert len(msg.discrepancies) == 1
    assert msg.discrepancies[0].topic == "Garantía de seriedad"
    assert len(msg.warnings) == 1
    assert "anexo_3.pdf" in msg.warnings[0]
    assert msg.unbacked_aspects == ["Presupuesto disponible estimado"]
    assert msg.has_sufficient_info is False


def test_corrupted_and_unreadable_document_errors():
    """Verifica que CorruptedDocumentError y UnreadableDocumentError hereden de TenderChatError y tengan mensajes adecuados."""
    from app.domain.errors.tender_chat_errors import (
        CorruptedDocumentError,
        UnreadableDocumentError,
    )

    err_corrupt = CorruptedDocumentError("El archivo anexo.pdf está dañado o no tiene formato válido.")
    assert isinstance(err_corrupt, TenderChatError)
    assert "dañado" in str(err_corrupt)

    err_unreadable = UnreadableDocumentError("No fue posible extraer o leer el contenido del documento.")
    assert isinstance(err_unreadable, TenderChatError)
    assert "leer el contenido" in str(err_unreadable)

