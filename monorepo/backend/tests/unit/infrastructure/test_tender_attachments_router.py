"""Rutas de los anexos de una licitación: la lista oficial y la subida manual.

`list_synced_at` nulo se distingue de "sin anexos": la interfaz dice cosas
distintas en cada caso, y el contrato lo tiene que conservar. Los errores de la
subida llevan un `code` estable que el frontend usa para decidir qué mostrar, y
ningún mensaje de 403 puede contener "revocado": el cliente lo trata como cierre
de sesión.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.application.services.attachment_storage import AttachmentStorageError
from app.application.use_cases.tender_attachments.get_tender_attachments import (
    AttachmentFileView,
    OfficialAttachmentView,
    TenderAttachmentsResult,
    UploadQuota,
    WorkspaceAccess,
)
from app.application.use_cases.tender_attachments.request_attachment_upload import (
    UploadDeduplicated,
    UploadTicket,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
)
from app.domain.entities.supplier_member import MemberRole, WorkspaceContext
from app.domain.entities.tender_attachment import AttachmentStatus, OfficialAttachment
from app.domain.errors.attachment_errors import (
    AttachmentAlreadyUploaded,
    AttachmentExtensionMismatch,
    AttachmentFileIsShared,
    AttachmentFileNotFound,
    AttachmentNameMismatch,
    AttachmentNotFound,
    AttachmentStorageUnavailable,
    AttachmentTooLarge,
    ConcurrentUploadConflict,
    NotAttachmentFileOwner,
    UploadedObjectMissing,
    UploadNotFound,
    UploadNotInProgress,
    UploadQuotaExceeded,
    UploadVerificationFailed,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.routers.tender_attachments import (
    create_tender_attachments_router,
)
from tests.unit.application.attachment_file_fakes import canonico

SINCRONIZADA = datetime(2026, 9, 28, 16, 28)
AHORA = datetime(2026, 10, 3, 15, 0)
SHA = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79"


def _anexo(tender_id):
    return OfficialAttachment(
        id=uuid4(),
        tender_id=tender_id,
        mp_document_id=1931002,
        name="Anexo 3 Composición personalidad juridica.xlsx",
        name_normalized="anexo 3 composicion personalidad juridica.xlsx",
        ext="xlsx",
        first_seen_at=SINCRONIZADA,
        last_seen_at=SINCRONIZADA,
    )


@pytest.fixture
def api():
    tender_id = uuid4()
    anexo = _anexo(tender_id)
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
                "name_normalized": "anexo 3 composicion personalidad juridica.xlsx",
                "ext": "xlsx",
                "status": "missing",
                "file": None,
                "processing": None,
            }
        ],
        "list_synced_at": "2026-09-28T16:28:00Z",
        "quota": None,
        "can_upload": False,
        "max_upload_size_bytes": 52428800,
        "processing_enabled": False,
    }
    api.use_case.execute.assert_awaited_once_with(api.tender_id, access=None)


def test_una_lista_sin_sincronizar_devuelve_null(api):
    api.use_case.execute.return_value = TenderAttachmentsResult(
        official=[], list_synced_at=None
    )

    respuesta = api.client.get(api.path)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "official": [],
        "list_synced_at": None,
        "quota": None,
        "can_upload": False,
        "max_upload_size_bytes": 52428800,
        "processing_enabled": False,
    }


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


# --- Subida manual ---

WS = uuid4()
USER = uuid4()
PERMISOS_MIEMBRO = [
    "view_matches",
    "save_tenders",
    "chat_assistant",
    "deep_analysis",
    "upload_attachments",
]


def _archivo(tender_id, *, ws=WS) -> AttachmentFile:
    return AttachmentFile(
        id=uuid4(),
        tender_attachment_id=uuid4(),
        tender_id=tender_id,
        sha256=SHA,
        size_bytes=2048,
        storage_key=f"private/{ws}/{SHA}.xlsx",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=USER,
        workspace_id=ws,
        status=AttachmentFileStatus.STORED,
        created_at=AHORA,
    )


@pytest.fixture
def subidas():
    tender_id = uuid4()
    anexo = _anexo(tender_id)
    contexto = SimpleNamespace(
        valor=WorkspaceContext(
            user_id=USER,
            active_supplier_id=WS,
            active_supplier_name="Empresa",
            role=MemberRole.MEMBER,
            permissions=list(PERMISOS_MIEMBRO),
        )
    )
    listar, pedir, completar, borrar = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    listar.execute.return_value = TenderAttachmentsResult(
        official=[OfficialAttachmentView(anexo, AttachmentStatus.MISSING)],
        list_synced_at=SINCRONIZADA,
        quota=UploadQuota(used=3, limit=100),
        can_upload=True,
    )
    pedir.execute.return_value = UploadTicket(
        upload_id=uuid4(),
        url="https://almacen.test/put?firma=x",
        method="PUT",
        headers={"x-amz-checksum-sha256": "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k=",
                 "Content-Type": "application/pdf"},
        expires_at=AHORA,
    )
    completar.execute.return_value = _archivo(tender_id)
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=USER)

    def workspace():
        return contexto.valor

    app.include_router(
        create_tender_attachments_router(
            current_user,
            lambda: listar,
            get_optional_workspace_context=workspace,
            get_current_workspace_context=workspace,
            get_request_upload_use_case=lambda: pedir,
            get_complete_upload_use_case=lambda: completar,
            get_delete_file_use_case=lambda: borrar,
        )
    )
    return SimpleNamespace(
        client=TestClient(app),
        app=app,
        contexto=contexto,
        listar=listar,
        pedir=pedir,
        completar=completar,
        borrar=borrar,
        anexo=anexo,
        tender_id=tender_id,
        url_pedir=f"/tenders/{tender_id}/attachments/{anexo.id}/upload-url",
        url_completar=lambda upload_id: (
            f"/tenders/{tender_id}/attachments/uploads/{upload_id}/complete"
        ),
        url_borrar=lambda file_id: (
            f"/tenders/{tender_id}/attachments/files/{file_id}"
        ),
        cuerpo={
            "file_name": "anexo 3 composicion personalidad juridica (1).XLSX",
            "size_bytes": 4,
            "mime": "application/pdf",
            "sha256": SHA,
        },
    )


def test_pedir_la_url_responde_201_con_el_ticket(subidas):
    respuesta = subidas.client.post(subidas.url_pedir, json=subidas.cuerpo)

    assert respuesta.status_code == 201
    ticket = subidas.pedir.execute.return_value
    assert respuesta.json() == {
        "deduplicated": False,
        "upload_id": str(ticket.upload_id),
        "url": "https://almacen.test/put?firma=x",
        "method": "PUT",
        "headers": {
            "x-amz-checksum-sha256": "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k=",
            "Content-Type": "application/pdf",
        },
        "expires_at": "2026-10-03T15:00:00Z",
    }
    pedido = subidas.pedir.execute.await_args.args[0]
    assert pedido.tender_id == subidas.tender_id
    assert pedido.attachment_id == subidas.anexo.id
    assert pedido.workspace_id == WS
    assert pedido.user_id == USER
    assert pedido.file_name == subidas.cuerpo["file_name"]
    assert pedido.size_bytes == 4


def test_si_ya_existe_el_archivo_responde_200_con_el_archivo(subidas):
    archivo = _archivo(subidas.tender_id)
    subidas.pedir.execute.return_value = UploadDeduplicated(archivo)

    respuesta = subidas.client.post(subidas.url_pedir, json=subidas.cuerpo)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "deduplicated": True,
        "file": {
            "id": str(archivo.id),
            "size_bytes": 2048,
            "source": "manual",
            "visibility": "private",
            "trust": "pending",
            "status": "stored",
            "is_mine": True,
            "created_at": "2026-10-03T15:00:00Z",
            "status_reason": None,
        },
    }


def test_un_sha256_en_mayusculas_llega_en_minusculas(subidas):
    subidas.client.post(subidas.url_pedir, json={**subidas.cuerpo, "sha256": SHA.upper()})

    assert subidas.pedir.execute.await_args.args[0].sha256 == SHA


@pytest.mark.parametrize(
    "cambio",
    [
        {"sha256": "xyz"},
        {"size_bytes": 0},
        {"file_name": ""},
        {"file_name": "x" * 256},
    ],
)
def test_un_cuerpo_invalido_es_422_y_no_llega_al_caso_de_uso(subidas, cambio):
    respuesta = subidas.client.post(subidas.url_pedir, json={**subidas.cuerpo, **cambio})

    assert respuesta.status_code == 422
    subidas.pedir.execute.assert_not_awaited()


def test_un_archivo_enorme_no_es_422_sino_un_error_del_caso_de_uso(subidas):
    # El tope lo decide el caso de uso (413), no la validación del cuerpo.
    subidas.pedir.execute.side_effect = AttachmentTooLarge(52428800)

    respuesta = subidas.client.post(
        subidas.url_pedir, json={**subidas.cuerpo, "size_bytes": 10**12}
    )

    assert respuesta.status_code == 413


@pytest.mark.parametrize("metodo", ["pedir", "completar", "borrar"])
def test_un_viewer_no_puede_subir_ni_borrar(subidas, metodo):
    subidas.contexto.valor = subidas.contexto.valor.model_copy(
        update={"role": MemberRole.VIEWER, "permissions": ["view_matches"]}
    )
    peticiones = {
        "pedir": lambda: subidas.client.post(subidas.url_pedir, json=subidas.cuerpo),
        "completar": lambda: subidas.client.post(subidas.url_completar(uuid4())),
        "borrar": lambda: subidas.client.delete(subidas.url_borrar(uuid4())),
    }

    respuesta = peticiones[metodo]()

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "permission_denied"
    assert "revocado" not in respuesta.json()["detail"].lower()
    getattr(subidas, metodo).execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "estado", "codigo", "extra"),
    [
        (UploadQuotaExceeded(used=100, limit=100), 403, "quota_exceeded", {"used": 100, "limit": 100}),
        (AttachmentNameMismatch("Bases.pdf"), 422, "attachment_name_mismatch", {"expected_name": "Bases.pdf"}),
        (
            AttachmentExtensionMismatch("pdf", "docx", "Bases.pdf"),
            422,
            "attachment_extension_mismatch",
            {"expected_ext": "pdf", "received_ext": "docx", "expected_name": "Bases.pdf"},
        ),
        (AttachmentTooLarge(52428800), 413, "file_too_large", {"max_size_bytes": 52428800}),
        (AttachmentNotFound(), 404, "attachment_not_found", {}),
        (AttachmentAlreadyUploaded(), 409, "attachment_already_uploaded", {}),
        (ConcurrentUploadConflict(), 409, "upload_in_progress", {}),
        (AttachmentStorageUnavailable(), 503, "storage_unavailable", {}),
        (AttachmentStorageError("boom"), 502, "storage_error", {}),
    ],
)
def test_errores_al_pedir_la_url(subidas, error, estado, codigo, extra):
    subidas.pedir.execute.side_effect = error

    respuesta = subidas.client.post(subidas.url_pedir, json=subidas.cuerpo)

    assert respuesta.status_code == estado
    cuerpo = respuesta.json()
    assert cuerpo["code"] == codigo
    assert isinstance(cuerpo["detail"], str) and cuerpo["detail"]
    assert {k: v for k, v in cuerpo.items() if k not in ("code", "detail")} == extra
    if estado == 403:
        assert "revocado" not in cuerpo["detail"].lower()


def test_completar_informa_la_visibilidad_efectiva_del_aporte_ya_corroborado(subidas):
    # La fila de la empresa sigue siendo privada; su contenido ya lo ven todas. La
    # etiqueta del panel sale de `visibility`, así que el backend manda la efectiva.
    propio = _archivo(subidas.tender_id).model_copy(update={"trust": AttachmentTrust.CORROBORATED})
    subidas.completar.execute.return_value = propio

    respuesta = subidas.client.post(subidas.url_completar(propio.id))

    assert respuesta.status_code == 200
    assert respuesta.json()["visibility"] == "shared"
    assert respuesta.json()["trust"] == "corroborated"
    assert respuesta.json()["is_mine"] is True


def test_completar_un_aporte_sin_confirmar_sigue_privado(subidas):
    respuesta = subidas.client.post(
        subidas.url_completar(subidas.completar.execute.return_value.id)
    )

    assert respuesta.json()["visibility"] == "private"
    assert respuesta.json()["trust"] == "pending"


def test_completar_responde_el_archivo_guardado(subidas):
    archivo = subidas.completar.execute.return_value

    respuesta = subidas.client.post(subidas.url_completar(archivo.id))

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == str(archivo.id)
    assert respuesta.json()["is_mine"] is True
    assert respuesta.json()["status"] == "stored"
    subidas.completar.execute.assert_awaited_once_with(
        tender_id=subidas.tender_id, upload_id=archivo.id, workspace_id=WS
    )


@pytest.mark.parametrize(
    ("error", "estado", "codigo"),
    [
        (UploadNotFound(), 404, "upload_not_found"),
        (UploadNotInProgress(), 409, "upload_not_in_progress"),
        (UploadedObjectMissing(), 409, "object_missing"),
        (AttachmentStorageUnavailable(), 503, "storage_unavailable"),
        (AttachmentStorageError("boom"), 502, "storage_error"),
    ],
)
def test_errores_al_completar(subidas, error, estado, codigo):
    subidas.completar.execute.side_effect = error

    respuesta = subidas.client.post(subidas.url_completar(uuid4()))

    assert respuesta.status_code == estado
    assert respuesta.json()["code"] == codigo


def test_completar_con_verificacion_fallida_es_422(subidas):
    rechazado = _archivo(subidas.tender_id)
    subidas.completar.execute.side_effect = UploadVerificationFailed(rechazado)

    respuesta = subidas.client.post(subidas.url_completar(rechazado.id))

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "upload_verification_failed"


def test_borrar_responde_204_sin_cuerpo(subidas):
    file_id = uuid4()

    respuesta = subidas.client.delete(subidas.url_borrar(file_id))

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    subidas.borrar.execute.assert_awaited_once_with(
        tender_id=subidas.tender_id, file_id=file_id, workspace_id=WS
    )


@pytest.mark.parametrize(
    ("error", "estado", "codigo"),
    [
        (AttachmentFileNotFound(), 404, "file_not_found"),
        (NotAttachmentFileOwner(), 403, "not_owner"),
        (AttachmentFileIsShared(), 409, "file_is_shared"),
        (AttachmentStorageUnavailable(), 503, "storage_unavailable"),
        (AttachmentStorageError("boom"), 502, "storage_error"),
    ],
)
def test_errores_al_borrar(subidas, error, estado, codigo):
    subidas.borrar.execute.side_effect = error

    respuesta = subidas.client.delete(subidas.url_borrar(uuid4()))

    assert respuesta.status_code == estado
    assert respuesta.json()["code"] == codigo
    if estado == 403:
        assert "revocado" not in respuesta.json()["detail"].lower()


def test_la_lista_con_empresa_informa_permiso_cupo_y_archivo_propio(subidas):
    archivo = _archivo(subidas.tender_id)
    subidas.listar.execute.return_value = TenderAttachmentsResult(
        official=[
            OfficialAttachmentView(
                subidas.anexo, AttachmentStatus.STORED, AttachmentFileView(archivo, True)
            )
        ],
        list_synced_at=SINCRONIZADA,
        quota=UploadQuota(used=3, limit=100),
        can_upload=True,
    )

    respuesta = subidas.client.get(f"/tenders/{subidas.tender_id}/attachments")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["quota"] == {"used": 3, "limit": 100}
    assert cuerpo["can_upload"] is True
    assert cuerpo["official"][0]["status"] == "stored"
    assert cuerpo["official"][0]["file"]["is_mine"] is True
    subidas.listar.execute.assert_awaited_once_with(
        subidas.tender_id, access=WorkspaceAccess(WS, True)
    )


def test_la_lista_muestra_la_version_canonica_como_compartida_y_ajena(subidas):
    compartida = canonico(
        tender_attachment_id=subidas.anexo.id, tender_id=subidas.tender_id, sha256=SHA
    )
    subidas.listar.execute.return_value = TenderAttachmentsResult(
        official=[
            OfficialAttachmentView(
                subidas.anexo, AttachmentStatus.STORED, AttachmentFileView(compartida, False)
            )
        ],
        list_synced_at=SINCRONIZADA,
        can_upload=True,
    )

    respuesta = subidas.client.get(f"/tenders/{subidas.tender_id}/attachments")

    archivo = respuesta.json()["official"][0]["file"]
    assert archivo["is_mine"] is False
    assert archivo["visibility"] == "shared"
    # Nunca se informa quién subió un archivo compartido.
    assert set(archivo) == {
        "id",
        "size_bytes",
        "source",
        "visibility",
        "trust",
        "status",
        "is_mine",
        "created_at",
        "status_reason",
    }


def test_la_lista_informa_la_visibilidad_efectiva_del_aporte_propio_corroborado(subidas):
    propio = _archivo(subidas.tender_id).model_copy(update={"trust": AttachmentTrust.CORROBORATED})
    subidas.listar.execute.return_value = TenderAttachmentsResult(
        official=[
            OfficialAttachmentView(
                subidas.anexo, AttachmentStatus.STORED, AttachmentFileView(propio, True)
            )
        ],
        list_synced_at=SINCRONIZADA,
        can_upload=True,
    )

    respuesta = subidas.client.get(f"/tenders/{subidas.tender_id}/attachments")

    assert respuesta.json()["official"][0]["file"]["visibility"] == "shared"


def test_la_lista_para_un_viewer_pasa_can_upload_falso(subidas):
    subidas.contexto.valor = subidas.contexto.valor.model_copy(
        update={"role": MemberRole.VIEWER, "permissions": ["view_matches"]}
    )

    subidas.client.get(f"/tenders/{subidas.tender_id}/attachments")

    subidas.listar.execute.assert_awaited_once_with(
        subidas.tender_id, access=WorkspaceAccess(WS, False)
    )


def test_sin_empresa_activa_la_lista_se_pide_sin_acceso(subidas):
    # `get_optional_workspace_context` devuelve None cuando no hay empresa.
    app = FastAPI()
    tender_id = subidas.tender_id
    app.include_router(
        create_tender_attachments_router(
            lambda: SimpleNamespace(id=USER),
            lambda: subidas.listar,
            get_optional_workspace_context=lambda: None,
        )
    )

    TestClient(app).get(f"/tenders/{tender_id}/attachments")

    subidas.listar.execute.assert_awaited_once_with(tender_id, access=None)


def test_las_rutas_de_escritura_solo_existen_con_el_contexto_de_empresa(api):
    paths = api.app.openapi()["paths"]

    assert list(paths) == ["/tenders/{tender_id}/attachments"]


def test_las_rutas_de_subida_estan_documentadas_en_openapi(subidas):
    paths = subidas.app.openapi()["paths"]

    pedir = paths["/tenders/{tender_id}/attachments/{attachment_id}/upload-url"]["post"]
    completar = paths["/tenders/{tender_id}/attachments/uploads/{upload_id}/complete"]["post"]
    borrar = paths["/tenders/{tender_id}/attachments/files/{file_id}"]["delete"]

    assert pedir["summary"] == "Pedir una URL para subir un anexo"
    assert completar["summary"] == "Confirmar la subida de un anexo"
    assert borrar["summary"] == "Borrar un archivo de anexo de la empresa"
    for operacion in (pedir, completar, borrar):
        assert operacion["tags"] == ["Tender attachments"]
    assert {"200", "201", "403", "404", "409", "413", "422", "502", "503"} <= set(
        pedir["responses"]
    )
    assert {"200", "403", "404", "409", "422", "502", "503"} <= set(completar["responses"])
    assert {"204", "403", "404", "409", "502", "503"} <= set(borrar["responses"])
