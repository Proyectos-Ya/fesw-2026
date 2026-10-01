"""Exportación del documento técnico a Word (HU-20, B6, CA3).

El Word lleva **solo el documento técnico**: es lo único que se sube como
archivo. Nombre, descripción y documentos se copian desde la pestaña del
borrador al formulario de la Compra Ágil.
"""

from io import BytesIO
from uuid import uuid4

import pytest
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn

from app.domain.entities.proposal import (
    DraftContent,
    DraftParagraph,
    DraftSection,
    DraftSource,
    ProposalDraft,
    ProposalWarning,
    TechnicalDocument,
    TechnicalSection,
)
from app.infrastructure.services.docx_proposal_exporter import DocxProposalExporter
from tests.unit.application.test_score_tender_on_demand import crear_licitacion


def _seccion(*textos: str) -> DraftSection:
    return DraftSection(
        paragraphs=[DraftParagraph.from_ai_text(t, sources=[]) for t in textos]
    )


def _tecnico() -> TechnicalDocument:
    return TechnicalDocument(
        sections=[
            TechnicalSection(
                key="antecedentes",
                title="Antecedentes de la empresa",
                paragraphs=[
                    DraftParagraph.from_ai_text(
                        "Operamos en la Región de Aysén hace 8 años.",
                        sources=[
                            DraftSource(id="perfil:region:aysen", label="Región: Aysén")
                        ],
                    )
                ],
            ),
            TechnicalSection(
                key="metodologia",
                title="Metodología",
                paragraphs=[
                    DraftParagraph.from_ai_text("Clases presenciales.", sources=[]),
                    DraftParagraph.from_ai_text(
                        "Evaluación final escrita.", sources=[]
                    ),
                ],
            ),
            TechnicalSection(
                key="equipo",
                title="Equipo de trabajo",
                paragraphs=[
                    DraftParagraph.from_ai_text(
                        "Relator: [[INSERTAR: nombre y experiencia del equipo]].",
                        sources=[],
                    )
                ],
            ),
        ]
    )


def _borrador(tecnico: TechnicalDocument | None = None) -> ProposalDraft:
    borrador = ProposalDraft(supplier_id=uuid4(), tender_id=uuid4(), status="READY")
    borrador.content = DraftContent(
        offer_name=_seccion("Capacitación PAC en Coyhaique"),
        offer_description=_seccion("Descripción comercial de la oferta."),
        required_documents=_seccion("Cotización"),
        technical_document=tecnico if tecnico is not None else _tecnico(),
    )
    borrador.warnings = [
        ProposalWarning(requirement_id="req-1", text="Las bases exigen SEC.")
    ]
    return borrador


def _documento(borrador: ProposalDraft):
    tender = crear_licitacion(borrador.tender_id)
    datos = DocxProposalExporter().to_docx(borrador, tender)
    return Document(BytesIO(datos)), tender


def _sombreado(parrafo) -> bool:
    ppr = parrafo._p.pPr
    return ppr is not None and ppr.find(qn("w:shd")) is not None


def _con_estilo(documento, estilo: str) -> list[str]:
    return [p.text for p in documento.paragraphs if p.style.name == estilo]


def test_titulo_y_una_seccion_por_cada_parte_de_la_plantilla():
    documento, _ = _documento(_borrador())

    assert _con_estilo(documento, "Heading 1") == ["Documento técnico"]
    assert _con_estilo(documento, "Heading 2") == [
        "Antecedentes de la empresa",
        "Metodología",
        "Equipo de trabajo",
    ]
    textos = [p.text for p in documento.paragraphs]
    assert textos.index("Clases presenciales.") > textos.index("Metodología")


def test_indica_la_oferta_la_licitacion_y_que_es_un_borrador():
    documento, tender = _documento(_borrador())

    texto = "\n".join(p.text for p in documento.paragraphs)
    assert "Capacitación PAC en Coyhaique" in texto
    assert tender.code in texto
    assert "Borrador" in texto


def test_no_lleva_lo_que_se_copia_desde_la_pestana_del_borrador():
    documento, _ = _documento(_borrador())

    texto = "\n".join(p.text for p in documento.paragraphs)
    assert "Descripción comercial de la oferta." not in texto
    assert "Cotización" not in texto
    assert "Las bases exigen SEC." not in texto


def test_no_incluye_las_fuentes_internas():
    """Las fuentes son para quien revisa en Chiripa, no para el comprador."""
    documento, _ = _documento(_borrador())

    texto = "\n".join(p.text for p in documento.paragraphs)
    assert "perfil:region:aysen" not in texto
    assert "Región: Aysén" not in texto


def test_los_vacios_van_resaltados_y_con_un_bloque_revisar():
    documento, _ = _documento(_borrador())

    # `documento.paragraphs` arma objetos nuevos en cada acceso: una sola lista.
    parrafos = documento.paragraphs
    indice = next(i for i, p in enumerate(parrafos) if p.text.startswith("Relator:"))
    resaltados = [
        r.text
        for r in parrafos[indice].runs
        if r.font.highlight_color == WD_COLOR_INDEX.YELLOW
    ]
    assert resaltados == [
        "(Por favor, inserte aquí el valor nombre y experiencia del equipo)"
    ]
    revisar = parrafos[indice + 1]
    assert revisar.text == "Revisar: completar nombre y experiencia del equipo."
    assert _sombreado(revisar)


def test_un_parrafo_sin_vacios_no_lleva_bloque_revisar():
    documento, _ = _documento(_borrador())

    textos = [p.text for p in documento.paragraphs]
    siguiente = textos[textos.index("Clases presenciales.") + 1]
    assert siguiente == "Evaluación final escrita."


def test_sin_documento_tecnico_no_hay_word():
    borrador = _borrador()
    borrador.content.technical_document = None  # type: ignore[union-attr]

    with pytest.raises(ValueError):
        DocxProposalExporter().to_docx(borrador, crear_licitacion(borrador.tender_id))
