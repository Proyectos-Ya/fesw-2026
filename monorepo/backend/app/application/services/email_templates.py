"""Cuerpo de los correos de alerta.

Deliberadamente sin datos sensibles: título, organismo, fecha de cierre y
compatibilidad. Todo lo demás se ve en la plataforma, tras iniciar sesión.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from uuid import UUID

from app.shared.datetime_utils import CHILE_TZ


@dataclass(frozen=True)
class AlertItem:
    """Una licitación tal como aparece en el correo."""

    tender_id: UUID
    title: str
    buyer_name: str | None
    closing_at: datetime | None
    score: float  # Escala 0..1

    @property
    def score_pct(self) -> int:
        return round(self.score * 100)


def _formatear_fecha(valor: datetime | None) -> str:
    return valor.strftime("%d-%m-%Y") if valor else "sin fecha informada"


@dataclass(frozen=True)
class DateChangeItem:
    """Una licitación con fechas oficiales movidas (HU-16)."""

    tender_id: UUID
    title: str
    # (hito, fecha anterior, fecha nueva), en UTC naive.
    changes: list[tuple[str, datetime, datetime]]


def _hora_chile(valor: datetime) -> str:
    return valor.replace(tzinfo=UTC).astimezone(CHILE_TZ).strftime("%d-%m-%Y %H:%M")


def build_date_change_subject(items: list[DateChangeItem]) -> str:
    if len(items) == 1:
        return f"Fecha modificada: {items[0].title}"
    return f"Fechas modificadas en {len(items)} licitaciones"


_ENCABEZADO_CAMBIO = (
    "Mercado Público modificó fechas oficiales de una licitación que tienes en tu "
    "calendario. Si la sincronizaste, el evento ya quedó actualizado."
)


def build_date_change_text_body(items: list[DateChangeItem], base_url: str) -> str:
    lineas = [_ENCABEZADO_CAMBIO, ""]
    for item in items:
        lineas.append(f"* {item.title}")
        for hito, antes, ahora in item.changes:
            lineas.append(f"  {hito}: {_hora_chile(antes)} → {_hora_chile(ahora)} (hora de Chile)")
        lineas.append(f"  Ver detalle: {tender_url(base_url, item.tender_id)}")
        lineas.append("")
    return "\n".join(lineas)


def build_date_change_html_body(items: list[DateChangeItem], base_url: str) -> str:
    tarjetas = []
    for item in items:
        url = tender_url(base_url, item.tender_id)
        filas = "".join(
            f'<p style="margin:0 0 4px;font-size:14px">{escape(hito)}: '
            f"<s>{_hora_chile(antes)}</s> → <strong>{_hora_chile(ahora)}</strong></p>"
            for hito, antes, ahora in item.changes
        )
        tarjetas.append(
            '<div style="border:1px solid #e5e0d8;border-radius:8px;'
            'padding:16px;margin-bottom:12px">'
            f'<h2 style="margin:0 0 8px;font-size:16px">{escape(item.title)}</h2>'
            f"{filas}"
            f'<a href="{escape(url)}" style="display:inline-block;margin-top:8px;'
            "background:#0f766e;color:#ffffff;padding:8px 16px;border-radius:6px;"
            'text-decoration:none;font-size:14px">Ver licitación</a>'
            "</div>"
        )
    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif;'
        'max-width:600px;margin:0 auto;padding:24px">'
        f'<p style="font-size:15px">{_ENCABEZADO_CAMBIO}</p>'
        f"{''.join(tarjetas)}"
        '<p style="color:#6b6259;font-size:13px">Horas en hora de Chile.</p>'
        "</div>"
    )


def tender_url(base_url: str, tender_id: UUID) -> str:
    """Enlace profundo a la ficha de la licitación."""
    return f"{base_url.rstrip('/')}/matches/{tender_id}"


def build_subject(items: list[AlertItem], is_digest: bool) -> str:
    if is_digest:
        return f"Resumen diario: {len(items)} licitaciones compatibles con tu empresa"
    if len(items) == 1:
        return f"Nueva licitación compatible ({items[0].score_pct}%): {items[0].title}"
    return f"{len(items)} nuevas licitaciones compatibles con tu empresa"


def build_text_body(items: list[AlertItem], base_url: str, is_digest: bool) -> str:
    encabezado = (
        "Estas son las licitaciones compatibles que encontramos hoy:"
        if is_digest
        else "Detectamos una nueva licitación compatible con tu empresa:"
        if len(items) == 1
        else "Detectamos nuevas licitaciones compatibles con tu empresa:"
    )
    lineas = [encabezado, ""]
    for item in items:
        lineas.append(f"* {item.title}")
        lineas.append(f"  Organismo: {item.buyer_name or 'no informado'}")
        lineas.append(f"  Cierra: {_formatear_fecha(item.closing_at)}")
        lineas.append(f"  Compatibilidad: {item.score_pct}%")
        lineas.append(f"  Ver detalle: {tender_url(base_url, item.tender_id)}")
        lineas.append("")
    lineas.append(
        "Puedes ajustar el umbral y la frecuencia de estos avisos en "
        f"{base_url.rstrip('/')}/configuracion/notificaciones"
    )
    return "\n".join(lineas)


def build_html_body(items: list[AlertItem], base_url: str, is_digest: bool) -> str:
    encabezado = (
        "Estas son las licitaciones compatibles que encontramos hoy:"
        if is_digest
        else "Detectamos una nueva licitación compatible con tu empresa:"
        if len(items) == 1
        else "Detectamos nuevas licitaciones compatibles con tu empresa:"
    )
    tarjetas = []
    for item in items:
        # Los títulos vienen de Mercado Público: se escapan antes de inyectarlos.
        url = tender_url(base_url, item.tender_id)
        tarjetas.append(
            '<div style="border:1px solid #e5e0d8;border-radius:8px;'
            'padding:16px;margin-bottom:12px">'
            f'<h2 style="margin:0 0 8px;font-size:16px">{escape(item.title)}</h2>'
            f'<p style="margin:0 0 4px;color:#6b6259;font-size:14px">'
            f"Organismo: {escape(item.buyer_name or 'no informado')}</p>"
            f'<p style="margin:0 0 4px;color:#6b6259;font-size:14px">'
            f"Cierra: {_formatear_fecha(item.closing_at)}</p>"
            f'<p style="margin:0 0 12px;font-size:14px">'
            f"<strong>Compatibilidad: {item.score_pct}%</strong></p>"
            f'<a href="{escape(url)}" style="display:inline-block;background:#0f766e;'
            "color:#ffffff;padding:8px 16px;border-radius:6px;"
            'text-decoration:none;font-size:14px">Ver licitación</a>'
            "</div>"
        )
    ajustes = f"{base_url.rstrip('/')}/configuracion/notificaciones"
    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif;'
        'max-width:600px;margin:0 auto;padding:24px">'
        f'<p style="font-size:15px">{encabezado}</p>'
        f"{''.join(tarjetas)}"
        f'<p style="color:#6b6259;font-size:13px">Puedes ajustar el umbral y la '
        f'frecuencia de estos avisos en <a href="{escape(ajustes)}">tus '
        "preferencias de notificaciones</a>.</p>"
        "</div>"
    )
