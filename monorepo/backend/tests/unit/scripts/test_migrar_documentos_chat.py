"""Tests unitarios para el script de migración de documentos del chat histórico (Plan 233, Decisión 5)."""

from datetime import datetime
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.services.attachment_storage import IAttachmentStorage
from app.domain.services.attachment_names import normalizar_nombre_anexo
from app.infrastructure.repositories.attachment_file_model import AttachmentFileModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_attachment_model import TenderAttachmentModel
from app.infrastructure.repositories.tender_chat_model import TenderChatDocumentModel
from scripts.migrar_documentos_chat_a_anexos import migrar_documentos_chat_a_anexos


class MockQueryResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


def _armar_mock_session(docs, supplier=None, anexo=None, existing_file=None):
    session = MagicMock(spec=AsyncSession)
    added = []
    session.add = MagicMock(side_effect=lambda x: added.append(x))
    session.commit = AsyncMock()

    async def fake_exec(statement):
        tables = [t.name for t in statement.get_final_froms()]
        if "tender_chat_documents" in tables:
            return MockQueryResult(docs)
        if "supplier" in tables:
            return MockQueryResult([supplier] if supplier else [])
        if "supplier_members" in tables:
            return MockQueryResult([])
        if "tender_attachment" in tables:
            return MockQueryResult([anexo] if anexo else [])
        if "attachment_file" in tables:
            return MockQueryResult([existing_file] if existing_file else [])
        return MockQueryResult([])

    session.exec = AsyncMock(side_effect=fake_exec)
    session._added = added
    return session


@pytest.fixture
def archivo_fisico(tmp_path: Path):
    contenido = b"%PDF-1.4 documento oficial de prueba con contenido relevante"
    archivo = tmp_path / "Bases_Licitacion.pdf"
    archivo.write_bytes(contenido)
    sha256 = hashlib.sha256(contenido).hexdigest()
    return archivo, contenido, sha256


@pytest.mark.asyncio
async def test_dry_run_no_escribe_en_bd_ni_storage(archivo_fisico):
    archivo, contenido, sha256 = archivo_fisico
    user_id = uuid4()
    supplier_id = uuid4()
    tender_id = uuid4()

    doc = TenderChatDocumentModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        file_name="Bases Licitacion.pdf",
        file_type="pdf",
        file_size_bytes=len(contenido),
        storage_path=str(archivo),
        created_at=datetime(2026, 9, 15),
    )

    supplier = SupplierModel(
        id=supplier_id,
        user_id=user_id,
        rut="76.192.083-9",
        legal_name="Empresa A SpA",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    anexo = TenderAttachmentModel(
        id=uuid4(),
        tender_id=tender_id,
        mp_document_id=1001,
        name="Bases Licitacion.pdf",
        name_normalized=normalizar_nombre_anexo("Bases Licitacion.pdf"),
        ext="pdf",
        first_seen_at=datetime(2026, 9, 1),
        last_seen_at=datetime(2026, 9, 1),
    )

    session = _armar_mock_session([doc], supplier=supplier, anexo=anexo)
    storage = MagicMock(spec=IAttachmentStorage)
    storage.put_bytes = AsyncMock()

    job_repo = MagicMock(spec=IAttachmentProcessingJobRepository)
    job_repo.enqueue_extract = AsyncMock()

    reporte = await migrar_documentos_chat_a_anexos(
        session=session,
        storage=storage,
        job_repo=job_repo,
        dry_run=True,
    )

    assert reporte.dry_run is True
    assert reporte.total_revisados == 1
    assert reporte.migrados == 1
    assert storage.put_bytes.call_count == 0
    assert len(session._added) == 0
    assert session.commit.call_count == 0
    assert job_repo.enqueue_extract.call_count == 0


@pytest.mark.asyncio
async def test_archivo_inexistente_en_disco_se_reporta_como_omitido(tmp_path: Path):
    user_id = uuid4()
    supplier_id = uuid4()
    tender_id = uuid4()

    doc = TenderChatDocumentModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        file_name="Archivo_Fantasma.pdf",
        file_type="pdf",
        file_size_bytes=500,
        storage_path=str(tmp_path / "no_existe_en_disco.pdf"),
        created_at=datetime(2026, 9, 15),
    )

    supplier = SupplierModel(
        id=supplier_id,
        user_id=user_id,
        rut="76.192.083-9",
        legal_name="Empresa A SpA",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    session = _armar_mock_session([doc], supplier=supplier)
    storage = MagicMock(spec=IAttachmentStorage)
    storage.put_bytes = AsyncMock()

    reporte = await migrar_documentos_chat_a_anexos(
        session=session,
        storage=storage,
        dry_run=False,
    )

    assert reporte.total_revisados == 1
    assert reporte.omitidos_sin_archivo == 1
    assert reporte.migrados == 0
    assert storage.put_bytes.call_count == 0
    assert len(session._added) == 0


@pytest.mark.asyncio
async def test_migracion_exitosa_crea_attachment_file_y_encola_extraccion(archivo_fisico):
    archivo, contenido, sha256 = archivo_fisico
    user_id = uuid4()
    supplier_id = uuid4()
    tender_id = uuid4()

    doc = TenderChatDocumentModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        file_name="Bases Licitacion.pdf",
        file_type="pdf",
        file_size_bytes=len(contenido),
        storage_path=str(archivo),
        created_at=datetime(2026, 9, 15),
    )

    supplier = SupplierModel(
        id=supplier_id,
        user_id=user_id,
        rut="76.192.083-9",
        legal_name="Empresa A SpA",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    anexo = TenderAttachmentModel(
        id=uuid4(),
        tender_id=tender_id,
        mp_document_id=1001,
        name="Bases Licitacion.pdf",
        name_normalized=normalizar_nombre_anexo("Bases Licitacion.pdf"),
        ext="pdf",
        first_seen_at=datetime(2026, 9, 1),
        last_seen_at=datetime(2026, 9, 1),
    )

    session = _armar_mock_session([doc], supplier=supplier, anexo=anexo)
    storage = MagicMock(spec=IAttachmentStorage)
    storage.put_bytes = AsyncMock()

    job_repo = MagicMock(spec=IAttachmentProcessingJobRepository)
    job_repo.enqueue_extract = AsyncMock(return_value=True)

    reporte = await migrar_documentos_chat_a_anexos(
        session=session,
        storage=storage,
        job_repo=job_repo,
        dry_run=False,
    )

    assert reporte.migrados == 1
    assert storage.put_bytes.call_count == 1
    storage_key_expected = f"private/{supplier_id}/{sha256}.pdf"
    storage.put_bytes.assert_called_once_with(storage_key_expected, contenido)

    assert len(session._added) == 1
    archivo_guardado: AttachmentFileModel = session._added[0]
    assert archivo_guardado.tender_attachment_id == anexo.id
    assert archivo_guardado.tender_id == tender_id
    assert archivo_guardado.sha256 == sha256
    assert archivo_guardado.size_bytes == len(contenido)
    assert archivo_guardado.storage_key == storage_key_expected
    assert archivo_guardado.source == "legacy_chat"
    assert archivo_guardado.uploader_user_id == user_id
    assert archivo_guardado.workspace_id == supplier_id
    assert archivo_guardado.visibility == "private"
    assert archivo_guardado.trust == "pending"
    assert archivo_guardado.status == "stored"

    assert session.commit.call_count == 1
    assert job_repo.enqueue_extract.call_count == 1
    job_args = job_repo.enqueue_extract.call_args[1]
    assert job_args["attachment_file_id"] == archivo_guardado.id
    assert job_args["tender_id"] == tender_id


@pytest.mark.asyncio
async def test_idempotencia_segunda_corrida_no_duplica_archivos(archivo_fisico):
    archivo, contenido, sha256 = archivo_fisico
    user_id = uuid4()
    supplier_id = uuid4()
    tender_id = uuid4()

    doc = TenderChatDocumentModel(
        id=uuid4(),
        tender_id=tender_id,
        user_id=user_id,
        file_name="Bases Licitacion.pdf",
        file_type="pdf",
        file_size_bytes=len(contenido),
        storage_path=str(archivo),
        created_at=datetime(2026, 9, 15),
    )

    supplier = SupplierModel(
        id=supplier_id,
        user_id=user_id,
        rut="76.192.083-9",
        legal_name="Empresa A SpA",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    anexo = TenderAttachmentModel(
        id=uuid4(),
        tender_id=tender_id,
        mp_document_id=1001,
        name="Bases Licitacion.pdf",
        name_normalized=normalizar_nombre_anexo("Bases Licitacion.pdf"),
        ext="pdf",
        first_seen_at=datetime(2026, 9, 1),
        last_seen_at=datetime(2026, 9, 1),
    )

    ya_existente = AttachmentFileModel(
        id=uuid4(),
        tender_attachment_id=anexo.id,
        tender_id=tender_id,
        sha256=sha256,
        size_bytes=len(contenido),
        storage_key=f"private/{supplier_id}/{sha256}.pdf",
        source="legacy_chat",
        uploader_user_id=user_id,
        workspace_id=supplier_id,
        visibility="private",
        trust="pending",
        status="stored",
        created_at=datetime(2026, 9, 15),
    )

    # La sesión ya encuentra un archivo existente
    session = _armar_mock_session([doc], supplier=supplier, anexo=anexo, existing_file=ya_existente)
    storage = MagicMock(spec=IAttachmentStorage)
    storage.put_bytes = AsyncMock()

    job_repo = MagicMock(spec=IAttachmentProcessingJobRepository)
    job_repo.enqueue_extract = AsyncMock()

    reporte = await migrar_documentos_chat_a_anexos(
        session=session,
        storage=storage,
        job_repo=job_repo,
        dry_run=False,
    )

    assert reporte.ya_migrados == 1
    assert reporte.migrados == 0
    assert storage.put_bytes.call_count == 0
    assert len(session._added) == 0
    assert job_repo.enqueue_extract.call_count == 0
