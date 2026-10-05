"""El cableado de la subida manual de anexos en el composition root (plan 233, decisiones 2 y 6).

Qué almacenamiento se elige según el entorno, que el receptor del disco local
(`/dev-storage`) solo existe cuando de verdad se usa el disco local, y que la
promoción a compartido se cuelga de "guardado" y de "borrado" con sesión propia.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from sqlmodel.ext.asyncio.session import AsyncSession

from app import bootstrap
from app.application.services.attachment_deleted_listener import (
    CompositeAttachmentDeletedListener,
)
from app.application.services.attachment_stored_listener import (
    CompositeAttachmentStoredListener,
)
from app.application.services.attachment_visibility_listener import (
    NoopAttachmentVisibilityListener,
)
from app.application.use_cases.tender_attachments.promote_attachment import (
    AttachmentPromotionListener,
)
from app.config import settings
from app.infrastructure.repositories.sql_attachment_file_repository import (
    SqlAttachmentFileRepository,
)
from app.infrastructure.repositories.sql_attachment_trust_repository import (
    SqlAttachmentTrustRepository,
)
from app.infrastructure.services.attachments.local_attachment_storage import (
    LocalDiskAttachmentStorage,
)
from app.infrastructure.services.attachments.r2_attachment_storage import (
    R2AttachmentStorage,
)
from tests.unit.application.fakes import FakeEmbeddingService, FakeRerankerService


def _con_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "r2_account_id", "cuenta")
    monkeypatch.setattr(settings, "r2_access_key_id", "clave")
    monkeypatch.setattr(settings, "r2_secret_access_key", "secreto")
    monkeypatch.setattr(settings, "r2_bucket", "bucket")


def _sin_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    for nombre in ("r2_account_id", "r2_access_key_id", "r2_secret_access_key", "r2_bucket"):
        monkeypatch.setattr(settings, nombre, None)


@pytest.mark.parametrize("es_dev", [True, False])
def test_con_r2_completo_se_usa_r2_tambien_en_desarrollo(monkeypatch, es_dev):
    _con_r2(monkeypatch)
    monkeypatch.setattr(settings, "is_dev", es_dev)

    assert isinstance(bootstrap.build_attachment_storage(), R2AttachmentStorage)


def test_sin_r2_y_en_desarrollo_se_usa_el_disco_local(monkeypatch):
    _sin_r2(monkeypatch)
    monkeypatch.setattr(settings, "is_dev", True)

    almacenamiento = bootstrap.build_attachment_storage()

    assert isinstance(almacenamiento, LocalDiskAttachmentStorage)


def test_sin_r2_y_fuera_de_desarrollo_la_subida_queda_apagada(monkeypatch):
    _sin_r2(monkeypatch)
    monkeypatch.setattr(settings, "is_dev", False)

    assert bootstrap.build_attachment_storage() is None


def _rutas(app: FastAPI) -> set[tuple[str, str]]:
    return {
        (ruta.path, metodo)
        for ruta in app.routes
        for metodo in getattr(ruta, "methods", None) or ()
    }


def _bootstrap(monkeypatch, almacenamiento) -> FastAPI:
    monkeypatch.setattr(bootstrap, "build_embedding_service", FakeEmbeddingService)
    monkeypatch.setattr(bootstrap, "build_reranker_service", FakeRerankerService)
    monkeypatch.setattr(bootstrap, "build_attachment_storage", lambda: almacenamiento)
    app = FastAPI()
    bootstrap.bootstrap(app)
    return app


def test_el_receptor_del_disco_local_se_monta_solo_con_disco_local(monkeypatch, tmp_path):
    local = LocalDiskAttachmentStorage(
        root=tmp_path, public_base_url="http://localhost:8000", secret=b"x"
    )

    app = _bootstrap(monkeypatch, local)

    assert app.state.attachment_storage is local
    assert ("/dev-storage/{key:path}", "PUT") in _rutas(app)
    # Las rutas de escritura de anexos también están.
    assert (
        "/tenders/{tender_id}/attachments/{attachment_id}/upload-url",
        "POST",
    ) in _rutas(app)


@pytest.mark.parametrize("almacenamiento", ["r2", None])
def test_el_receptor_no_se_monta_con_r2_ni_sin_almacenamiento(monkeypatch, almacenamiento):
    if almacenamiento == "r2":
        almacenamiento = R2AttachmentStorage(
            account_id="c", access_key_id="a", secret_access_key="s", bucket="b"
        )

    app = _bootstrap(monkeypatch, almacenamiento)

    assert ("/dev-storage/{key:path}", "PUT") not in _rutas(app)


def test_el_getter_lee_el_almacenamiento_de_app_state():
    class Peticion:
        class app:  # noqa: N801
            class state:  # noqa: N801
                attachment_storage = "el-almacenamiento"

    assert bootstrap.get_attachment_storage(Peticion()) == "el-almacenamiento"  # type: ignore[arg-type]


def test_sin_almacenamiento_en_app_state_el_getter_devuelve_none():
    class Peticion:
        class app:  # noqa: N801
            class state:  # noqa: N801
                pass

    assert bootstrap.get_attachment_storage(Peticion()) is None  # type: ignore[arg-type]


def test_las_dependencias_se_arman_con_lo_recibido():
    sesion = AsyncMock(spec=AsyncSession)
    archivos = bootstrap.get_attachment_file_repo(sesion)
    promocion = bootstrap.get_attachment_promotion_listener(
        None, bootstrap.get_attachment_visibility_listener()
    )
    guardado = bootstrap.get_attachment_stored_listener(promocion)
    borrado = bootstrap.get_attachment_deleted_listener(promocion)

    assert isinstance(archivos, SqlAttachmentFileRepository)

    pedir = bootstrap.get_request_attachment_upload_use_case(
        bootstrap.get_tender_attachment_repo(sesion), archivos, None, guardado
    )
    completar = bootstrap.get_complete_attachment_upload_use_case(archivos, None, guardado)
    borrar = bootstrap.get_delete_attachment_file_use_case(archivos, None, borrado)

    assert pedir.files is archivos and pedir.storage is None
    assert pedir.uploads_per_month == settings.attachment_manual_uploads_per_month
    assert pedir.listener is guardado
    assert completar.files is archivos and completar.listener is guardado
    assert borrar.files is archivos and borrar.listener is borrado


def test_la_promocion_se_cuelga_de_guardado_y_de_borrado():
    promocion = bootstrap.get_attachment_promotion_listener(
        None, bootstrap.get_attachment_visibility_listener()
    )

    guardado = bootstrap.get_attachment_stored_listener(promocion)
    borrado = bootstrap.get_attachment_deleted_listener(promocion)

    assert isinstance(promocion, AttachmentPromotionListener)
    assert isinstance(guardado, CompositeAttachmentStoredListener)
    assert guardado.listeners == [promocion]
    assert isinstance(borrado, CompositeAttachmentDeletedListener)
    assert borrado.listeners == [promocion]


def test_hasta_la_decision_4_nadie_escucha_los_cambios_de_visibilidad():
    assert isinstance(
        bootstrap.get_attachment_visibility_listener(), NoopAttachmentVisibilityListener
    )


async def test_cada_promocion_abre_su_propia_sesion():
    # La promoción toma un candado y hace su propio commit: no puede usar la sesión de
    # la petición. Construir y cerrar una sesión sin consultas no conecta.
    abrir = bootstrap.build_promotion_opener(None, NoopAttachmentVisibilityListener())

    async with abrir() as primera, abrir() as segunda:
        assert isinstance(primera.trust, SqlAttachmentTrustRepository)
        assert isinstance(segunda.trust, SqlAttachmentTrustRepository)
        assert primera.trust.session is not segunda.trust.session
        assert primera.storage is None


def test_las_rutas_nuevas_aparecen_en_openapi():
    from app.main import app

    paths = app.openapi()["paths"]
    esperadas = {
        "/tenders/{tender_id}/attachments/{attachment_id}/upload-url": (
            "post",
            "Pedir una URL para subir un anexo",
        ),
        "/tenders/{tender_id}/attachments/uploads/{upload_id}/complete": (
            "post",
            "Confirmar la subida de un anexo",
        ),
        "/tenders/{tender_id}/attachments/files/{file_id}": (
            "delete",
            "Borrar un archivo de anexo de la empresa",
        ),
    }
    for ruta, (metodo, resumen) in esperadas.items():
        operacion = paths[ruta][metodo]
        assert operacion["summary"] == resumen
        assert operacion["tags"] == ["Tender attachments"]
