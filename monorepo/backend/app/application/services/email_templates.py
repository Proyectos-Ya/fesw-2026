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


@dataclass(frozen=True)
class MilestoneReminderItem:
    """Una licitación con hitos próximos que el usuario pidió recordar (HU-16)."""

    tender_id: UUID
    title: str
    # (hito, cuándo vence), en UTC naive.
    milestones: list[tuple[str, datetime]]


def build_reminder_subject(items: list[MilestoneReminderItem]) -> str:
    total = sum(len(i.milestones) for i in items)
    if total == 1:
        return f"Recordatorio: {items[0].milestones[0][0]} — {items[0].title}"
    return f"Recordatorio: {total} hitos próximos"


_ENCABEZADO_RECORDATORIO = (
    "Se acercan hitos de licitaciones para los que pediste un recordatorio:"
)


def build_reminder_text_body(items: list[MilestoneReminderItem], base_url: str) -> str:
    lineas = [_ENCABEZADO_RECORDATORIO, ""]
    for item in items:
        lineas.append(f"* {item.title}")
        for hito, vence in item.milestones:
            lineas.append(f"  {hito}: {_hora_chile(vence)} (hora de Chile)")
        lineas.append(f"  Ver detalle: {tender_url(base_url, item.tender_id)}")
        lineas.append("")
    return "\n".join(lineas)


def build_reminder_html_body(items: list[MilestoneReminderItem], base_url: str) -> str:
    tarjetas = []
    for item in items:
        url = tender_url(base_url, item.tender_id)
        filas = "".join(
            f'<p style="margin:0 0 4px;font-size:14px">{escape(hito)}: '
            f"<strong>{_hora_chile(vence)}</strong></p>"
            for hito, vence in item.milestones
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
        f'<p style="font-size:15px">{_ENCABEZADO_RECORDATORIO}</p>'
        f"{''.join(tarjetas)}"
        '<p style="color:#6b6259;font-size:13px">Horas en hora de Chile. Puedes desactivar '
        "el recordatorio desde la ficha de la licitación.</p>"
        "</div>"
    )


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


_ETIQUETA_ROL: dict[str, str] = {
    "admin": "Administrador",
    "member": "Miembro",
}


def _nombre_rol(role: object) -> str:
    valor = getattr(role, "value", str(role)).lower()
    return _ETIQUETA_ROL.get(valor, "Miembro")


def invitation_url(base_url: str, token: str) -> str:
    """Enlace directo al panel principal con el token de invitación."""
    from urllib.parse import quote

    return f"{base_url.rstrip('/')}/?invitation_token={quote(token)}"


def build_invitation_subject(supplier_name: str) -> str:
    return f"Invitación para unirte al equipo de {supplier_name} en Chiripa"


def build_invitation_text_body(
    supplier_name: str,
    inviter_name: str,
    role: object,
    base_url: str,
    token: str,
) -> str:
    rol_legible = _nombre_rol(role)
    url = invitation_url(base_url, token)
    lineas = [
        "Hola,",
        "",
        f"{inviter_name} te ha invitado a unirte al espacio de trabajo de "
        f'"{supplier_name}" en Chiripa con el rol de {rol_legible}.',
        "",
        "Para revisar y aceptar o rechazar esta invitación, ingresa a tu cuenta en:",
        f"  {url}",
        "",
        "Si no esperabas esta invitación, puedes ignorar este mensaje o rechazarla desde la plataforma.",
    ]
    return "\n".join(lineas)


def build_invitation_html_body(
    supplier_name: str,
    inviter_name: str,
    role: object,
    base_url: str,
    token: str,
) -> str:
    rol_legible = escape(_nombre_rol(role))
    empresa_segura = escape(supplier_name)
    invitador_seguro = escape(inviter_name)
    url_segura = escape(invitation_url(base_url, token))
    return (
        '<div style="font-family:system-ui,-apple-system,sans-serif;'
        'max-width:600px;margin:0 auto;padding:24px">'
        '<div style="border:1px solid #e5e0d8;border-radius:8px;padding:20px">'
        f'<h2 style="margin:0 0 12px;font-size:18px">Invitación a {empresa_segura}</h2>'
        f'<p style="margin:0 0 12px;font-size:15px;line-height:1.5">'
        f"<strong>{invitador_seguro}</strong> te ha invitado a formar parte del equipo de "
        f"<strong>{empresa_segura}</strong> en Chiripa con el rol de "
        f"<strong>{rol_legible}</strong>.</p>"
        f'<p style="margin:0 0 16px;font-size:14px;color:#6b6259">'
        "Al aceptar, podrás colaborar en las licitaciones de esta organización sin perder "
        "tus membresías actuales.</p>"
        f'<a href="{url_segura}" style="display:inline-block;background:#0f766e;'
        "color:#ffffff;padding:10px 18px;border-radius:6px;"
        'text-decoration:none;font-size:14px;font-weight:600">Revisar invitación en Chiripa</a>'
        "</div>"
        '<p style="color:#6b6259;font-size:12px;margin-top:12px">'
        "Si no reconoces esta invitación, puedes rechazarla desde tu panel de inicio en Chiripa.</p>"
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
