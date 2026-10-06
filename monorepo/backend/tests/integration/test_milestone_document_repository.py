"""Registro de bases ya leídas por la extracción de hitos, contra Postgres real (HU-16)."""

from datetime import datetime
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.tender_chat import TenderChatDocument
from app.infrastructure.repositories.sql_tender_chat_repository import (
    SQLTenderChatRepository,
)
from app.infrastructure.repositories.tender_milestone_document_repository import (
    TenderMilestoneDocumentRepository,
)
from tests.integration.test_milestone_calendar_repositories import _licitacion, _usuario

AHORA = datetime(2026, 10, 6, 12, 0)


async def _subir(session: AsyncSession, tmp_path: Path, user_id, tender_id) -> TenderChatDocument:
    chat = SQLTenderChatRepository(session, storage_dir=tmp_path)
    return await chat.save_document(
        TenderChatDocument(
            tender_id=tender_id,
            user_id=user_id,
            file_name="bases.pdf",
            file_type="pdf",
            file_size_bytes=4,
            storage_path="uploads/bases.pdf",
        ),
        b"%PDF",
    )


async def test_marca_y_lista_las_bases_procesadas_del_usuario(db_session: AsyncSession, tmp_path: Path):
    usuario, otro = await _usuario(db_session), await _usuario(db_session)
    licitacion = await _licitacion(db_session)
    propia = await _subir(db_session, tmp_path, usuario, licitacion)
    ajena = await _subir(db_session, tmp_path, otro, licitacion)
    repo = TenderMilestoneDocumentRepository(db_session)

    await repo.mark_processed(usuario, licitacion, propia.id, 3, AHORA)
    await repo.mark_processed(otro, licitacion, ajena.id, 1, AHORA)

    assert await repo.list_processed(usuario, licitacion) == {propia.id}


async def test_marcar_dos_veces_no_falla(db_session: AsyncSession, tmp_path: Path):
    usuario = await _usuario(db_session)
    licitacion = await _licitacion(db_session)
    documento = await _subir(db_session, tmp_path, usuario, licitacion)
    repo = TenderMilestoneDocumentRepository(db_session)

    await repo.mark_processed(usuario, licitacion, documento.id, 3, AHORA)
    await repo.mark_processed(usuario, licitacion, documento.id, 4, AHORA)

    assert await repo.list_processed(usuario, licitacion) == {documento.id}


async def test_al_borrar_la_base_se_borra_su_registro(db_session: AsyncSession, tmp_path: Path):
    # Si el usuario la vuelve a subir, se vuelve a leer.
    usuario = await _usuario(db_session)
    licitacion = await _licitacion(db_session)
    documento = await _subir(db_session, tmp_path, usuario, licitacion)
    repo = TenderMilestoneDocumentRepository(db_session)
    await repo.mark_processed(usuario, licitacion, documento.id, 3, AHORA)

    await SQLTenderChatRepository(db_session, storage_dir=tmp_path).delete_document(documento.id, usuario)

    assert await repo.list_processed(usuario, licitacion) == set()
