"""PDF del detalle de una licitación, con ReportLab (HdU 19, criterio 3)."""

from decimal import Decimal
from functools import partial
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.application.use_cases.exports.export_snapshot import ExportSnapshot
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.quotation import Quotation
from app.infrastructure.services.exports.formatting import (
    NO_INFORMADO,
    format_chile,
    format_money,
)

_PRIMARIO = colors.HexColor("#0F766E")
_PRIMARIO_SUAVE = colors.HexColor("#F0FDFA")
_TEXTO = colors.HexColor("#1F2937")
_TENUE = colors.HexColor("#6B7280")
_BORDE = colors.HexColor("#E5E7EB")
_RECOMENDACION = {
    "Postular": colors.HexColor("#15803D"),
    "Evaluar con cautela": colors.HexColor("#B45309"),
    "No recomendado": colors.HexColor("#B91C1C"),
}
_MARGEN = 18 * mm
_ANCHO_UTIL = A4[0] - 2 * _MARGEN

_base = getSampleStyleSheet()
_ESTILOS = {
    "marca": ParagraphStyle("marca", parent=_base["Normal"], fontSize=8, textColor=_TENUE),
    "titulo": ParagraphStyle(
        "titulo", parent=_base["Title"], fontSize=18, leading=22, alignment=0, textColor=_PRIMARIO
    ),
    "subtitulo": ParagraphStyle("subtitulo", parent=_base["Normal"], fontSize=9, textColor=_TENUE),
    "seccion": ParagraphStyle(
        "seccion",
        parent=_base["Heading2"],
        fontSize=12,
        textColor=_PRIMARIO,
        spaceBefore=10,
        spaceAfter=6,
    ),
    "texto": ParagraphStyle("texto", parent=_base["Normal"], fontSize=9.5, leading=13, textColor=_TEXTO),
    "etiqueta": ParagraphStyle(
        "etiqueta", parent=_base["Normal"], fontSize=8.5, textColor=_TENUE, fontName="Helvetica-Bold"
    ),
    "celda": ParagraphStyle("celda", parent=_base["Normal"], fontSize=8.5, leading=11, textColor=_TEXTO),
    "celda_derecha": ParagraphStyle(
        "celda_derecha", parent=_base["Normal"], fontSize=8.5, leading=11, alignment=TA_RIGHT
    ),
    "puntaje": ParagraphStyle(
        "puntaje", parent=_base["Normal"], fontSize=22, leading=26, fontName="Helvetica-Bold"
    ),
}


def _p(texto: str | None, estilo: str = "texto") -> Paragraph:
    """Párrafo con el texto escapado.

    ReportLab interpreta etiquetas dentro de los párrafos: un "<" de las bases o
    de la justificación rompería la generación o se tomaría como formato.
    """
    valor = escape(texto) if texto else NO_INFORMADO
    return Paragraph(valor.replace("\n", "<br/>"), _ESTILOS[estilo])


def _p_marcado(marcado: str) -> Paragraph:
    """Para marcado propio y ya escapado; nunca con texto de datos."""
    return Paragraph(marcado, _ESTILOS["celda_derecha"])


def _cantidad(valor: Decimal | float) -> str:
    texto = f"{Decimal(str(valor)).normalize():f}"
    return texto.replace(".", ",")


def _tabla(
    filas: list[list],
    anchos: list[float],
    encabezado: bool = True,
    numericas: tuple[int, ...] = (),
) -> Table:
    tabla = Table(filas, colWidths=anchos, repeatRows=1 if encabezado else 0)
    # El encabezado de una columna de números se alinea con sus valores.
    estilo: list[tuple] = [("ALIGN", (c, 0), (c, 0), "RIGHT") for c in numericas]
    estilo += [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if encabezado:
        estilo += [
            ("BACKGROUND", (0, 0), (-1, 0), _PRIMARIO),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ]
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _barra(puntaje: float) -> Drawing:
    ancho, alto = 60 * mm, 3 * mm
    lleno = max(0.0, min(puntaje, 100.0)) / 100 * ancho
    dibujo = Drawing(ancho, alto)
    dibujo.add(Rect(0, 0, ancho, alto, fillColor=_BORDE, strokeColor=None))
    dibujo.add(Rect(0, 0, lleno, alto, fillColor=_PRIMARIO, strokeColor=None))
    return dibujo


def _encabezado(s: ExportSnapshot) -> list[Flowable]:
    t = s.tender
    estado = "Cerrada" if t.esta_cerrada() else (t.status_code or "").capitalize()
    return [
        _p("CHIRIPA · DETALLE DE LICITACIÓN · COMPRA ÁGIL", "marca"),
        Spacer(1, 2 * mm),
        _p(t.name, "titulo"),
        _p(f"ID {t.code}" + (f" · {estado}" if estado else ""), "subtitulo"),
        Spacer(1, 4 * mm),
    ]


def _datos_generales(s: ExportSnapshot) -> list[Flowable]:
    t = s.tender
    ubicacion = ", ".join(v for v in (t.commune, t.region) if v) or None
    pares = [
        ("Organismo", t.buyer_name),
        ("Unidad compradora", t.buyer_unit),
        ("Ubicación", ubicacion),
        ("Monto disponible", format_money(t.available_amount_clp)),
        ("Preparado para", s.supplier_name),
    ]
    filas = [[_p(etiqueta, "etiqueta"), _p(valor)] for etiqueta, valor in pares]
    tabla = _tabla(filas, [45 * mm, _ANCHO_UTIL - 45 * mm], encabezado=False)
    bloque: list[Flowable] = [_p("Datos generales", "seccion"), tabla]
    if t.description:
        bloque += [Spacer(1, 3 * mm), _p(t.description)]
    return bloque


def _analisis(s: ExportSnapshot) -> list[Flowable]:
    titulo = _p("Análisis de compatibilidad", "seccion")
    a: DeepAnalysis | None = s.analysis
    if a is None:
        mensaje = "Sin análisis de compatibilidad para esta empresa."
        if s.score_pct is not None:
            mensaje = f"Compatibilidad calculada: {s.score_pct}%. {mensaje}"
        return [titulo, _p(mensaje)]

    color = _RECOMENDACION.get(a.recommendation, _TEXTO)
    puntaje = ParagraphStyle("p", parent=_ESTILOS["puntaje"], textColor=color)
    recomendacion = ParagraphStyle(
        "r", parent=_ESTILOS["texto"], textColor=color, fontName="Helvetica-Bold", fontSize=11
    )
    resumen = Table(
        [
            [
                Paragraph(f"{round(a.compatibility_score)}%", puntaje),
                Paragraph(escape(a.recommendation), recomendacion),
            ],
            [_barra(a.compatibility_score), _p(f"Actualizado el {format_chile(a.updated_at)}", "subtitulo")],
        ],
        colWidths=[70 * mm, _ANCHO_UTIL - 70 * mm],
    )
    resumen.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _PRIMARIO_SUAVE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    # La justificación va suelta, no dentro de una tabla: una celda no se parte
    # entre páginas y un texto largo haría fallar la generación.
    return [
        KeepTogether([titulo, resumen]),
        Spacer(1, 3 * mm),
        _p("Justificación", "etiqueta"),
        Spacer(1, 1 * mm),
        _p(a.justification),
    ]


def _fechas(s: ExportSnapshot) -> list[Flowable]:
    filas: list[list] = [["Hito", "Fecha (hora de Chile)"]]
    filas += [[_p(f.label, "celda"), _p(format_chile(f.at), "celda")] for f in s.key_dates]
    return [_p("Fechas clave", "seccion"), _tabla(filas, [90 * mm, _ANCHO_UTIL - 90 * mm])]


def _items(s: ExportSnapshot) -> list[Flowable]:
    if not s.tender.items:
        return []
    filas: list[list] = [["Ítem", "Descripción", "Cantidad"]]
    filas += [
        [
            _p(i.name, "celda"),
            _p(i.description or "—", "celda"),
            _p(f"{_cantidad(i.quantity)} {i.unit_of_measure}", "celda_derecha"),
        ]
        for i in s.tender.items
    ]
    return [
        _p("Ítems solicitados", "seccion"),
        _tabla(filas, [60 * mm, _ANCHO_UTIL - 95 * mm, 35 * mm], numericas=(2,)),
    ]


def _cotizacion(s: ExportSnapshot) -> list[Flowable]:
    titulo = _p(f"Cotización de {s.supplier_name}", "seccion")
    q: Quotation | None = s.quotation
    if q is None:
        return [titulo, _p("Sin cotización registrada para esta licitación.")]

    filas: list[list] = [["Material", "Unidad", "Cantidad", "Precio unitario", "Subtotal"]]
    for item in q.items:
        filas.append(
            [
                _p(item.description, "celda"),
                _p(item.unit, "celda"),
                _p(_cantidad(item.quantity), "celda_derecha"),
                _p(format_money(item.unit_price, q.currency), "celda_derecha"),
                _p(format_money(item.subtotal, q.currency), "celda_derecha"),
            ]
        )
    total = escape(format_money(q.total, q.currency))
    filas.append(
        ["", "", "", _p_marcado("<b>Total</b>"), _p_marcado(f"<b>{total}</b>")]
    )
    tabla = _tabla(
        filas,
        [_ANCHO_UTIL - 125 * mm, 20 * mm, 25 * mm, 40 * mm, 40 * mm],
        numericas=(2, 3, 4),
    )
    tabla.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.8, _PRIMARIO)]))
    return [titulo, tabla, Spacer(1, 1 * mm), _p(f"Actualizada el {format_chile(q.updated_at)}", "subtitulo")]


class _CanvasNumerado(Canvas):
    """Pie con "Página X de Y": el total recién se conoce al final, así que se
    guarda cada página y el pie se dibuja todo junto al cerrar el documento."""

    def __init__(self, *args, pie: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pie = pie
        self._paginas: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 (nombre de ReportLab)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(_TENUE)
            self.drawString(_MARGEN, 10 * mm, self._pie)
            self.drawRightString(A4[0] - _MARGEN, 10 * mm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


class ReportLabPdfRenderer:
    def render(self, snapshot: ExportSnapshot) -> bytes:
        salida = BytesIO()
        documento = SimpleDocTemplate(
            salida,
            pagesize=A4,
            leftMargin=_MARGEN,
            rightMargin=_MARGEN,
            topMargin=_MARGEN,
            bottomMargin=20 * mm,
            title=f"Licitación {snapshot.tender.code}",
            author="Chiripa",
        )
        contenido = [
            *_encabezado(snapshot),
            *_datos_generales(snapshot),
            *_analisis(snapshot),
            *_fechas(snapshot),
            *_items(snapshot),
            *_cotizacion(snapshot),
        ]
        pie = f"Generado el {format_chile(snapshot.generated_at)} · Chiripa"
        documento.build(contenido, canvasmaker=partial(_CanvasNumerado, pie=pie))
        return salida.getvalue()
