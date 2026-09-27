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


_ETIQUETA_ROL: dict[str, str] = {
    "admin": "Administrador",
    "member": "Miembro",
    "viewer": "Lector",
}


def _nombre_rol(role: object) -> str:
    valor = getattr(role, "value", str(role)).lower()
    return _ETIQUETA_ROL.get(valor, "Representante")


def invitation_url(base_url: str, token: str) -> str:
    """Enlace directo al panel principal con el token de invitación."""
    from urllib.parse import quote

    return f"{base_url.rstrip('/')}/?invitation_token={quote(token)}"


def build_invitation_subject(supplier_name: str) -> str:
    return f"Invitación para unirte al equipo de {supplier_name} en ProyectosYA"


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
        f'"{supplier_name}" en ProyectosYA con el rol de {rol_legible}.',
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
        f"<strong>{empresa_segura}</strong> en ProyectosYA con el rol de "
        f"<strong>{rol_legible}</strong>.</p>"
        f'<p style="margin:0 0 16px;font-size:14px;color:#6b6259">'
        "Al aceptar, podrás colaborar en las licitaciones de esta organización sin perder "
        "tus membresías actuales.</p>"
        f'<a href="{url_segura}" style="display:inline-block;background:#0f766e;'
        "color:#ffffff;padding:10px 18px;border-radius:6px;"
        'text-decoration:none;font-size:14px;font-weight:600">Revisar invitación</a>'
        "</div>"
        '<p style="color:#6b6259;font-size:12px;margin-top:12px">'
        "Si no reconoces esta invitación, puedes rechazarla desde tu panel de inicio en ProyectosYA.</p>"
        "</div>"
    )

