"""Las dependencias de la lista oficial de anexos en bootstrap.py resuelven bien
y la ruta queda montada en la aplicación (sin NameError ni errores de importación)."""

from unittest.mock import AsyncMock

from sqlmodel.ext.asyncio.session import AsyncSession

from app.bootstrap import get_tender_attachment_repo, get_tender_attachments_use_case
from app.infrastructure.repositories.sql_tender_attachment_repository import (
    SqlTenderAttachmentRepository,
)


def test_get_tender_attachment_repo_usa_la_sesion_recibida():
    session = AsyncMock(spec=AsyncSession)

    repo = get_tender_attachment_repo(session)

    assert isinstance(repo, SqlTenderAttachmentRepository)
    assert repo.session is session


def test_el_caso_de_uso_recibe_el_repositorio():
    repo = SqlTenderAttachmentRepository(AsyncMock(spec=AsyncSession))

    use_case = get_tender_attachments_use_case(repo)

    assert use_case.attachments is repo


def test_la_ruta_aparece_en_la_aplicacion():
    from app.main import app

    operacion = app.openapi()["paths"]["/tenders/{tender_id}/attachments"]["get"]

    assert operacion["summary"] == "Listar los anexos oficiales de una licitación"
    assert operacion["tags"] == ["Tender attachments"]
