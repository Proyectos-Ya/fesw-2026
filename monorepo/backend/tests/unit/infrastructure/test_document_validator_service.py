import io
import pytest
import zipfile
from app.infrastructure.services.document_validator_service import DocumentValidatorService
from app.application.services.document_validator_service import DocumentValidationResult


@pytest.fixture
def validator():
    return DocumentValidatorService()


# --- Pruebas de Archivos Válidos ---

def test_validate_valid_pdf(validator):
    # PDF mínimo válido
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000102 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF"
    )
    result = validator.validate_integrity(
        file_bytes=pdf_content,
        file_name="bases_administrativas.pdf",
        declared_type="pdf",
    )
    assert isinstance(result, DocumentValidationResult)
    assert result.is_valid is True
    assert result.file_type == "pdf"
    assert result.error_message is None


def test_validate_valid_xlsx(validator):
    # Crear un archivo XLSX (ZIP) mínimo en memoria
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types></Types>')
        zf.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook></workbook>')
    xlsx_bytes = buf.getvalue()

    result = validator.validate_integrity(
        file_bytes=xlsx_bytes,
        file_name="anexo_economico.xlsx",
        declared_type="xlsx",
    )
    assert result.is_valid is True
    assert result.file_type == "xlsx"
    assert result.error_message is None


def test_validate_valid_png(validator):
    # PNG mínimo de 1x1 pixel
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    result = validator.validate_integrity(
        file_bytes=png_bytes,
        file_name="plano_esquema.png",
        declared_type="png",
    )
    assert result.is_valid is True
    assert result.file_type == "png"
    assert result.error_message is None


# --- Pruebas de Archivos Corruptos / Inválidos ---

def test_validate_corrupted_pdf_without_header(validator):
    corrupt_bytes = b"Esto no es un PDF valido, son solo bytes de texto plano."
    result = validator.validate_integrity(
        file_bytes=corrupt_bytes,
        file_name="documento_falso.pdf",
        declared_type="pdf",
    )
    assert result.is_valid is False
    assert result.file_type == "pdf"
    assert "dañado" in result.error_message or "cabecera" in result.error_message or "inválida" in result.error_message


def test_validate_corrupted_xlsx_invalid_zip(validator):
    corrupt_bytes = b"PK\x03\x04bytes_corruptos_no_es_un_zip_valido"
    result = validator.validate_integrity(
        file_bytes=corrupt_bytes,
        file_name="anexo_danado.xlsx",
        declared_type="xlsx",
    )
    assert result.is_valid is False
    assert result.file_type == "xlsx"
    assert "dañado" in result.error_message or "válido" in result.error_message


def test_validate_corrupted_png_invalid_signature(validator):
    corrupt_bytes = b"\x89PNG\r\n\x1a\nbytes_truncados_sin_chunks_ihdr"
    result = validator.validate_integrity(
        file_bytes=corrupt_bytes,
        file_name="imagen_rota.png",
        declared_type="png",
    )
    assert result.is_valid is False
    assert result.file_type == "png"
    assert "dañada" in result.error_message or "válido" in result.error_message or "PNG" in result.error_message


def test_validate_empty_bytes(validator):
    result = validator.validate_integrity(
        file_bytes=b"",
        file_name="vacio.pdf",
        declared_type="pdf",
    )
    assert result.is_valid is False
    assert "vacío" in result.error_message


def test_validate_unsupported_type(validator):
    result = validator.validate_integrity(
        file_bytes=b"sample content",
        file_name="script.exe",
        declared_type="exe",
    )
    assert result.is_valid is False
    assert "no soportado" in result.error_message.lower()
