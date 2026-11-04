"""Firma AWS Signature Version 4 para la API S3 de Cloudflare R2 (plan 233, decisión 2).

Módulo propio y no boto3 (aprobado): boto3 arrastra decenas de MB para cinco
operaciones, y SigV4 es un algoritmo público y estable. Los tests lo fijan con
los vectores oficiales de la documentación de S3, así que un error de
canonicalización no pasa en silencio.

- Query string auth: https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html
- Header auth:       https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html
"""

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

ALGORITHM = "AWS4-HMAC-SHA256"
UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()
_MAX_EXPIRES = 7 * 24 * 60 * 60  # tope de S3 para una URL prefirmada


@dataclass(frozen=True)
class SigV4Credentials:
    access_key_id: str
    secret_access_key: str
    region: str  # "auto" en R2
    service: str = "s3"


def uri_encode(value: str, *, encode_slash: bool = True) -> str:
    """URI-encode de SigV4: todo salvo A-Z a-z 0-9 - _ . ~, con hex en mayúsculas.

    En la ruta las barras se conservan; en la query no. `quote` ya usa mayúsculas.
    """
    return quote(value, safe="-_.~" if encode_slash else "-_.~/")


def _utc(moment: datetime) -> datetime:
    # Convención del proyecto: un datetime naive ya está en UTC.
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def amz_date(moment: datetime) -> str:
    return _utc(moment).strftime("%Y%m%dT%H%M%SZ")


def date_stamp(moment: datetime) -> str:
    return _utc(moment).strftime("%Y%m%d")


def credential_scope(stamp: str, region: str, service: str) -> str:
    return f"{stamp}/{region}/{service}/aws4_request"


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def derive_signing_key(secret_access_key: str, stamp: str, region: str, service: str) -> bytes:
    k_date = _hmac(f"AWS4{secret_access_key}".encode(), stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, "aws4_request")


def canonical_query_string(params: Mapping[str, str]) -> str:
    # Se ordena por la clave ya codificada, como pide la especificación.
    pares = sorted((uri_encode(k), uri_encode(v)) for k, v in params.items())
    return "&".join(f"{k}={v}" for k, v in pares)


def canonical_headers(headers: Mapping[str, str]) -> tuple[str, str]:
    """(bloque canónico con salto final, nombres firmados separados por ';')."""
    normalizados = {
        nombre.strip().lower(): " ".join(valor.strip().split())
        for nombre, valor in headers.items()
    }
    nombres = sorted(normalizados)
    bloque = "".join(f"{n}:{normalizados[n]}\n" for n in nombres)
    return bloque, ";".join(nombres)


def canonical_request(
    *,
    method: str,
    canonical_uri: str,
    query: Mapping[str, str],
    headers: Mapping[str, str],
    payload_hash: str,
) -> tuple[str, str]:
    bloque, firmados = canonical_headers(headers)
    texto = "\n".join(
        [
            method.upper(),
            canonical_uri,
            canonical_query_string(query),
            bloque,
            firmados,
            payload_hash,
        ]
    )
    return texto, firmados


def string_to_sign(*, moment: datetime, scope: str, canonical: str) -> str:
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return "\n".join([ALGORITHM, amz_date(moment), scope, digest])


def _firma(
    credentials: SigV4Credentials, moment: datetime, scope: str, canonical: str
) -> str:
    clave = derive_signing_key(
        credentials.secret_access_key,
        date_stamp(moment),
        credentials.region,
        credentials.service,
    )
    texto = string_to_sign(moment=moment, scope=scope, canonical=canonical)
    return hmac.new(clave, texto.encode("utf-8"), hashlib.sha256).hexdigest()


def presign_url(
    *,
    credentials: SigV4Credentials,
    method: str,
    host: str,
    canonical_uri: str,
    signed_headers: Mapping[str, str],
    expires_in_seconds: int,
    now: datetime,
    scheme: str = "https",
) -> str:
    """URL prefirmada. `host` se firma siempre; `signed_headers` son las cabeceras que el
    cliente DEBE mandar tal cual (en la subida: `content-length` y `x-amz-checksum-sha256`,
    que atan la URL al tamaño y al contenido declarados)."""
    if not 1 <= expires_in_seconds <= _MAX_EXPIRES:
        raise ValueError(f"expires_in_seconds fuera de rango: {expires_in_seconds}")
    scope = credential_scope(date_stamp(now), credentials.region, credentials.service)
    headers = {"host": host, **{k.lower(): v for k, v in signed_headers.items()}}
    _, firmados = canonical_headers(headers)
    query = {
        "X-Amz-Algorithm": ALGORITHM,
        "X-Amz-Credential": f"{credentials.access_key_id}/{scope}",
        "X-Amz-Date": amz_date(now),
        "X-Amz-Expires": str(expires_in_seconds),
        "X-Amz-SignedHeaders": firmados,
    }
    canonical, _ = canonical_request(
        method=method,
        canonical_uri=canonical_uri,
        query=query,
        headers=headers,
        payload_hash=UNSIGNED_PAYLOAD,
    )
    firma = _firma(credentials, now, scope, canonical)
    return f"{scheme}://{host}{canonical_uri}?{canonical_query_string(query)}&X-Amz-Signature={firma}"


def sign_request_headers(
    *,
    credentials: SigV4Credentials,
    method: str,
    host: str,
    canonical_uri: str,
    query: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
    payload_hash: str = EMPTY_PAYLOAD_SHA256,
    now: datetime,
) -> dict[str, str]:
    """Cabeceras para una petición directa (HEAD, GET, PUT de copia y DELETE), con Authorization.

    Devuelve también `host`: así lo que viaja es exactamente lo que se firmó.
    """
    scope = credential_scope(date_stamp(now), credentials.region, credentials.service)
    firmadas = {
        **{k.lower(): v for k, v in (headers or {}).items()},
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date(now),
    }
    canonical, firmados = canonical_request(
        method=method,
        canonical_uri=canonical_uri,
        query=query or {},
        headers=firmadas,
        payload_hash=payload_hash,
    )
    firma = _firma(credentials, now, scope, canonical)
    return {
        **firmadas,
        "authorization": (
            f"{ALGORITHM} Credential={credentials.access_key_id}/{scope},"
            f"SignedHeaders={firmados},Signature={firma}"
        ),
    }
