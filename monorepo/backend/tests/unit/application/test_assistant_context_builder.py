from datetime import date, datetime
import hashlib
from uuid import uuid4

from app.application.services.assistant_context_builder import (
    MAX_ATTACHMENT_TEXT_CHARS,
    construir_contexto_anexos,
    deduplicar_documentos_chat,
)
from app.domain.entities.attachment_extraction import AttachmentExtractionData, FuenteDeExtraccion
from app.domain.entities.attachment_file import AttachmentTrust, AttachmentVisibility
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.entities.tender_digest import (
    CampoConsolidado,
    CamposConsolidados,
    CitaDeFuente,
    Discrepancia,
    EntregableConsolidado,
    ItemConsolidado,
    RequisitoConsolidado,
    ResumenDeAnexo,
    TenderDigestData,
    TipoDeDiscrepancia,
    ValorDeFecha,
    ValorDePresupuesto,
    ValorDeVisita,
)


from app.domain.entities.attachment_extraction import (
    AttachmentExtractionData,
    Cita,
    FuenteDeExtraccion,
    ResumenGeneral,
)


def _crear_cita(doc: str = "Bases.pdf", pag: str = "1", texto: str = "Cita de prueba") -> CitaDeFuente:
    return CitaDeFuente(
        documento=doc,
        pagina_u_hoja=pag,
        cita=texto,
        verificada=True,
        anexo_id=uuid4(),
        archivo_id=uuid4(),
    )


def _crear_fuente(doc: str = "Bases.pdf", sha256: str = "abc123sha") -> FuenteDeExtraccion:
    ext_data = AttachmentExtractionData(
        resumen_general=ResumenGeneral(
            texto="Resumen",
            citas=[Cita(documento=doc, cita="Resumen general", verificada=True)],
        )
    )
    return FuenteDeExtraccion(
        extraction_id=uuid4(),
        attachment_file_id=uuid4(),
        tender_attachment_id=uuid4(),
        mp_document_id=1001,
        documento=doc,
        sha256=sha256,
        visibility=AttachmentVisibility.SHARED,
        trust=AttachmentTrust.CORROBORATED,
        workspace_id=None,
        data=ext_data,
        citas_total=5,
        citas_verificadas=5,
        texto_disponible=True,
        model="gemini-3.1-flash-lite",
        prompt_version="anexos-v1",
        created_at=datetime(2026, 10, 4, 12, 0),
    )


def test_formatear_contexto_con_digest_vacio():
    texto = construir_contexto_anexos(None, [], [])
    assert "=== ANTECEDENTES Y BASES OFICIALES DE LA LICITACIÓN" in texto
    assert "No hay documentos o bases oficiales procesadas" in texto


def test_formatear_contexto_con_digest_completo():
    cita = _crear_cita("Bases.pdf", "3", "Presupuesto $15.000.000")
    campos = CamposConsolidados(
        presupuesto=CampoConsolidado(
            valor=ValorDePresupuesto(monto_clp=15000000.0, incluye_iva=True, monto_texto="$15.000.000 CLP (IVA incluido)"),
            citas=[cita],
        ),
        fecha_publicacion=CampoConsolidado(
            valor=ValorDeFecha(fecha=date(2026, 10, 1), hora="10:00"),
            citas=[_crear_cita("Bases.pdf", "1", "Publicado 01-10")],
        ),
        fecha_cierre_primer_llamado=CampoConsolidado(
            valor=ValorDeFecha(fecha=date(2026, 10, 15), hora="15:00"),
            citas=[_crear_cita("Bases.pdf", "2", "Cierre 15-10")],
        ),
        visita_tecnica=CampoConsolidado(
            valor=ValorDeVisita(obligatoria=True, fecha=date(2026, 10, 8), hora="10:00", lugar="Av. Providencia 1234"),
            citas=[_crear_cita("Bases.pdf", "4", "Visita técnica")],
        ),
    )
    requisitos = [
        RequisitoConsolidado(
            descripcion="Certificación ISO 9001",
            tipo="técnico",
            obligatorio=True,
            citas=[_crear_cita("Bases.pdf", "5", "Exige ISO 9001")],
        )
    ]
    items = [
        ItemConsolidado(
            descripcion="Bombas centrífugas",
            cantidad=4.0,
            unidad="unidades",
            citas=[cita],
        )
    ]
    entregables = [
        EntregableConsolidado(
            descripcion="Informe técnico final",
            plazo="10 días",
            citas=[cita],
        )
    ]
    digest = TenderDigestData.vacio()
    digest.campos = campos
    digest.requisitos = requisitos
    digest.items = items
    digest.entregables = entregables

    fuente = _crear_fuente("Bases.pdf")
    texto = construir_contexto_anexos(digest, [fuente], [])

    assert "Presupuesto oficial estimado: $15.000.000 CLP (IVA incluido)" in texto
    assert "Fecha de cierre (1.er llamado): 2026-10-15 15:00" in texto
    assert "Visita a terreno: Obligatoria, Fecha: 2026-10-08 10:00, Lugar: Av. Providencia 1234" in texto
    assert "[Obligatorio] (técnico): Certificación ISO 9001" in texto
    assert "* Bombas centrífugas (Cantidad: 4.0 unidades)" in texto
    assert "* Informe técnico final [Plazo: 10 días]" in texto


def test_discrepancias_incluidas_en_contexto():
    digest = TenderDigestData.vacio()
    digest.discrepancias = [
        Discrepancia(
            tipo=TipoDeDiscrepancia.ANEXO_VS_API,
            campo="fecha_cierre_primer_llamado",
            tema="Plazo de cierre",
            descripcion="La API indica 30 días pero Bases indica 45 días",
            valores_anexos=["45 días"],
            fuentes=[_crear_cita("Bases.pdf", "2", "45 días")],
        )
    ]
    texto = construir_contexto_anexos(digest, [_crear_fuente()], [])
    assert "--- CONTRADICCIONES O DISCREPANCIAS DETECTADAS ---" in texto
    assert "[Plazo de cierre] La API indica 30 días pero Bases indica 45 días" in texto


def test_deduplicacion_chat_legacy_contra_panel():
    contenido_comun = b"mismo contenido de bases"
    sha_comun = hashlib.sha256(contenido_comun).hexdigest()

    doc_dup = TenderChatDocument(
        id=uuid4(),
        tender_id=uuid4(),
        user_id=uuid4(),
        file_name="bases.pdf",
        file_type="pdf",
        file_size_bytes=len(contenido_comun),
        storage_path="/tmp/bases.pdf",
        created_at=datetime(2026, 6, 1),
    )
    doc_unico = TenderChatDocument(
        id=uuid4(),
        tender_id=uuid4(),
        user_id=uuid4(),
        file_name="aclaracion_privada.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="/tmp/aclaracion.pdf",
        created_at=datetime(2026, 6, 1),
    )

    fuente_panel = _crear_fuente("Bases.pdf", sha256=sha_comun)
    bytes_by_id = {
        doc_dup.id: contenido_comun,
        doc_unico.id: b"contenido unico diferente",
    }

    unicos = deduplicar_documentos_chat([doc_dup, doc_unico], bytes_by_id, [fuente_panel])
    assert len(unicos) == 1
    assert unicos[0].id == doc_unico.id


def test_control_de_longitud_maxima_trunca_resumenes():
    digest = TenderDigestData.vacio()
    # Agregar resumenes gigantescos
    texto_gigante = "A" * (MAX_ATTACHMENT_TEXT_CHARS + 50_000)
    digest.resumenes = [
        ResumenDeAnexo(
            anexo_id=uuid4(),
            documento="Bases.pdf",
            texto=texto_gigante,
            citas=[],
        )
    ]
    texto = construir_contexto_anexos(digest, [_crear_fuente()], [])
    assert len(texto) <= MAX_ATTACHMENT_TEXT_CHARS + 200
    assert "[... texto de anexos recortado por límite de contexto ...]" in texto
