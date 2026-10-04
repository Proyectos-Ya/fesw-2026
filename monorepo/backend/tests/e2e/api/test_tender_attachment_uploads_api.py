"""Subida manual de anexos de punta a punta por HTTP (plan 233, decisión 2).

Sesión de Supabase y resolución de la empresa activa son las reales; solo el
almacenamiento, los repositorios de anexos y los de usuarios son dobles en memoria.
Lo que se comprueba: que el permiso `upload_attachments` llega de verdad desde el
rol hasta la ruta, y que el cupo de la empresa se refleja al volver a listar.
"""

import hashlib
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app import bootstrap
from app.config import settings
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.main import app
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
)

NOMBRE_OFICIAL = "Anexo 3 Composición personalidad juridica.xlsx"
DESCARGADO = "anexo 3 composicion personalidad juridica (1).XLSX"
SHA = hashlib.sha256(b"hola").hexdigest()
SUB_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUB_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


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

    cuerpo = {
        "file_name": DESCARGADO,
        "size_bytes": 4,
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "sha256": SHA,
    }


@pytest_asyncio.fixture
async def anexos(api: AsyncClient) -> Anexos:
    # El fixture `api` limpia los overrides al terminar el test.
    mundo = Anexos()
    await mundo.preparar()
    app.dependency_overrides[bootstrap.get_tender_attachment_repo] = lambda: mundo.repo
    app.dependency_overrides[bootstrap.get_attachment_file_repo] = lambda: mundo.archivos
    app.dependency_overrides[bootstrap.get_attachment_storage] = lambda: mundo.storage
    return mundo


def _cabeceras(api: AsyncClient, sub: str, email: str) -> dict[str, str]:
    api.directorio_de_identidad.confirmar(sub)
    token = api.claves.token(sub=sub, email=email, user_metadata={"full_name": email})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_un_admin_pide_la_url_y_la_lista_refleja_el_cupo(
    api: AsyncClient, anexos: Anexos
):
    headers = _cabeceras(api, SUB_A, "admin@test.cl")
    creada = await api.post("/suppliers", json=_empresa("76.123.456-0", "Empresa Uno SpA"), headers=headers)
    assert creada.status_code == 201

    pedida = await api.post(anexos.url_pedir, json=Anexos.cuerpo, headers=headers)

    assert pedida.status_code == 201
    cuerpo = pedida.json()
    assert cuerpo["deduplicated"] is False
    assert cuerpo["method"] == "PUT"

    listada = await api.get(anexos.url_lista, headers=headers)
    assert listada.status_code == 200
    lista = listada.json()
    assert lista["can_upload"] is True
    assert lista["quota"] == {
        "used": 1,
        "limit": settings.attachment_manual_uploads_per_month,
    }
    [anexo] = lista["official"]
    assert anexo["status"] == "uploading"
    assert anexo["file"]["id"] == cuerpo["upload_id"]
    assert anexo["file"]["is_mine"] is True


@pytest.mark.asyncio
async def test_un_viewer_no_puede_subir_y_la_lista_no_se_lo_ofrece(
    api: AsyncClient, anexos: Anexos
):
    headers_a = _cabeceras(api, SUB_A, "user_a@test.cl")
    headers_b = _cabeceras(api, SUB_B, "user_b@test.cl")
    await api.post("/suppliers", json=_empresa("76.123.456-0", "Empresa Uno SpA"), headers=headers_a)
    empresa_2 = await api.post(
        "/suppliers", json=_empresa("77.654.321-7", "Empresa Dos Ltda"), headers=headers_b
    )
    empresa_2_id = empresa_2.json()["id"]
    invitacion = await api.post(
        "/workspaces/invitations",
        json={"supplier_id": empresa_2_id, "email": "user_a@test.cl", "role": "viewer"},
        headers=headers_b,
    )
    assert invitacion.status_code == 201
    aceptada = await api.post(
        "/workspaces/invitations/accept",
        json={"token": invitacion.json()["token"]},
        headers=headers_a,
    )
    assert aceptada.status_code == 200
    cambio = await api.post(
        "/workspaces/switch", json={"supplier_id": empresa_2_id}, headers=headers_a
    )
    assert cambio.status_code == 200
    assert cambio.json()["role"] == "viewer"

    pedida = await api.post(anexos.url_pedir, json=Anexos.cuerpo, headers=headers_a)

    assert pedida.status_code == 403
    assert pedida.json()["code"] == "permission_denied"
    assert "revocado" not in pedida.json()["detail"].lower()
    lista = (await api.get(anexos.url_lista, headers=headers_a)).json()
    assert lista["can_upload"] is False
    assert anexos.archivos.filas == {}
