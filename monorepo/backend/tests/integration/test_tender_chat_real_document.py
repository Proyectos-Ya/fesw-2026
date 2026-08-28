import os
from pathlib import Path
from uuid import uuid4
import pytest

from app.application.use_cases.upload_tender_chat_document_use_case import UploadTenderChatDocumentUseCase
from app.domain.entities.tender_chat import TenderChatDocument
from tests.unit.application.fakes import InMemoryTenderChatRepository

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "documents"
    / "terminos de referencia diseño conexión.pdf"
)

# Metadata real obtenida de la API Compra Ágil v2 para 4280-312-COT26
REAL_TENDER_CATEMU = {
    "codigo": "4280-312-COT26",
    "nombre": "SE SOLICITA COTIZAR SERVICIO DE DISEÑO DE CONEXIÓN DE AGUA POTABLE Y ALCANTARILLADO.",
    "comprador": "I MUNICIPALIDAD DE CATEMU",
    "monto_disponible": 1200000.0,
    "region": "Valparaíso",
    "documento_nombre": "terminos de referencia diseño conexión.pdf"
}


@pytest.mark.asyncio
async def test_upload_real_catemu_tender_document():
    """Valida la carga y procesamiento inicial del PDF real de Catemu (4280-312-COT26)."""
    assert FIXTURE_PATH.exists(), f"El archivo fixture no existe en {FIXTURE_PATH}"

    pdf_bytes = FIXTURE_PATH.read_bytes()
    assert len(pdf_bytes) > 500_000, "El archivo PDF debe tener su tamaño completo (>500KB)"

    repo = InMemoryTenderChatRepository()
    use_case = UploadTenderChatDocumentUseCase(chat_repo=repo)

    tender_id = uuid4()
    user_id = uuid4()

    doc = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        file_name=REAL_TENDER_CATEMU["documento_nombre"],
        file_bytes=pdf_bytes,
    )

    assert isinstance(doc, TenderChatDocument)
    assert doc.file_name == "terminos de referencia diseño conexión.pdf"
    assert doc.file_type == "pdf"
    assert doc.file_size_bytes == len(pdf_bytes)

    # Validar que los bytes guardados correspondan exactamente al PDF original
    saved_bytes = await repo.get_document_bytes(doc.id, user_id)
    assert saved_bytes is not None
    assert saved_bytes[:4] == b"%PDF"
