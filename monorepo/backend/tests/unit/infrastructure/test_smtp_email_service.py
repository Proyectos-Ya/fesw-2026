"""Pruebas del envío SMTP, centradas en la detección de direcciones inexistentes.

El caso que motiva estas pruebas: al probar con una dirección que no existe, el
correo salía marcado como "enviado". Brevo y SendGrid aceptan el mensaje con un
250 y recién después descubren que el destinatario no existe, así que el rebote
llega de forma asíncrona —por webhook— y el `SMTPRecipientsRefused` que el
servicio esperaba nunca ocurre. Sin webhook configurado, el sistema jamás se
enteraba y el aviso de la interfaz no aparecía nunca.

La comprobación de DNS cierra la mitad del hueco que sí se puede cerrar sin
depender del proveedor: un dominio que no existe se detecta antes de enviar.
"""

import aiosmtplib
import pytest

from app.application.services.email_service import EmailMessage
from app.domain.errors.notification_errors import (
    PermanentEmailError,
    TransientEmailError,
)
from app.infrastructure.services.notifications.recipient_domain import EstadoDominio
from app.infrastructure.services.notifications.smtp_email_service import (
    SmtpEmailService,
)

MENSAJE = EmailMessage(
    to="alertas-rebote@demo.invalid",
    subject="Licitación compatible",
    text_body="texto",
    html_body="<p>html</p>",
)


class SmtpEspia:
    """Reemplaza a `aiosmtplib.send` y anota si llegó a llamarse."""

    def __init__(self) -> None:
        self.llamadas = 0

    async def __call__(self, *args, **kwargs) -> None:
        self.llamadas += 1


@pytest.fixture
def smtp(monkeypatch) -> SmtpEspia:
    espia = SmtpEspia()
    monkeypatch.setattr(aiosmtplib, "send", espia)
    return espia


def _servicio(estado: EstadoDominio) -> SmtpEmailService:
    async def verificar(_dominio: str) -> EstadoDominio:
        return estado

    return SmtpEmailService(
        host="smtp.example.com", port=587, verificar_dominio=verificar
    )


async def test_dominio_inexistente_es_error_permanente(smtp: SmtpEspia) -> None:
    """Es lo que apaga el envío de correo y muestra el aviso al usuario."""
    with pytest.raises(PermanentEmailError):
        await _servicio(EstadoDominio.NO_EXISTE).send(MENSAJE)


async def test_dominio_inexistente_ni_siquiera_intenta_enviar(
    smtp: SmtpEspia,
) -> None:
    """Sin esto el proveedor aceptaría el mensaje y lo daría por enviado."""
    with pytest.raises(PermanentEmailError):
        await _servicio(EstadoDominio.NO_EXISTE).send(MENSAJE)

    assert smtp.llamadas == 0


async def test_el_motivo_nombra_el_dominio(smtp: SmtpEspia) -> None:
    """El texto va tal cual al aviso de la interfaz: tiene que ser accionable."""
    with pytest.raises(PermanentEmailError) as exc:
        await _servicio(EstadoDominio.NO_EXISTE).send(MENSAJE)

    assert "demo.invalid" in str(exc.value)


async def test_dominio_valido_se_envia(smtp: SmtpEspia) -> None:
    await _servicio(EstadoDominio.EXISTE).send(MENSAJE)

    assert smtp.llamadas == 1


async def test_dns_indeterminado_no_bloquea_el_envio(smtp: SmtpEspia) -> None:
    """Fail open: un DNS caído no puede desactivarle el correo a nadie.

    Marcar como permanente lo que en realidad es un problema de red apagaría
    las notificaciones de usuarios con direcciones perfectamente válidas, y eso
    solo lo revierte el usuario a mano desde la interfaz.
    """
    await _servicio(EstadoDominio.INDETERMINADO).send(MENSAJE)

    assert smtp.llamadas == 1


async def test_direccion_sin_arroba_es_error_permanente(smtp: SmtpEspia) -> None:
    servicio = _servicio(EstadoDominio.EXISTE)

    with pytest.raises(PermanentEmailError):
        await servicio.send(
            EmailMessage(
                to="no-es-una-direccion", subject="s", text_body="t", html_body="h"
            )
        )

    assert smtp.llamadas == 0


# ---------------------------------------------------------------------------
# Traducción de los errores del servidor SMTP (comportamiento ya existente)
# ---------------------------------------------------------------------------


async def test_timeout_del_servidor_es_transitorio(monkeypatch) -> None:
    async def cae(*args, **kwargs):
        raise TimeoutError("sin respuesta")

    monkeypatch.setattr(aiosmtplib, "send", cae)

    with pytest.raises(TransientEmailError):
        await _servicio(EstadoDominio.EXISTE).send(MENSAJE)


async def test_respuesta_5xx_es_permanente(monkeypatch) -> None:
    async def rechaza(*args, **kwargs):
        raise aiosmtplib.SMTPResponseException(550, "Mailbox unavailable")

    monkeypatch.setattr(aiosmtplib, "send", rechaza)

    with pytest.raises(PermanentEmailError):
        await _servicio(EstadoDominio.EXISTE).send(MENSAJE)


# ---------------------------------------------------------------------------
# Resolución de dominios contra el DNS real
#
# Estas dos sí salen a la red. Van marcadas para poder excluirlas, pero valen
# la pena: son las que prueban que la traducción de respuestas del DNS a
# EstadoDominio es correcta, que es justo lo que un doble no puede demostrar.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dominio", "esperado"),
    [
        ("demo.invalid", EstadoDominio.NO_EXISTE),  # TLD reservado (RFC 2606)
        ("gmial.con", EstadoDominio.NO_EXISTE),  # error de tipeo típico
        ("example.com", EstadoDominio.NO_EXISTE),  # MX nulo (RFC 7505)
        ("gmail.com", EstadoDominio.EXISTE),
    ],
)
@pytest.mark.network
async def test_resuelve_dominios_reales(dominio: str, esperado) -> None:
    from app.infrastructure.services.notifications.recipient_domain import (
        DnsDomainChecker,
    )

    assert await DnsDomainChecker()(dominio) is esperado
