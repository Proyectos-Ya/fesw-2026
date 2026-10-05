"""Anexos compartidos de punta a punta por HTTP (plan 233, decisión 6).

Sesión de Supabase y resolución de la empresa activa son las reales; el
almacenamiento, los repositorios de anexos y la promoción son dobles en memoria
(la promoción real abre su propia sesión de base, que acá no existe).

Lo que se comprueba: dos empresas independientes que suben el mismo archivo lo
comparten; una tercera lo ve sin gastar cupo ni saber quién lo subió; y el archivo
propio ya confirmado deja de poder borrarse.
"""

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app import bootstrap
from app.application.services.attachment_stored_listener import (
    CompositeAttachmentStoredListener,
)
from app.application.services.attachment_visibility_listener import (
    NoopAttachmentVisibilityListener,
)
from app.application.use_cases.tender_attachments.promote_attachment import (
    AttachmentPromotionListener,
    PromoteAttachmentUseCase,
)
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.domain.services.attachment_files import clave_privada
from app.main import app
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
    InMemoryAttachmentTrustRepository,
)

NOMBRE_OFICIAL = "Anexo 3 Composición personalidad juridica.xlsx"
DESCARGADO = "anexo 3 composicion personalidad juridica (1).XLSX"
CONTENIDO = b"hola"
SHA = hashlib.sha256(CONTENIDO).hexdigest()
SUB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
SUB_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
CUERPO = {
    "file_name": DESCARGADO,
    "size_bytes": 4,
    "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "sha256": SHA,
}


def _empresa(rut: str, nombre: str) -> dict:
    return {
        "rut": rut,
        "legal_name": nombre,
        "description": "Empresa especializada en soluciones tecnológicas y consultoría TI.",
        "regions": ["Metropolitana"],
        "sectors": ["Tecnología"],
        "years_experience": 4,
        "num_employees": 15,
    }


class Anexos:
    def __init__(self) -> None:
        self.tender_id = uuid4()
        self.repo = InMemoryTenderAttachmentRepository({"A": self.tender_id})
        self.archivos = InMemoryAttachmentFileRepository()
        self.storage = FakeAttachmentStorage()
        self.anexo_id = None

    async def preparar(self) -> None:
        await self.repo.sync_official_lists(
            {self.tender_id: [DocumentoOficialDTO(mp_document_id=1931002, nombre=NOMBRE_OFICIAL)]},
            visto_en=datetime(2026, 9, 28, 16, 0),
        )
        self.anexo_id = self.repo.filas[(self.tender_id, 1931002)].id

    @property
    def url_pedir(self) -> str:
        return f"/tenders/{self.tender_id}/attachments/{self.anexo_id}/upload-url"

    @property
    def url_lista(self) -> str:
        return f"/tenders/{self.tender_id}/attachments"

    def url_completar(self, upload_id: str) -> str:
        return f"/tenders/{self.tender_id}/attachments/uploads/{upload_id}/complete"

    def url_borrar(self, file_id: str) -> str:
        return f"/tenders/{self.tender_id}/attachments/files/{file_id}"


@pytest_asyncio.fixture
async def anexos(api: AsyncClient) -> Anexos:
    # El fixture `api` limpia los overrides al terminar el test.
    mundo = Anexos()
    await mundo.preparar()
    trust = InMemoryAttachmentTrustRepository(
        files=mundo.archivos, attachments=mundo.repo
    )

    @asynccontextmanager
    async def abrir() -> AsyncIterator[PromoteAttachmentUseCase]:
        yield PromoteAttachmentUseCase(
            trust=trust,
            storage=mundo.storage,
            visibility_listener=NoopAttachmentVisibilityListener(),
        )

    promocion = AttachmentPromotionListener(abrir)
    app.dependency_overrides[bootstrap.get_tender_attachment_repo] = lambda: mundo.repo
    app.dependency_overrides[bootstrap.get_attachment_file_repo] = lambda: mundo.archivos
    app.dependency_overrides[bootstrap.get_attachment_storage] = lambda: mundo.storage
    app.dependency_overrides[bootstrap.get_attachment_stored_listener] = lambda: (
        CompositeAttachmentStoredListener([promocion])
    )
    app.dependency_overrides[bootstrap.get_attachment_deleted_listener] = lambda: promocion
    return mundo


def _cabeceras(api: AsyncClient, sub: str, email: str) -> dict[str, str]:
    api.directorio_de_identidad.confirmar(sub)
    token = api.claves.token(sub=sub, email=email, user_metadata={"full_name": email})
    return {"Authorization": f"Bearer {token}"}


async def _crear_empresa(api: AsyncClient, sub: str, email: str, rut: str) -> tuple[dict, str]:
    headers = _cabeceras(api, sub, email)
    creada = await api.post("/suppliers", json=_empresa(rut, f"Empresa {rut}"), headers=headers)
    assert creada.status_code == 201
    return headers, creada.json()["id"]


async def _subir(api: AsyncClient, anexos: Anexos, headers: dict, empresa_id: str) -> str:
    """Los tres pasos de la subida: URL, PUT del navegador y confirmación."""
    pedida = await api.post(anexos.url_pedir, json=CUERPO, headers=headers)
    assert pedida.status_code == 201
    upload_id = pedida.json()["upload_id"]
    anexos.storage.subir(clave_privada(empresa_id, SHA, "xlsx"), CONTENIDO)
    completada = await api.post(anexos.url_completar(upload_id), headers=headers)
    assert completada.status_code == 200
    return upload_id


async def _archivo_de(api: AsyncClient, anexos: Anexos, headers: dict) -> dict:
    lista = (await api.get(anexos.url_lista, headers=headers)).json()
    [anexo] = lista["official"]
    return anexo


@pytest.mark.asyncio
async def test_dos_empresas_que_suben_lo_mismo_lo_comparten_con_una_tercera(
    api: AsyncClient, anexos: Anexos
):
    headers_a, empresa_a = await _crear_empresa(api, SUB_A, "a@test.cl", "76.123.456-0")
    headers_b, empresa_b = await _crear_empresa(api, SUB_B, "b@test.cl", "77.654.321-7")
    headers_c, _ = await _crear_empresa(api, SUB_C, "c@test.cl", "76.086.428-5")

    upload_a = await _subir(api, anexos, headers_a, empresa_a)
    # Con una sola fuente sigue siendo privado.
    sola = (await _archivo_de(api, anexos, headers_a))["file"]
    assert (sola["visibility"], sola["trust"]) == ("private", "pending")
    assert (await _archivo_de(api, anexos, headers_c))["status"] == "missing"

    await _subir(api, anexos, headers_b, empresa_b)

    # La tercera empresa ve el archivo compartido, sin saber de quién viene.
    de_c = await _archivo_de(api, anexos, headers_c)
    assert de_c["status"] == "stored"
    assert de_c["file"]["is_mine"] is False
    assert de_c["file"]["visibility"] == "shared"
    assert "workspace_id" not in de_c["file"] and "uploader_user_id" not in de_c["file"]
    # La primera ve su propio aporte ya confirmado como compartido.
    de_a = await _archivo_de(api, anexos, headers_a)
    assert de_a["file"]["is_mine"] is True
    assert de_a["file"]["visibility"] == "shared"
    assert de_a["file"]["trust"] == "corroborated"

    # C pide subir el mismo archivo: no hay nada que subir ni cupo que gastar.
    pedida_c = await api.post(anexos.url_pedir, json=CUERPO, headers=headers_c)
    assert pedida_c.status_code == 200
    assert pedida_c.json()["deduplicated"] is True
    cupo_c = (await api.get(anexos.url_lista, headers=headers_c)).json()["quota"]
    assert cupo_c["used"] == 0

    # El aporte propio ya confirmado no se borra: no "descomparte" nada.
    borrar = await api.delete(anexos.url_borrar(upload_a), headers=headers_a)
    assert borrar.status_code == 409
    assert borrar.json()["code"] == "file_is_shared"
    assert upload_a in {str(f) for f in anexos.archivos.filas}


@pytest.mark.asyncio
async def test_borrar_el_aporte_sin_confirmar_funciona_y_avisa_a_la_promocion(
    api: AsyncClient, anexos: Anexos
):
    headers_a, empresa_a = await _crear_empresa(api, SUB_A, "a@test.cl", "76.123.456-0")
    upload_a = await _subir(api, anexos, headers_a, empresa_a)

    borrar = await api.delete(anexos.url_borrar(upload_a), headers=headers_a)

    assert borrar.status_code == 204
    assert (await _archivo_de(api, anexos, headers_a))["status"] == "missing"
