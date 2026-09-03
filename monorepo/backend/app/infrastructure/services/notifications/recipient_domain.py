"""¿Puede este dominio recibir correo?

Por qué existe
--------------
El servicio SMTP solo detectaba una dirección inexistente si el relay la
rechazaba en el acto, con un `SMTPRecipientsRefused` 5xx. Brevo y SendGrid no
trabajan así: aceptan el mensaje con un 250 y notifican el rebote después, por
webhook. Como el backend no expone ningún webhook de rebotes, esos casos se
marcaban como "enviado" y el usuario nunca veía el aviso.

Consultar el DNS antes de enviar cierra la mitad del hueco que no depende del
proveedor: si el dominio no existe, se sabe sin mandar nada. Lo que esto **no**
cubre es un buzón inexistente en un dominio que sí existe (`nadie@gmail.com`):
eso solo lo sabe el servidor de destino, y para enterarse hace falta el webhook.

Criterio de resolución (RFC 5321, §5.1): primero MX; si no hay, se cae a A/AAAA,
porque un dominio sin MX pero con dirección IP sí acepta correo.
"""

from enum import Enum, auto

import dns.asyncresolver
import dns.exception
import dns.resolver

# Corto a propósito: esto corre dentro del bucle de entrega, delante de cada
# envío. Si el DNS no contesta en este tiempo se sigue adelante igual.
DEFAULT_DNS_TIMEOUT_SECONDS = 5.0


class EstadoDominio(Enum):
    EXISTE = auto()
    NO_EXISTE = auto()
    # Ni sí ni no: DNS caído, timeout o SERVFAIL. Nunca se traduce a un fallo
    # permanente, porque desactivarle el correo a alguien por un problema de red
    # ajeno solo lo revierte el propio usuario, a mano, desde la interfaz.
    INDETERMINADO = auto()


def extraer_dominio(direccion: str) -> str | None:
    """Devuelve el dominio de la dirección, o None si no tiene forma de tal."""
    _, separador, dominio = direccion.rpartition("@")
    if not separador or not dominio.strip():
        return None
    return dominio.strip().lower()


class DnsDomainChecker:
    """Resuelve el dominio contra el DNS real."""

    def __init__(self, timeout: float = DEFAULT_DNS_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    async def __call__(self, dominio: str) -> EstadoDominio:
        try:
            respuesta = await dns.asyncresolver.resolve(
                dominio, "MX", lifetime=self._timeout, raise_on_no_answer=True
            )
            # MX nulo (RFC 7505): un único registro que apunta a la raíz, ".".
            # Es la forma estándar de declarar "este dominio no recibe correo",
            # y la usan dominios reservados como example.com.
            if all(str(r.exchange) == "." for r in respuesta):
                return EstadoDominio.NO_EXISTE
            return EstadoDominio.EXISTE
        except dns.resolver.NXDOMAIN:
            # El dominio no existe. Es el caso de los TLD reservados como
            # .invalid y también el de los errores de tipeo (@gmial.con).
            return EstadoDominio.NO_EXISTE
        except dns.resolver.NoAnswer:
            # Existe pero no publica MX: hay que probar A/AAAA antes de decidir.
            return await self._tiene_direccion(dominio)
        except (dns.exception.DNSException, OSError):
            return EstadoDominio.INDETERMINADO

    async def _tiene_direccion(self, dominio: str) -> EstadoDominio:
        for tipo in ("A", "AAAA"):
            try:
                await dns.asyncresolver.resolve(
                    dominio, tipo, lifetime=self._timeout, raise_on_no_answer=True
                )
                return EstadoDominio.EXISTE
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                continue
            except (dns.exception.DNSException, OSError):
                return EstadoDominio.INDETERMINADO
        # Registrado pero sin MX ni dirección: no hay a dónde entregar.
        return EstadoDominio.NO_EXISTE
