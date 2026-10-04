"""AWS Signature Version 4 contra los vectores oficiales de la documentación de S3.

Si la canonicalización tuviera un error de un solo carácter, estos hashes no
coincidirían: por eso los vectores van primero y el módulo se escribió después.

- https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
- https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/signature-v4-examples.html
"""

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.services.attachments.sigv4 import (
    SigV4Credentials,
    canonical_headers,
    canonical_request,
    derive_signing_key,
    presign_url,
    sign_request_headers,
    string_to_sign,
    uri_encode,
)

AWS = SigV4Credentials(
    "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1"
)
HOST = "examplebucket.s3.amazonaws.com"
MOMENTO = datetime(2013, 5, 24)  # naive = UTC
VACIO = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

URL_PREFIRMADA_S3 = (
    "https://examplebucket.s3.amazonaws.com/test.txt"
    "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request"
    "&X-Amz-Date=20130524T000000Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host"
    "&X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"
)


def test_clave_de_firma_vector_oficial_iam() -> None:
    # Ojo: esta clave de la documentación de IAM lleva "+"; la de S3 lleva "/".
    clave = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"

    assert (
        derive_signing_key(clave, "20150830", "us-east-1", "iam").hex()
        == "c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9"
    )
    assert (
        derive_signing_key(clave, "20120215", "us-east-1", "iam").hex()
        == "f4780e2d9f65fa895f9c67b32ce1baf0b0d8a43505a000a1a9e090d414db404d"
    )


def test_presign_canonical_request_vector_s3() -> None:
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": "AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request",
        "X-Amz-Date": "20130524T000000Z",
        "X-Amz-Expires": "86400",
        "X-Amz-SignedHeaders": "host",
    }

    texto = canonical_request(
        method="GET",
        canonical_uri="/test.txt",
        query=query,
        headers={"host": HOST},
        payload_hash="UNSIGNED-PAYLOAD",
    )[0]

    assert texto == (
        "GET\n"
        "/test.txt\n"
        "X-Amz-Algorithm=AWS4-HMAC-SHA256"
        "&X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request"
        "&X-Amz-Date=20130524T000000Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host\n"
        "host:examplebucket.s3.amazonaws.com\n"
        "\n"
        "host\n"
        "UNSIGNED-PAYLOAD"
    )
    digest = hashlib.sha256(texto.encode()).hexdigest()
    assert digest == "3bfa292879f6447bbcda7001decf97f4a54dc650c8942174ae0a9121cf58ad04"
    assert string_to_sign(
        moment=MOMENTO, scope="20130524/us-east-1/s3/aws4_request", canonical=texto
    ) == (
        "AWS4-HMAC-SHA256\n20130524T000000Z\n20130524/us-east-1/s3/aws4_request\n" + digest
    )


def test_presign_url_vector_s3() -> None:
    url = presign_url(
        credentials=AWS,
        method="GET",
        host=HOST,
        canonical_uri="/test.txt",
        signed_headers={},
        expires_in_seconds=86400,
        now=MOMENTO,
    )

    assert url == URL_PREFIRMADA_S3


def test_cabeceras_get_con_range_vector_s3() -> None:
    cabeceras = sign_request_headers(
        credentials=AWS,
        method="GET",
        host=HOST,
        canonical_uri="/test.txt",
        headers={"Range": "bytes=0-9"},
        payload_hash=VACIO,
        now=MOMENTO,
    )

    assert cabeceras["authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    # Lo que viaja es exactamente lo que se firmó.
    assert cabeceras["host"] == HOST
    assert cabeceras["x-amz-date"] == "20130524T000000Z"
    assert cabeceras["x-amz-content-sha256"] == VACIO

    canonico, _ = canonical_request(
        method="GET",
        canonical_uri="/test.txt",
        query={},
        headers={
            "host": HOST,
            "range": "bytes=0-9",
            "x-amz-content-sha256": VACIO,
            "x-amz-date": "20130524T000000Z",
        },
        payload_hash=VACIO,
    )
    assert (
        hashlib.sha256(canonico.encode()).hexdigest()
        == "7344ae5b7ee6c3e7e6b0fe0640412a37625d1fbfff95c48bbb2dc43964946972"
    )


def test_cabeceras_put_vector_s3() -> None:
    uri = "/" + uri_encode("test$file.text", encode_slash=False)
    assert uri == "/test%24file.text"
    payload = hashlib.sha256(b"Welcome to Amazon S3.").hexdigest()
    assert payload == "44ce7dd67c959e0d3524ffac1771dfbba87d2b6b4b4e99e42034a8b803f8b072"
    cabeceras_firmadas = {
        "Date": "Fri, 24 May 2013 00:00:00 GMT",
        "x-amz-storage-class": "REDUCED_REDUNDANCY",
    }

    cabeceras = sign_request_headers(
        credentials=AWS,
        method="PUT",
        host=HOST,
        canonical_uri=uri,
        headers=cabeceras_firmadas,
        payload_hash=payload,
        now=MOMENTO,
    )

    assert cabeceras["authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=date;host;x-amz-content-sha256;x-amz-date;x-amz-storage-class,"
        "Signature=98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd"
    )
    canonico, _ = canonical_request(
        method="PUT",
        canonical_uri=uri,
        query={},
        headers={
            "date": "Fri, 24 May 2013 00:00:00 GMT",
            "host": HOST,
            "x-amz-content-sha256": payload,
            "x-amz-date": "20130524T000000Z",
            "x-amz-storage-class": "REDUCED_REDUNDANCY",
        },
        payload_hash=payload,
    )
    assert (
        hashlib.sha256(canonico.encode()).hexdigest()
        == "9e0e90d9c76de8fa5b200d8c849cd5b8dc7a3be3951ddb7f6a76b4158342019d"
    )


def test_uri_encode() -> None:
    assert uri_encode("a b/c") == "a%20b%2Fc"
    assert uri_encode("a b/c", encode_slash=False) == "a%20b/c"
    assert uri_encode("-_.~") == "-_.~"
    assert uri_encode("ñ") == "%C3%B1"


def test_canonical_headers_minusculas_ordena_y_colapsa_espacios() -> None:
    assert canonical_headers({"X-B": "  a   b ", "host": "h"}) == (
        "host:h\nx-b:a b\n",
        "host;x-b",
    )


@pytest.mark.parametrize("segundos", [0, 604801])
def test_expiracion_fuera_de_rango(segundos: int) -> None:
    with pytest.raises(ValueError):
        presign_url(
            credentials=AWS,
            method="GET",
            host=HOST,
            canonical_uri="/test.txt",
            signed_headers={},
            expires_in_seconds=segundos,
            now=MOMENTO,
        )


def test_un_datetime_con_zona_se_convierte_a_utc() -> None:
    # 20:00 en Chile el 23 de mayo de 2013 (UTC-4) son las 00:00 UTC del día 24.
    local = datetime(2013, 5, 23, 20, 0, tzinfo=ZoneInfo("America/Santiago"))

    url = presign_url(
        credentials=AWS,
        method="GET",
        host=HOST,
        canonical_uri="/test.txt",
        signed_headers={},
        expires_in_seconds=86400,
        now=local,
    )

    assert url == URL_PREFIRMADA_S3


def test_presign_put_r2_con_checksum_y_tamano() -> None:
    # Vector propio, calculado con la implementación de referencia: ata la URL al
    # tamaño (content-length) y al contenido (x-amz-checksum-sha256) declarados.
    r2 = SigV4Credentials(
        "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "auto"
    )
    host = "0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com"
    uri = (
        "/chiripa-anexos/private/11111111-1111-1111-1111-111111111111/"
        "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79.pdf"
    )

    url = presign_url(
        credentials=r2,
        method="PUT",
        host=host,
        canonical_uri=uri,
        signed_headers={
            "content-length": "4",
            "x-amz-checksum-sha256": "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k=",
        },
        expires_in_seconds=900,
        now=datetime(2026, 10, 3, 12, 0, 0),
    )

    assert url == (
        "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com"
        "/chiripa-anexos/private/11111111-1111-1111-1111-111111111111/"
        "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79.pdf"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
        "&X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20261003%2Fauto%2Fs3%2Faws4_request"
        "&X-Amz-Date=20261003T120000Z&X-Amz-Expires=900"
        "&X-Amz-SignedHeaders=content-length%3Bhost%3Bx-amz-checksum-sha256"
        "&X-Amz-Signature=6166142c10c95335759733a85859489d316b54ba900682be9c39ef6a72127a53"
    )
