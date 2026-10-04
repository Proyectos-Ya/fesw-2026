"""Codificación del checksum que S3 y R2 aceptan en `x-amz-checksum-sha256`.

Es el **base64 de los 32 bytes crudos** del digest SHA-256: 44 caracteres, y
termina en `=`. No es el hex (64 caracteres) ni el base64 del hex (88), que es el
error común. Chiripa guarda el hex; esto traduce de ida y de vuelta.
"""

import base64
import binascii


def sha256_hex_a_base64(hex_digest: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_digest)).decode("ascii")


def base64_a_sha256_hex(valor: str | None) -> str | None:
    """El hex del checksum, o `None` si falta o no es el base64 de un SHA-256."""
    if not valor:
        return None
    try:
        crudo = base64.b64decode(valor, validate=True)
    except (binascii.Error, ValueError):
        return None
    return crudo.hex() if len(crudo) == 32 else None
