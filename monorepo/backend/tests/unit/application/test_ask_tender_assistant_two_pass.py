from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest

from app.application.repositories.attachment_extraction_repository import IAttachmentExtractionRepository
from app.application.repositories.attachment_file_repository import IAttachmentFileRepository
from app.application.repositories.gemini_usage_repository import IGeminiUsageRepository
from app.application.repositories.tender_digest_repository import ITenderDigestRepository
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.tender_assistant_ai_service import (
    AIResponseDTO,
    DocumentContextDTO,
    ITenderAssistantAIService,
)
from app.application.use_cases.ask_tender_assistant_use_case import AskTenderAssistantUseCase
from app.domain.entities.attachment_extraction import (
    AttachmentExtractionData,
    Cita,
    FuenteDeExtraccion,
    ResumenGeneral,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender_chat import (
    Citation,
    TenderChatMessage,
)
from app.domain.entities.tender_digest import (
    CampoConsolidado,
    CamposConsolidados,
    CitaDeFuente,
    RequisitoConsolidado,
    TenderDigest,
    TenderDigestData,
    ValorDePresupuesto,
)
from tests.unit.application.fakes import (
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
)


def _crear_fuente(doc: str, archivo_id, storage_key: str, vis: AttachmentVisibility, ws_id=None) -> FuenteDeExtraccion:
    ext_data = AttachmentExtractionData(
        resumen_general=ResumenGeneral(
            texto=f"Resumen de {doc}",
            citas=[Cita(documento=doc, cita="Cita", verificada=True)],
        )
    )
    return FuenteDeExtraccion(
        extraction_id=uuid4(),
        attachment_file_id=archivo_id,
        tender_attachment_id=uuid4(),
        mp_document_id=101,
        documento=doc,
        sha256="hash123",
        visibility=vis,
        trust=AttachmentTrust.CORROBORATED,
        workspace_id=ws_id,
        data=ext_data,
        citas_total=1,
        citas_verificadas=1,
        texto_disponible=True,
        model="gemini-3.1-flash-lite",
        prompt_version="anexos-v1",
        created_at=datetime(2026, 10, 4),
    )


@pytest.mark.asyncio
async def test_pase_uno_exitoso_no_descarga_bytes_de_archivos():
    user_id = uuid4()
    tender_id = uuid4()
    archivo_id = uuid4()

    chat_repo = InMemoryTenderChatRepository()
    ai_service = MagicMock(spec=ITenderAssistantAIService)
    ai_service.generate_response = AsyncMock(
        return_value=AIResponseDTO(
            answer="Respuesta del pase 1",
            citations=[Citation(document_name="Bases.pdf", page_or_sheet="1", quote="Cita")],
            has_sufficient_info=True,
        )
    )

    digest_repo = MagicMock(spec=ITenderDigestRepository)
    digest_data = TenderDigestData.vacio()
    digest_entity = TenderDigest(
        id=uuid4(),
        tender_id=tender_id,
        workspace_id=None,
        version=1,
        extraction_set_hash="hash",
        is_current=True,
        source_count=1,
        data=digest_data,
        api_snapshot={},
        created_at=datetime(2026, 10, 4),
    )
    digest_repo.get_current = AsyncMock(return_value=digest_entity)

    fuente = _crear_fuente("Bases.pdf", archivo_id, "shared/bases.pdf", AttachmentVisibility.SHARED)
    extraction_repo = MagicMock(spec=IAttachmentExtractionRepository)
    extraction_repo.list_sources = AsyncMock(return_value=[fuente])

    storage = MagicMock(spec=IAttachmentStorage)
    storage.get_bytes = AsyncMock()

    usage_repo = MagicMock(spec=IGeminiUsageRepository)

    use_case = AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
        attachment_storage=storage,
        usage_repo=usage_repo,
    )

    result = await use_case.execute(tender_id=tender_id, user_id=user_id, question="¿Cuál es el plazo?")

    assert result.role == "assistant"
    assert result.content == "Respuesta del pase 1"
    assert result.has_sufficient_info is True
    assert storage.get_bytes.call_count == 0
    assert ai_service.generate_response.call_count == 1
    # Verifica que en pase 1 se enviaron zero bytes crudos
    call_args = ai_service.generate_response.call_args[1]
    assert call_args["pass_number"] == 1
    docs_sent = call_args["documents"]
    assert len(docs_sent) == 1
    assert docs_sent[0].file_bytes == b""
    assert docs_sent[0].text is not None


@pytest.mark.asyncio
async def test_pase_uno_insuficiente_dispara_segunda_pasada_con_bytes():
    user_id = uuid4()
    tender_id = uuid4()
    archivo_id = uuid4()

    chat_repo = InMemoryTenderChatRepository()
    ai_service = MagicMock(spec=ITenderAssistantAIService)
    ai_service.generate_response = AsyncMock(
        side_effect=[
            AIResponseDTO(
                answer="No tengo información suficiente en el resumen.",
                citations=[],
                has_sufficient_info=False,
            ),
            AIResponseDTO(
                answer="Respuesta detallada desde inspección profunda.",
                citations=[Citation(document_name="Bases.pdf", page_or_sheet="12", quote="Cita profunda")],
                has_sufficient_info=True,
            ),
        ]
    )

    digest_repo = MagicMock(spec=ITenderDigestRepository)
    digest_repo.get_current = AsyncMock(return_value=None)

    fuente = _crear_fuente("Bases.pdf", archivo_id, "shared/bases.pdf", AttachmentVisibility.SHARED)
    extraction_repo = MagicMock(spec=IAttachmentExtractionRepository)
    extraction_repo.list_sources = AsyncMock(return_value=[fuente])

    file_repo = MagicMock(spec=IAttachmentFileRepository)
    af = AttachmentFile(
        id=archivo_id,
        tender_attachment_id=uuid4(),
        tender_id=tender_id,
        sha256="hash123",
        size_bytes=1000,
        storage_key="shared/bases.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        status=AttachmentFileStatus.STORED,
        created_at=datetime(2026, 10, 4),
    )
    file_repo.get = AsyncMock(return_value=af)

    raw_pdf_bytes = b"%PDF-1.4 mock content"
    storage = MagicMock(spec=IAttachmentStorage)
    storage.get_bytes = AsyncMock(return_value=raw_pdf_bytes)

    usage_repo = MagicMock(spec=IGeminiUsageRepository)
    usage_repo.try_reserve_call = AsyncMock(return_value=True)

    use_case = AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
        attachment_file_repo=file_repo,
        attachment_storage=storage,
        usage_repo=usage_repo,
        daily_budget=100,
    )

    result = await use_case.execute(tender_id=tender_id, user_id=user_id, question="¿Exige boleta?")

    assert result.content == "Respuesta detallada desde inspección profunda."
    assert result.has_sufficient_info is True
    assert ai_service.generate_response.call_count == 2
    assert storage.get_bytes.call_count == 1
    assert usage_repo.try_reserve_call.call_count == 1

    # Verificamos que el segundo llamado recibió file_bytes
    p2_call = ai_service.generate_response.call_args_list[1][1]
    assert p2_call["pass_number"] == 2
    docs_p2 = p2_call["documents"]
    assert len(docs_p2) == 1
    assert docs_p2[0].file_bytes == raw_pdf_bytes


@pytest.mark.asyncio
async def test_segunda_pasada_bloqueada_si_tope_diario_gemini_agotado():
    user_id = uuid4()
    tender_id = uuid4()
    archivo_id = uuid4()

    chat_repo = InMemoryTenderChatRepository()
    ai_service = MagicMock(spec=ITenderAssistantAIService)
    ai_service.generate_response = AsyncMock(
        return_value=AIResponseDTO(
            answer="No tengo información suficiente en el resumen.",
            citations=[],
            has_sufficient_info=False,
        )
    )

    fuente = _crear_fuente("Bases.pdf", archivo_id, "shared/bases.pdf", AttachmentVisibility.SHARED)
    extraction_repo = MagicMock(spec=IAttachmentExtractionRepository)
    extraction_repo.list_sources = AsyncMock(return_value=[fuente])

    storage = MagicMock(spec=IAttachmentStorage)
    storage.get_bytes = AsyncMock()

    usage_repo = MagicMock(spec=IGeminiUsageRepository)
    usage_repo.try_reserve_call = AsyncMock(return_value=False)  # Cupo agotado!

    use_case = AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        extraction_repo=extraction_repo,
        attachment_storage=storage,
        usage_repo=usage_repo,
        daily_budget=100,
    )

    result = await use_case.execute(tender_id=tender_id, user_id=user_id, question="¿Exige boleta?")

    assert result.content == "No tengo información suficiente en el resumen."
    assert storage.get_bytes.call_count == 0
    assert ai_service.generate_response.call_count == 1  # No hubo segunda pasada
    assert len(result.warnings) > 0
    assert "límite diario de consultas" in result.warnings[0]


@pytest.mark.asyncio
async def test_privacidad_empresa_b_no_ve_anexos_privados_de_empresa_a():
    empresa_a_id = uuid4()
    empresa_b_id = uuid4()
    user_b_id = uuid4()
    tender_id = uuid4()

    supplier_b = Supplier(
        id=empresa_b_id,
        user_id=user_b_id,
        legal_name="Empresa B SpA",
        rut="76.192.083-9",
    )
    supplier_repo = MagicMock()
    supplier_repo.find_by_user = AsyncMock(return_value=supplier_b)
    supplier_repo.get_by_id = AsyncMock(return_value=supplier_b)
    supplier_repo.get_by_user_id = AsyncMock(return_value=supplier_b)

    chat_repo = InMemoryTenderChatRepository()
    ai_service = MagicMock(spec=ITenderAssistantAIService)
    ai_service.generate_response = AsyncMock(
        return_value=AIResponseDTO(answer="OK", has_sufficient_info=True)
    )

    # El repositorio de extracciones filtra por workspace_id. Si le piden para empresa B,
    # solo devuelve S1 (shared). P1 de empresa A no debe ser devuelto.
    fuente_s1 = _crear_fuente("Bases_Compartidas.pdf", uuid4(), "shared/s1.pdf", AttachmentVisibility.SHARED)
    extraction_repo = MagicMock(spec=IAttachmentExtractionRepository)
    extraction_repo.list_sources = AsyncMock(return_value=[fuente_s1])

    digest_repo = MagicMock(spec=ITenderDigestRepository)
    digest_repo.get_current = AsyncMock(return_value=None)

    use_case = AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        supplier_repo=supplier_repo,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
    )

    await use_case.execute(
        tender_id=tender_id,
        user_id=user_b_id,
        question="¿Qué documentos hay?",
    )

    # Verificamos que list_sources fue llamado con workspace_id = empresa_b_id
    extraction_repo.list_sources.assert_called_once_with(
        tender_id=tender_id,
        workspace_id=empresa_b_id,
        prompt_version="anexos-v1",
    )
    digest_repo.get_current.assert_any_call(
        tender_id, empresa_b_id
    )

    call_args = ai_service.generate_response.call_args[1]
    prompt_text = call_args["documents"][0].text
    assert "Bases_Compartidas.pdf" in prompt_text
    assert "Empresa A" not in prompt_text
    assert "privado_empresa_a" not in prompt_text


@pytest.mark.asyncio
async def test_digest_fallback_a_compartido_cuando_no_hay_privado():
    user_id = uuid4()
    empresa_id = uuid4()
    tender_id = uuid4()

    supplier = Supplier(
        id=empresa_id,
        user_id=user_id,
        legal_name="Mi Empresa SpA",
        rut="76.192.083-9",
    )
    supplier_repo = MagicMock()
    supplier_repo.get_by_user_id = AsyncMock(return_value=supplier)

    chat_repo = InMemoryTenderChatRepository()
    ai_service = MagicMock(spec=ITenderAssistantAIService)
    ai_service.generate_response = AsyncMock(
        return_value=AIResponseDTO(answer="OK con bases compartidas", has_sufficient_info=True)
    )

    # Digest compartido con requisitos
    digest_compartido_data = TenderDigestData.vacio()
    digest_compartido_data.requisitos = [
        RequisitoConsolidado(
            descripcion="Garantía de seriedad de 5%",
            tipo="económico",
            obligatorio=True,
            citas=[],
        )
    ]
    digest_compartido = TenderDigest(
        id=uuid4(),
        tender_id=tender_id,
        workspace_id=None,
        version=1,
        extraction_set_hash="hash_shared",
        is_current=True,
        source_count=1,
        data=digest_compartido_data,
        api_snapshot={},
        created_at=datetime(2026, 10, 5),
    )

    digest_repo = MagicMock(spec=ITenderDigestRepository)
    # get_current para empresa_id devuelve None, pero para None devuelve el compartido
    digest_repo.get_current = AsyncMock(
        side_effect=lambda t_id, ws_id: digest_compartido if ws_id is None else None
    )

    fuente = _crear_fuente("Bases_Oficiales.pdf", uuid4(), "shared/bases.pdf", AttachmentVisibility.SHARED)
    extraction_repo = MagicMock(spec=IAttachmentExtractionRepository)
    extraction_repo.list_sources = AsyncMock(return_value=[fuente])

    use_case = AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        supplier_repo=supplier_repo,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
    )

    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        question="¿Exige garantía?",
    )

    assert result.content == "OK con bases compartidas"
    call_args = ai_service.generate_response.call_args[1]
    prompt_text = call_args["documents"][0].text
    assert "Garantía de seriedad de 5%" in prompt_text
    assert "Bases_Oficiales.pdf" in prompt_text


@pytest.mark.asyncio
async def test_consolidacion_en_vivo_cuando_digest_no_ha_sido_persistido():
    from app.domain.entities.tender import Tender
    user_id = uuid4()
    tender_id = uuid4()

    chat_repo = InMemoryTenderChatRepository()
    ai_service = MagicMock(spec=ITenderAssistantAIService)
    ai_service.generate_response = AsyncMock(
        return_value=AIResponseDTO(answer="OK consolidado en caliente", has_sufficient_info=True)
    )

    digest_repo = MagicMock(spec=ITenderDigestRepository)
    digest_repo.get_current = AsyncMock(return_value=None)

    fuente = _crear_fuente("Especificaciones.pdf", uuid4(), "shared/esp.pdf", AttachmentVisibility.SHARED)
    extraction_repo = MagicMock(spec=IAttachmentExtractionRepository)
    extraction_repo.list_sources = AsyncMock(return_value=[fuente])

    tender_repo = InMemoryTenderRepository()
    now = datetime(2026, 10, 1, 10, 0)
    tender = Tender(
        id=tender_id,
        code="5555-22-L1",
        name="Licitación con fuentes",
        status_id=1,
        status_code="publicada",
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="60.504.000-9",
        buyer_unit="Depto Adquisiciones",
        items=[],
    )
    tender_repo.tenders[tender_id] = tender

    use_case = AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        tender_repo=tender_repo,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
    )

    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        question="¿Qué especificaciones hay?",
    )

    assert result.content == "OK consolidado en caliente"
    call_args = ai_service.generate_response.call_args[1]
    prompt_text = call_args["documents"][0].text
    assert "Especificaciones.pdf" in prompt_text
    assert "Resumen de Especificaciones.pdf" in prompt_text


@pytest.mark.asyncio
async def test_archivos_visibles_sin_extraccion_se_descargan_en_pase_dos():
    from app.application.repositories.tender_attachment_repository import ITenderAttachmentRepository
    from app.domain.entities.tender_attachment import OfficialAttachment

    user_id = uuid4()
    tender_id = uuid4()
    archivo_id = uuid4()
    att_id = uuid4()

    chat_repo = InMemoryTenderChatRepository()
    ai_service = MagicMock(spec=ITenderAssistantAIService)
    ai_service.generate_response = AsyncMock(
        side_effect=[
            AIResponseDTO(answer="Insuficiente", has_sufficient_info=False),
            AIResponseDTO(answer="Respuesta con PDF no extraído", has_sufficient_info=True),
        ]
    )

    # extraction_repo no tiene fuentes extraídas todavía
    extraction_repo = MagicMock(spec=IAttachmentExtractionRepository)
    extraction_repo.list_sources = AsyncMock(return_value=[])

    digest_repo = MagicMock(spec=ITenderDigestRepository)
    digest_repo.get_current = AsyncMock(return_value=None)

    # Pero en attachment_file hay un archivo STORED
    af = AttachmentFile(
        id=archivo_id,
        tender_attachment_id=att_id,
        tender_id=tender_id,
        sha256="sha_unextracted",
        size_bytes=2048,
        storage_key="attachments/plano.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=None,
        workspace_id=None,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        status=AttachmentFileStatus.STORED,
        created_at=datetime(2026, 10, 5),
    )
    file_repo = MagicMock(spec=IAttachmentFileRepository)
    file_repo.list_visible_for_tender = AsyncMock(return_value=[af])

    att_repo = MagicMock(spec=ITenderAttachmentRepository)
    att = OfficialAttachment(
        id=att_id,
        tender_id=tender_id,
        mp_document_id=505,
        name="Plano_Arquitectura.pdf",
        name_normalized="plano_arquitectura.pdf",
        ext="pdf",
        first_seen_at=datetime(2026, 10, 1),
        last_seen_at=datetime(2026, 10, 1),
    )
    att_repo.list_for_tender = AsyncMock(return_value=[att])

    raw_pdf = b"%PDF-1.4 plano arquitectonico"
    storage = MagicMock(spec=IAttachmentStorage)
    storage.get_bytes = AsyncMock(return_value=raw_pdf)

    use_case = AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        digest_repo=digest_repo,
        extraction_repo=extraction_repo,
        attachment_file_repo=file_repo,
        tender_attachment_repo=att_repo,
        attachment_storage=storage,
    )

    result = await use_case.execute(
        tender_id=tender_id,
        user_id=user_id,
        question="¿Qué medidas tiene el plano?",
    )

    assert result.content == "Respuesta con PDF no extraído"
    assert storage.get_bytes.call_count == 1
    # En pase 2 se enviaron los bytes del archivo
    p2_call = ai_service.generate_response.call_args_list[1][1]
    docs_p2 = p2_call["documents"]
    assert any(d.document_name == "Plano_Arquitectura.pdf" and d.file_bytes == raw_pdf for d in docs_p2)
