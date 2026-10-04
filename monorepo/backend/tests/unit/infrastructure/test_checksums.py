"""Codificación del checksum de S3/R2: base64 de los 32 bytes crudos del digest.

No es el hex (64 caracteres) ni el base64 del hex (88 caracteres, un error común):
una cabecera mal codificada hace que R2 rechace la subida con un `BadDigest`
que no dice nada útil.
"""

import base64
import hashlib

from app.infrastructure.services.attachments.checksums import (
    base64_a_sha256_hex,
    sha256_hex_a_base64,
)

HOLA_HEX = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79"
HOLA_B64 = "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k="


def test_hex_a_base64() -> None:
    resultado = sha256_hex_a_base64(HOLA_HEX)

    assert resultado == HOLA_B64
    assert len(resultado) == 44


def test_base64_a_hex() -> None:
    assert base64_a_sha256_hex(HOLA_B64) == HOLA_HEX


def test_base64_invalido_o_de_otro_largo_es_none() -> None:
    assert base64_a_sha256_hex(None) is None
    assert base64_a_sha256_hex("") is None
    assert base64_a_sha256_hex("no-es-base64!") is None
    assert base64_a_sha256_hex(base64.b64encode(b"x" * 16).decode()) is None


def test_vector_de_la_documentacion_de_s3() -> None:
    digest = hashlib.sha256(b"Welcome to Amazon S3.").hexdigest()

    assert sha256_hex_a_base64(digest) == "RM591nyVng01JP+sF3Hfu6h9K2tLTpnkIDSouAP4sHI="
