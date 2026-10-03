"""GET /tenders/{tender_id}/attachments: la lista oficial de anexos.

`list_synced_at` nulo se distingue de "sin anexos": la interfaz dice cosas
distintas en cada caso, y el contrato lo tiene que conservar.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.application.use_cases.tender_attachments.get_tender_attachments import (
    OfficialAttachmentView,
    TenderAttachmentsResult,
)
from app.domain.entities.tender_attachment import AttachmentStatus, OfficialAttachment
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.routers.tender_attachments import (
    create_tender_attachments_router,
)

SINCRONIZADA = datetime(2026, 9, 28, 16, 28)


@pytest.fixture
def api():
    tender_id = uuid4()
    anexo = OfficialAttachment(
        id=uuid4(),
        tender_id=tender_id,
        mp_document_id=1931002,
        name="Anexo 3 Composición personalidad juridica.xlsx",
        name_normalized="anexo 3 composicion personalidad juridica.xlsx",
        ext="xlsx",
        first_seen_at=SINCRONIZADA,
        last_seen_at=SINCRONIZADA,
    )
    use_case = AsyncMock()
    use_case.execute.return_value = TenderAttachmentsResult(
        official=[OfficialAttachmentView(anexo, AttachmentStatus.MISSING)],
        list_synced_at=SINCRONIZADA,
    )
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=uuid4())

    app.include_router(
        create_tender_attachments_router(current_user, lambda: use_case)
    )
    return SimpleNamespace(
        client=TestClient(app),
        app=app,
        current_user=current_user,
        use_case=use_case,
        anexo=anexo,
        tender_id=tender_id,
        path=f"/tenders/{tender_id}/attachments",
    )


def test_lista_los_anexos_oficiales_con_su_estado_y_la_fecha_en_utc(api):
    respuesta = api.client.get(api.path)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "official": [
            {
                "id": str(api.anexo.id),
                "mp_document_id": 1931002,
                "name": "Anexo 3 Composición personalidad juridica.xlsx",
                "ext": "xlsx",
                "status": "missing",
            }
        ],
        "list_synced_at": "2026-09-28T16:28:00Z",
    }
    api.use_case.execute.assert_awaited_once_with(api.tender_id)


def test_una_lista_sin_sincronizar_devuelve_null(api):
    api.use_case.execute.return_value = TenderAttachmentsResult(
        official=[], list_synced_at=None
    )

    respuesta = api.client.get(api.path)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"official": [], "list_synced_at": None}


def test_licitacion_inexistente_es_404(api):
    api.use_case.execute.side_effect = TenderNotFound(api.tender_id)

    assert api.client.get(api.path).status_code == 404


def test_un_id_que_no_es_uuid_es_422(api):
    respuesta = api.client.get("/tenders/no-es-uuid/attachments")

    assert respuesta.status_code == 422
    api.use_case.execute.assert_not_awaited()


def test_sin_sesion_es_401_y_no_llama_al_caso_de_uso(api):
    def denegado():
        raise HTTPException(401, "No autenticado")

    api.app.dependency_overrides[api.current_user] = denegado

    assert api.client.get(api.path).status_code == 401
    api.use_case.execute.assert_not_awaited()


def test_la_ruta_esta_documentada_en_openapi(api):
    operacion = api.app.openapi()["paths"]["/tenders/{tender_id}/attachments"]["get"]

    assert operacion["summary"] == "Listar los anexos oficiales de una licitación"
    assert operacion["tags"] == ["Tender attachments"]
    assert "404" in operacion["responses"]
