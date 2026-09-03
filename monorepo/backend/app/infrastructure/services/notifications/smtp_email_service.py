"""Envío de correo por SMTP.

SMTP plano y no la API propietaria de un proveedor: es el denominador común de
Mailpit (desarrollo), Brevo y SendGrid (producción), así que el mismo código
sirve en los tres y cambiar de entorno es cambiar variables, no clases.
"""

from collections.abc import Awaitable, Callable
from email.message import EmailMessage as MimeMessage

import aiosmtplib

from app.application.services.email_service import EmailMessage, IEmailService
from app.domain.errors.notification_errors import (
    PermanentEmailError,
    TransientEmailError,
)
from app.infrastructure.services.notifications.recipient_domain import (
    DnsDomainChecker,
    EstadoDominio,
    extraer_dominio,
)

VerificadorDeDominio = Callable[[str], Awaitable[EstadoDominio]]


def _es_codigo_permanente(code: int | None) -> bool:
    """Un 5xx del servidor es definitivo; un 4xx es "vuelve a intentar"."""
    return code is not None and 500 <= code < 600


class SmtpEmailService(IEmailService):
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        sender: str = "alertas@proyectosya.local",
        use_tls: bool = False,
        timeout: float = 15.0,
        verificar_dominio: VerificadorDeDominio | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username or None
        self.password = password or None
        self.sender = sender
        self.use_tls = use_tls
        self.timeout = timeout
        self._verificar_dominio = verificar_dominio or DnsDomainChecker()

    def _build_mime(self, message: EmailMessage) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = self.sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")
        return mime

    async def _rechazar_si_el_dominio_no_existe(self, destinatario: str) -> None:
        """Corta antes de enviar lo que el relay aceptaría y rebotaría después.

        Brevo y SendGrid responden 250 y avisan del rebote por webhook, que este
        backend no expone. Sin esta comprobación, una dirección inexistente
        quedaba marcada como enviada y el usuario nunca veía el aviso.
        """
        dominio = extraer_dominio(destinatario)
        if dominio is None:
            raise PermanentEmailError(
                f"'{destinatario}' no es una dirección de correo válida."
            )

        if await self._verificar_dominio(dominio) is EstadoDominio.NO_EXISTE:
            raise PermanentEmailError(
                f"El dominio '{dominio}' no existe, así que la dirección "
                f"'{destinatario}' no puede recibir correo."
            )

    async def send(self, message: EmailMessage) -> None:
        await self._rechazar_si_el_dominio_no_existe(message.to)

        mime = self._build_mime(message)
        try:
            await aiosmtplib.send(
                mime,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                # STARTTLS sobre el 587 es lo que piden Brevo y SendGrid.
                # Mailpit escucha en claro, de ahí el default en False.
                start_tls=self.use_tls or None,
                timeout=self.timeout,
            )
        except aiosmtplib.SMTPRecipientsRefused as exc:
            # El servidor rechazó al destinatario. Si el código es 5xx la
            # dirección no existe y reintentar no cambiaría nada.
            codigos = [r.code for r in exc.recipients] if exc.recipients else []
            detalle = f"Destinatario rechazado: {exc}"
            if any(_es_codigo_permanente(c) for c in codigos):
                raise PermanentEmailError(detalle) from exc
            raise TransientEmailError(detalle) from exc
        except aiosmtplib.SMTPAuthenticationError as exc:
            # Credenciales mal configuradas. Es culpa del despliegue, no de la
            # dirección del usuario: se reintenta para que al corregir la clave
            # lo encolado salga solo, en vez de castigar al destinatario.
            raise TransientEmailError(f"Autenticación SMTP rechazada: {exc}") from exc
        except aiosmtplib.SMTPResponseException as exc:
            detalle = f"El servidor SMTP respondió {exc.code}: {exc.message}"
            if _es_codigo_permanente(exc.code):
                raise PermanentEmailError(detalle) from exc
            raise TransientEmailError(detalle) from exc
        except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
            # Servicio caído, DNS que no resuelve, conexión rechazada o timeout.
            # Es el caso del criterio "servicio de mensajería externa caído".
            raise TransientEmailError(
                f"No se pudo contactar al servidor SMTP: {exc}"
            ) from exc
