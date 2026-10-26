"""Almacenamiento en disco local, solo para desarrollo (plan 233, decisión 2).

Imita a R2 lo justo para probar el flujo completo sin credenciales: URL con
token HMAC, verificación de tamaño y huella al escribir, y una ruta que no puede
salirse de la carpeta raíz.
"""

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.application.services.attachment_storage import (
    AttachmentStorageError,
    StoredObjectInfo,
)
from app.infrastructure.services.attachments.local_attachment_storage import (
    ContenidoInvalido,
    LocalDiskAttachmentStorage,
)

AHORA = datetime(2026, 10, 3, 12, 0)
HOLA = b"hola"
HOLA_HEX = hashlib.sha256(HOLA).hexdigest()
KEY = f"private/11111111-1111-1111-1111-111111111111/{HOLA_HEX}.pdf"


def _almacenamiento(raiz: Path) -> LocalDiskAttachmentStorage:
    return LocalDiskAttachmentStorage(
        root=raiz, public_base_url="http://localhost:8000", secret=b"secreto-de-prueba"
    )


async def _partes(*trozos: bytes):
    for trozo in trozos:
        yield trozo


def _presign(almacenamiento: LocalDiskAttachmentStorage):
    return almacenamiento.presign_put(
        key=KEY,
        size_bytes=4,
        sha256_hex=HOLA_HEX,
        content_type="application/pdf",
        expires_in_seconds=900,
        now=AHORA,
    )


def test_la_url_apunta_al_backend_y_lleva_el_token(tmp_path: Path) -> None:
    subida = _presign(_almacenamiento(tmp_path))

    assert subida.url.startswith(f"http://localhost:8000/dev-storage/{KEY}?")
    for parametro in ("expires=", "size=4", f"sha256={HOLA_HEX}", "token="):
        assert parametro in subida.url
    assert subida.method == "PUT"
    # Mismos headers que en R2: el cliente no distingue el adaptador.
    assert subida.headers["Content-Type"] == "application/pdf"
    assert "x-amz-checksum-sha256" in subida.headers
    assert subida.expires_at == AHORA + timedelta(minutes=15)


def _firmar(almacenamiento: LocalDiskAttachmentStorage) -> tuple[int, str]:
    from urllib.parse import parse_qs, urlsplit

    consulta = parse_qs(urlsplit(_presign(almacenamiento).url).query)
    return int(consulta["expires"][0]), consulta["token"][0]


def test_verificar_token_acepta_lo_firmado(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    expires, token = _firmar(almacenamiento)

    assert almacenamiento.verificar_token(
        key=KEY, expires=expires, size=4, sha256_hex=HOLA_HEX, token=token, now=AHORA
    )


def test_verificar_token_rechaza_lo_vencido(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    expires, token = _firmar(almacenamiento)

    assert not almacenamiento.verificar_token(
        key=KEY,
        expires=expires,
        size=4,
        sha256_hex=HOLA_HEX,
        token=token,
        now=AHORA + timedelta(minutes=16),
    )


@pytest.mark.parametrize(
    "cambio",
    [
        {"size": 5},
        {"sha256_hex": "0" * 64},
        {"key": KEY + "x"},
        {"token": "otro"},
    ],
)
def test_verificar_token_rechaza_cualquier_alteracion(
    tmp_path: Path, cambio: dict[str, object]
) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    expires, token = _firmar(almacenamiento)
    valores: dict[str, object] = {
        "key": KEY,
        "expires": expires,
        "size": 4,
        "sha256_hex": HOLA_HEX,
        "token": token,
        "now": AHORA,
    }
    valores.update(cambio)

    assert not almacenamiento.verificar_token(**valores)  # type: ignore[arg-type]


async def test_escribir_deja_el_archivo_y_head_lo_informa(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)

    await almacenamiento.escribir(KEY, _partes(b"ho", b"la"), size=4, sha256_hex=HOLA_HEX)

    assert await almacenamiento.head(KEY) == StoredObjectInfo(4, HOLA_HEX)
    assert await almacenamiento.get_bytes(KEY) == HOLA


async def test_bytes_distintos_con_el_mismo_tamano_no_dejan_rastro(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)

    with pytest.raises(ContenidoInvalido):
        await almacenamiento.escribir(KEY, _partes(b"chao"), size=4, sha256_hex=HOLA_HEX)

    assert await almacenamiento.head(KEY) is None
    assert list(tmp_path.rglob("*.part")) == []


async def test_mas_bytes_que_el_tamano_declarado_lanza(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)

    with pytest.raises(ContenidoInvalido):
        await almacenamiento.escribir(
            KEY, _partes(b"hola", b" mundo"), size=4, sha256_hex=HOLA_HEX
        )

    assert await almacenamiento.head(KEY) is None
    assert list(tmp_path.rglob("*.part")) == []


async def test_menos_bytes_que_el_tamano_declarado_lanza(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)

    with pytest.raises(ContenidoInvalido):
        await almacenamiento.escribir(KEY, _partes(b"ho"), size=4, sha256_hex=HOLA_HEX)

    assert list(tmp_path.rglob("*.part")) == []


async def test_head_de_lo_que_no_existe_es_none(tmp_path: Path) -> None:
    assert await _almacenamiento(tmp_path).head(KEY) is None


async def test_delete_es_idempotente(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    await almacenamiento.escribir(KEY, _partes(HOLA), size=4, sha256_hex=HOLA_HEX)

    await almacenamiento.delete(KEY)
    await almacenamiento.delete(KEY)

    assert await almacenamiento.head(KEY) is None


async def test_copy_duplica_el_objeto(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    await almacenamiento.escribir(KEY, _partes(HOLA), size=4, sha256_hex=HOLA_HEX)
    destino = f"shared/t/1/{HOLA_HEX}.pdf"

    await almacenamiento.copy(source_key=KEY, destination_key=destino)

    assert await almacenamiento.get_bytes(destino) == HOLA
    assert await almacenamiento.get_bytes(KEY) == HOLA


async def test_copy_y_get_de_lo_que_no_existe_lanzan(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)

    with pytest.raises(AttachmentStorageError):
        await almacenamiento.get_bytes(KEY)
    with pytest.raises(AttachmentStorageError):
        await almacenamiento.copy(source_key=KEY, destination_key="otro")


@pytest.mark.parametrize(
    "clave", ["../x", "a//b", "", "a/./b", "a\\b", "a/../../b", "/abs"]
)
def test_ruta_de_rechaza_lo_que_se_sale_de_la_raiz(tmp_path: Path, clave: str) -> None:
    with pytest.raises(ValueError):
        _almacenamiento(tmp_path).ruta_de(clave)


def test_presign_valida_la_clave_temprano(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _almacenamiento(tmp_path).presign_put(
            key="../x",
            size_bytes=4,
            sha256_hex=HOLA_HEX,
            content_type="application/pdf",
            expires_in_seconds=900,
            now=AHORA,
        )


def test_construir_no_crea_la_carpeta(tmp_path: Path) -> None:
    raiz = tmp_path / "no-existe"

    _almacenamiento(raiz)

    assert not raiz.exists()
