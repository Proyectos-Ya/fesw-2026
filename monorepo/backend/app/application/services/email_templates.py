"""Cuerpo de los correos de alerta.

Deliberadamente sin datos sensibles: título, organismo, fecha de cierre y
compatibilidad. Todo lo demás se ve en la plataforma, tras iniciar sesión.
"""

from dataclasses import dataclass
from datetime import datetime
from html import escape
from uuid import UUID


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


# --- Exportaciones en segundo plano (HdU 19, criterios 8 y 9) ---


@dataclass(frozen=True)
class ExportReadyItem:
    """Un archivo que tardó más de 10 s y se terminó en segundo plano."""

    job_id: UUID
    tender_name: str
    # "PDF" o "Excel": es lo que el usuario pidió, dicho como lo diría él.
    format_label: str


def export_download_url(base_url: str, job_id: UUID) -> str:
    """Página de la app que descarga el archivo, previa sesión."""
    return f"{base_url.rstrip('/')}/exportaciones/{job_id}"


def _envoltorio(cuerpo: str) -> str:
    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif;'
        f'max-width:600px;margin:0 auto;padding:24px">{cuerpo}</div>'
    )


def build_export_ready_subject(item: ExportReadyItem) -> str:
    return f"Tu {item.format_label} está listo: {item.tender_name}"


def build_export_ready_text_body(item: ExportReadyItem, base_url: str) -> str:
    return (
        f"El {item.format_label} de la licitación «{item.tender_name}» ya está listo.\n\n"
        f"Descárgalo aquí: {export_download_url(base_url, item.job_id)}\n\n"
        "El enlace está disponible por 7 días y requiere iniciar sesión.\n"
    )


def build_export_ready_html_body(item: ExportReadyItem, base_url: str) -> str:
    url = export_download_url(base_url, item.job_id)
    return _envoltorio(
        f'<p style="font-size:15px">El {escape(item.format_label)} de la licitación '
        f"<strong>{escape(item.tender_name)}</strong> ya está listo.</p>"
        f'<a href="{escape(url)}" style="display:inline-block;background:#0f766e;'
        "color:#ffffff;padding:8px 16px;border-radius:6px;"
        f'text-decoration:none;font-size:14px">Descargar {escape(item.format_label)}</a>'
        '<p style="color:#6b6259;font-size:13px">El enlace está disponible por 7 días '
        "y requiere iniciar sesión.</p>"
    )


def build_export_failed_subject(item: ExportReadyItem) -> str:
    return f"No se pudo generar tu {item.format_label}: {item.tender_name}"


def build_export_failed_text_body(item: ExportReadyItem) -> str:
    return (
        f"No pudimos generar el {item.format_label} de la licitación «{item.tender_name}».\n\n"
        "Vuelve a exportarlo desde la ficha de la licitación.\n"
    )


def build_export_failed_html_body(item: ExportReadyItem) -> str:
    return _envoltorio(
        f'<p style="font-size:15px">No pudimos generar el {escape(item.format_label)} '
        f"de la licitación <strong>{escape(item.tender_name)}</strong>.</p>"
        '<p style="font-size:14px">Vuelve a exportarlo desde la ficha de la licitación.</p>'
    )
