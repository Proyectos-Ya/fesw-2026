"""Interfaz del envío de correo.

La capa de aplicación solo conoce esta abstracción. Que detrás haya SMTP, una
API HTTP o un doble de pruebas es un detalle de infraestructura.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    """Un correo listo para enviar.

    Se manda siempre en las dos variantes: el cuerpo de texto plano es el que
    ven los clientes que bloquean HTML, y su presencia también reduce la
    probabilidad de que el correo caiga en spam.
    """

    to: str
    subject: str
    text_body: str
    html_body: str


class IEmailService(ABC):
    @abstractmethod
    async def send(self, message: EmailMessage) -> None:
        """Envía el correo.

        Lanza `TransientEmailError` si el fallo admite reintento y
        `PermanentEmailError` si la dirección fue rechazada de forma definitiva.
        """
        pass
