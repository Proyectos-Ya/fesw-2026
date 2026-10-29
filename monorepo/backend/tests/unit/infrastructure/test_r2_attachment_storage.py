"""Adaptador de Cloudflare R2: solo habla S3 firmado, sin red real (respx).

Las firmas de las peticiones directas están fijadas con valores dorados
calculados con la implementación de referencia: si cambia cualquier cabecera
firmada, el test lo delata antes de que R2 responda 403 en producción.
"""

from datetime import datetime

import httpx
import pytest
import respx

from app.application.services.attachment_storage import (
    AttachmentStorageError,
    StoredObjectInfo,
)
from app.infrastructure.services.attachments.r2_attachment_storage import (
    R2AttachmentStorage,
)

AHORA = datetime(2026, 10, 3, 12, 0)
ACCOUNT = "0123456789abcdef0123456789abcdef"
HOST = f"{ACCOUNT}.r2.cloudflarestorage.com"
BUCKET = "chiripa-anexos"
HOLA_HEX = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79"
HOLA_B64 = "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k="
KEY = f"private/11111111-1111-1111-1111-111111111111/{HOLA_HEX}.pdf"
URL_OBJETO = f"https://{HOST}/{BUCKET}/{KEY}"


def _almacenamiento() -> R2AttachmentStorage:
    return R2AttachmentStorage(
        account_id=ACCOUNT,
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        bucket=BUCKET,
        clock=lambda: AHORA,
    )


def test_presign_put_ata_tamano_y_checksum() -> None:
    subida = _almacenamiento().presign_put(
        key=KEY,
        size_bytes=4,
        sha256_hex=HOLA_HEX,
        content_type="application/pdf",
        expires_in_seconds=900,
        now=AHORA,
    )

    assert subida.url == (
        f"https://{HOST}/{BUCKET}/{KEY}"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
        "&X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20261003%2Fauto%2Fs3%2Faws4_request"
        "&X-Amz-Date=20261003T120000Z&X-Amz-Expires=900"
        "&X-Amz-SignedHeaders=content-length%3Bhost%3Bx-amz-checksum-sha256"
        # Es el vector dorado de test_sigv4: mismo host, misma ruta y mismas cabeceras firmadas.
        "&X-Amz-Signature=6166142c10c95335759733a85859489d316b54ba900682be9c39ef6a72127a53"
    )
    assert subida.method == "PUT"
    # Content-Length no va acá: es una cabecera prohibida en el navegador, que la pone sola.
    assert subida.headers == {
        "x-amz-checksum-sha256": HOLA_B64,
        "Content-Type": "application/pdf",
    }
    assert subida.expires_at == datetime(2026, 10, 3, 12, 15)


@respx.mock
async def test_head_informa_tamano_y_checksum() -> None:
    ruta = respx.head(URL_OBJETO).mock(
        return_value=httpx.Response(
            200, headers={"content-length": "4", "x-amz-checksum-sha256": HOLA_B64}
        )
    )

    info = await _almacenamiento().head(KEY)

    assert info == StoredObjectInfo(size_bytes=4, sha256_hex=HOLA_HEX)
    enviada = ruta.calls.last.request
    assert enviada.headers["x-amz-checksum-mode"] == "ENABLED"
    assert enviada.headers["x-amz-date"] == "20261003T120000Z"
    assert enviada.headers["authorization"] == _autorizacion_dorada_del_head()


def _autorizacion_dorada_del_head() -> str:
    return (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20261003/auto/s3/aws4_request,"
        "SignedHeaders=host;x-amz-checksum-mode;x-amz-content-sha256;x-amz-date,"
        "Signature=4499d3c30368ec7bf8b33f4e14990c682c2f34f63b59d2035286dcee705cc017"
    )


@respx.mock
async def test_head_sin_checksum() -> None:
    respx.head(URL_OBJETO).mock(
        return_value=httpx.Response(200, headers={"content-length": "4"})
    )

    info = await _almacenamiento().head(KEY)

    assert info is not None
    assert info.sha256_hex is None
    assert info.size_bytes == 4


@respx.mock
async def test_head_de_un_objeto_que_no_existe_es_none() -> None:
    respx.head(URL_OBJETO).mock(return_value=httpx.Response(404))

    assert await _almacenamiento().head(KEY) is None


@respx.mock
async def test_head_con_error_del_servidor_lanza() -> None:
    respx.head(URL_OBJETO).mock(return_value=httpx.Response(500))

    with pytest.raises(AttachmentStorageError):
        await _almacenamiento().head(KEY)


@respx.mock
async def test_head_sin_red_lanza_error_de_almacenamiento() -> None:
    respx.head(URL_OBJETO).mock(side_effect=httpx.ConnectError("sin red"))

    with pytest.raises(AttachmentStorageError):
        await _almacenamiento().head(KEY)


@respx.mock
async def test_get_devuelve_los_bytes() -> None:
    respx.get(URL_OBJETO).mock(return_value=httpx.Response(200, content=b"hola"))

    assert await _almacenamiento().get_bytes(KEY) == b"hola"


@respx.mock
async def test_get_de_un_objeto_que_no_existe_lanza() -> None:
    respx.get(URL_OBJETO).mock(return_value=httpx.Response(404))

    with pytest.raises(AttachmentStorageError):
        await _almacenamiento().get_bytes(KEY)


@respx.mock
async def test_copy_firma_el_origen_y_acepta_200() -> None:
    destino = f"shared/t/1/{HOLA_HEX}.pdf"
    ruta = respx.put(f"https://{HOST}/{BUCKET}/{destino}").mock(
        return_value=httpx.Response(200, content=b"<CopyObjectResult/>")
    )

    await _almacenamiento().copy(source_key=KEY, destination_key=destino)

    assert ruta.calls.last.request.headers["x-amz-copy-source"] == f"/{BUCKET}/{KEY}"


@respx.mock
async def test_copy_con_200_que_trae_un_error_lanza() -> None:
    # S3 puede responder 200 con un <Error> en el cuerpo si la copia falla a medias.
    destino = f"shared/t/1/{HOLA_HEX}.pdf"
    respx.put(f"https://{HOST}/{BUCKET}/{destino}").mock(
        return_value=httpx.Response(
            200, content=b"<Error><Code>InternalError</Code></Error>"
        )
    )

    with pytest.raises(AttachmentStorageError):
        await _almacenamiento().copy(source_key=KEY, destination_key=destino)


@respx.mock
@pytest.mark.parametrize("codigo", [204, 404])
async def test_delete_es_idempotente(codigo: int) -> None:
    respx.delete(URL_OBJETO).mock(return_value=httpx.Response(codigo))

    await _almacenamiento().delete(KEY)


@respx.mock
async def test_delete_prohibido_lanza() -> None:
    respx.delete(URL_OBJETO).mock(return_value=httpx.Response(403))

    with pytest.raises(AttachmentStorageError):
        await _almacenamiento().delete(KEY)
