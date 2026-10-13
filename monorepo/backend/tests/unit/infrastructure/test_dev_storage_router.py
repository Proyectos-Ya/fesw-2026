"""PUT /dev-storage/...: el receptor de subidas del disco local, solo en desarrollo.

Es la contraparte de la URL firmada de R2: no tiene sesión, así que lo único que
autoriza la escritura es el token HMAC, que ata clave, tamaño y huella. El cuerpo
se lee por partes (nunca `request.body()`: cargaría 50 MB en memoria) y se
verifica mientras llega.
"""

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.infrastructure.middleware import register_middleware
from app.infrastructure.routers.dev_storage import create_dev_storage_router
from app.infrastructure.services.attachments.checksums import sha256_hex_a_base64
from app.infrastructure.services.attachments.local_attachment_storage import (
    LocalDiskAttachmentStorage,
)

AHORA = datetime(2026, 10, 3, 12, 0)
HOLA = b"hola"
HOLA_HEX = hashlib.sha256(HOLA).hexdigest()
KEY = f"private/11111111-1111-1111-1111-111111111111/{HOLA_HEX}.pdf"


class Escenario:
    def __init__(self, raiz: Path) -> None:
        self.reloj = AHORA
        self.raiz = raiz
        self.storage = LocalDiskAttachmentStorage(
            root=raiz, public_base_url="http://localhost:8000", secret=b"secreto"
        )
        self.app = FastAPI()
        self.app.include_router(
            create_dev_storage_router(self.storage, clock=lambda: self.reloj)
        )
        self.client = TestClient(self.app)

    def url(self, *, size: int = 4, sha: str = HOLA_HEX) -> str:
        firmada = self.storage.presign_put(
            key=KEY,
            size_bytes=size,
            sha256_hex=sha,
            content_type="application/pdf",
            expires_in_seconds=900,
            now=AHORA,
        )
        partes = urlsplit(firmada.url)
        return f"{partes.path}?{partes.query}"

    def cabeceras(self, sha: str = HOLA_HEX) -> dict[str, str]:
        return {
            "x-amz-checksum-sha256": sha256_hex_a_base64(sha),
            "content-type": "application/pdf",
        }


@pytest.fixture
def escenario(tmp_path: Path) -> Escenario:
    return Escenario(tmp_path)


def test_un_put_valido_guarda_el_archivo(escenario: Escenario) -> None:
    respuesta = escenario.client.put(
        escenario.url(), content=HOLA, headers=escenario.cabeceras()
    )

    assert respuesta.status_code == 200
    assert escenario.storage.ruta_de(KEY).read_bytes() == HOLA


def test_un_token_vencido_es_403(escenario: Escenario) -> None:
    url = escenario.url()
    escenario.reloj = AHORA + timedelta(minutes=16)

    respuesta = escenario.client.put(url, content=HOLA, headers=escenario.cabeceras())

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "signature_mismatch"
    assert not escenario.storage.ruta_de(KEY).exists()


def test_un_tamano_alterado_en_la_url_es_403(escenario: Escenario) -> None:
    url = escenario.url().replace("size=4", "size=5")

    respuesta = escenario.client.put(url, content=HOLA, headers=escenario.cabeceras())

    assert respuesta.status_code == 403


def test_el_checksum_de_la_cabecera_incorrecto_es_400(escenario: Escenario) -> None:
    cabeceras = escenario.cabeceras(sha="0" * 64)

    respuesta = escenario.client.put(escenario.url(), content=HOLA, headers=cabeceras)

    assert respuesta.status_code == 400
    assert respuesta.json()["code"] == "bad_digest"


def test_sin_la_cabecera_de_checksum_es_400(escenario: Escenario) -> None:
    respuesta = escenario.client.put(escenario.url(), content=HOLA)

    assert respuesta.status_code == 400


def test_un_cuerpo_de_otro_tamano_es_400(escenario: Escenario) -> None:
    respuesta = escenario.client.put(
        escenario.url(), content=b"hola!", headers=escenario.cabeceras()
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["code"] == "size_mismatch"
    assert not escenario.storage.ruta_de(KEY).exists()


def test_mismo_tamano_pero_otros_bytes_es_400_y_no_deja_rastro(
    escenario: Escenario, tmp_path: Path
) -> None:
    respuesta = escenario.client.put(
        escenario.url(), content=b"chao", headers=escenario.cabeceras()
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["code"] == "bad_digest"
    assert not escenario.storage.ruta_de(KEY).exists()
    assert list(tmp_path.rglob("*.part")) == []


def test_sin_content_length_es_411(escenario: Escenario) -> None:
    # Un cuerpo sin tamaño (chunked) no se puede acotar antes de leerlo.
    def partes():
        yield b"ho"
        yield b"la"

    respuesta = escenario.client.put(
        escenario.url(), content=partes(), headers=escenario.cabeceras()
    )

    assert respuesta.status_code == 411


def test_el_navegador_puede_hacer_el_preflight_cors_desde_localhost_3000(
    escenario: Escenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    # El PUT es cross-origin (:3000 -> :8000): sin esto el navegador lo bloquea.
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:3000")
    register_middleware(escenario.app)

    respuesta = TestClient(escenario.app).options(
        escenario.url(),
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,x-amz-checksum-sha256",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_la_ruta_esta_documentada_en_openapi(escenario: Escenario) -> None:
    operacion = escenario.app.openapi()["paths"]["/dev-storage/{key}"]["put"]

    assert operacion["tags"] == ["Dev storage"]
    assert operacion["summary"] == "Recibir un anexo en el disco local (solo desarrollo)"
