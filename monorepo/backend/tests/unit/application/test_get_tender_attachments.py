"""Lo que ve quien abre la ficha: la lista oficial de anexos y su estado.

`list_synced_at` nulo no es lo mismo que "sin anexos": significa que la lista
todavía no se sincronizó con Mercado Público, y la interfaz lo dice distinto.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from app.application.use_cases.tender_attachments.get_tender_attachments import (
    GetTenderAttachmentsUseCase,
)
from app.domain.entities.tender_attachment import AttachmentStatus
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository

T1 = datetime(2026, 9, 28, 16, 0)
T2 = datetime(2026, 9, 28, 17, 0)


async def test_una_licitacion_con_lista_devuelve_cada_anexo_como_faltante():
    tender_id = uuid4()
    repo = InMemoryTenderAttachmentRepository({"A": tender_id})
    await repo.sync_official_lists(
        {
            tender_id: [
                DocumentoOficialDTO(mp_document_id=2, nombre="Anexo 1.docx"),
                DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf"),
            ]
        },
        visto_en=T1,
    )

    resultado = await GetTenderAttachmentsUseCase(repo).execute(tender_id)

    assert [v.attachment.name for v in resultado.official] == ["Bases.pdf", "Anexo 1.docx"]
    assert {v.status for v in resultado.official} == {AttachmentStatus.MISSING}
    assert resultado.list_synced_at == T1


async def test_los_retirados_quedan_fuera():
    tender_id = uuid4()
    repo = InMemoryTenderAttachmentRepository({"A": tender_id})
    doc1 = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")
    doc2 = DocumentoOficialDTO(mp_document_id=2, nombre="Anexo 1.docx")
    await repo.sync_official_lists({tender_id: [doc1, doc2]}, visto_en=T1)
    await repo.sync_official_lists({tender_id: [doc1]}, visto_en=T2)

    resultado = await GetTenderAttachmentsUseCase(repo).execute(tender_id)

    assert [v.attachment.mp_document_id for v in resultado.official] == [1]
    assert resultado.list_synced_at == T2


async def test_una_licitacion_existente_sin_sincronizar_no_tiene_lista_ni_fecha():
    tender_id = uuid4()
    repo = InMemoryTenderAttachmentRepository({"A": tender_id})

    resultado = await GetTenderAttachmentsUseCase(repo).execute(tender_id)

    assert resultado.official == []
    assert resultado.list_synced_at is None


async def test_una_licitacion_inexistente_lanza_tender_not_found():
    repo = InMemoryTenderAttachmentRepository({"A": uuid4()})

    with pytest.raises(TenderNotFound):
        await GetTenderAttachmentsUseCase(repo).execute(uuid4())
