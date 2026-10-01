"""Exportación del borrador de postulación a Word con python-docx (HU-20, CA3).

Estructura: título con el nombre de la oferta, un H2 por sección y los
documentos necesarios como viñetas. Lo que hay que revisar antes de enviar va
como bloques "Revisar" sombreados: las advertencias al inicio y, después de cada
párrafo con vacíos, qué datos completar. Los vacíos además quedan resaltados en
el texto.

Las fuentes de cada párrafo **no** se exportan: sirven para revisar en Chiripa,
pero el archivo es el que la empresa termina enviando al comprador.
"""

import re
from io import BytesIO

from docx import Document
from docx.document import Document as DocumentoWord
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph

from app.application.services.proposal_exporter import IProposalExporter
from app.domain.entities.proposal import DraftParagraph, DraftSection, ProposalDraft
from app.domain.entities.tender import Tender

# Lo que `render_placeholders` deja visible en el texto.
_VACIO = re.compile(r"(\(Por favor, inserte aquí el valor [^)]*\))")
_FONDO_REVISAR = "FFF2CC"


def _sombrear(parrafo: Paragraph) -> None:
    """python-docx no expone el sombreado de párrafo: se escribe el w:shd a mano."""
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:val"), "clear")
    sombra.set(qn("w:color"), "auto")
    sombra.set(qn("w:fill"), _FONDO_REVISAR)
    parrafo._p.get_or_add_pPr().append(sombra)


def _revisar(documento: DocumentoWord, texto: str) -> None:
    parrafo = documento.add_paragraph()
    etiqueta = parrafo.add_run("Revisar: ")
    etiqueta.bold = True
    parrafo.add_run(texto)
    _sombrear(parrafo)


def _texto_con_vacios(parrafo: Paragraph, texto: str) -> None:
    for trozo in _VACIO.split(texto):
        if not trozo:
            continue
        run = parrafo.add_run(trozo)
        if _VACIO.fullmatch(trozo):
            run.bold = True
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _parrafo(
    documento: DocumentoWord, parrafo: DraftParagraph, estilo: str | None = None
) -> None:
    salida = documento.add_paragraph(style=estilo)
    _texto_con_vacios(salida, parrafo.text)
    if parrafo.placeholders:
        _revisar(documento, f"completar {', '.join(parrafo.placeholders)}.")


def _seccion(
    documento: DocumentoWord,
    titulo: str,
    seccion: DraftSection,
    estilo: str | None = None,
) -> None:
    documento.add_heading(titulo, level=2)
    for parrafo in seccion.paragraphs:
        _parrafo(documento, parrafo, estilo)


class DocxProposalExporter(IProposalExporter):
    def to_docx(self, draft: ProposalDraft, tender: Tender) -> bytes:
        if draft.content is None:
            raise ValueError("El borrador todavía no está redactado.")
        contenido = draft.content
        documento = Document()

        nombre = " ".join(p.text for p in contenido.offer_name.paragraphs).strip()
        documento.add_heading(nombre or "Oferta", level=1)
        encabezado = documento.add_paragraph(
            f"Borrador de postulación para la Compra Ágil {tender.code} — "
            f"{tender.name}. Revisar antes de enviar."
        )
        for run in encabezado.runs:
            run.italic = True
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)

        for advertencia in draft.warnings:
            _revisar(documento, advertencia.text)

        _seccion(documento, "Descripción de la oferta", contenido.offer_description)
        _seccion(
            documento,
            "Documentos necesarios",
            contenido.required_documents,
            estilo="List Bullet",
        )
        if contenido.technical_document is not None:
            _seccion(documento, "Documento técnico", contenido.technical_document)

        salida = BytesIO()
        documento.save(salida)
        return salida.getvalue()
