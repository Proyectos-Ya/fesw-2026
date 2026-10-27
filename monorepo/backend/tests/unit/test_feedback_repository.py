"""Almacenamiento de la retroalimentación de usuario (HU-24, #315).

Sin Postgres a mano, la migración se aplica sobre SQLite con el esquema mínimo
previo, igual que en `test_quotation_repository`. Que los modelos y la
migración coincidan lo comprueba `tests/integration/test_migraciones.py`
cuando hay Postgres.
"""

import importlib.util
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.feedback import (
    AppFeedback,
    AppFeedbackKind,
    AssistantMessageFeedback,
    MatchReport,
    MatchReportKind,
)
from app.infrastructure.repositories.feedback_repository import (
    AppFeedbackRepository,
    AssistantFeedbackRepository,
    MatchReportRepository,
)

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/b7f3c1a9d2e4_retroalimentacion_de_usuario.py"
)
_TABLES = ("match_report", "assistant_message_feedback", "app_feedback")


def _load_migration():
    spec = importlib.util.spec_from_file_location("feedback_migration", _MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run(engine: AsyncEngine, direction: str) -> None:
    migration = _load_migration()

    def apply(connection):
        with Operations.context(MigrationContext.configure(connection)):
            getattr(migration, direction)()

    async with engine.begin() as connection:
        await connection.run_sync(apply)


@pytest_asyncio.fixture
async def engine(tmp_path) -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'feedback.db'}")
    async with eng.begin() as connection:
        # Esquema mínimo previo: las tablas de la funcionalidad las crea Alembic.
        for table in ("users", "supplier", "tender", "tender_chat_messages"):
            await connection.execute(
                text(f"CREATE TABLE {table} (id CHAR(32) PRIMARY KEY)")
            )
    await _run(eng, "upgrade")
    try:
        yield eng
    finally:
        await eng.dispose()


def _session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_migration_creates_and_drops_only_the_feedback_tables(engine):
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert set(_TABLES) <= names

    await _run(engine, "downgrade")
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert names == {"users", "supplier", "tender", "tender_chat_messages"}


@pytest.mark.asyncio
async def test_match_report_is_replaced_per_supplier_tender_and_kind(engine):
    supplier, tender, user = uuid4(), uuid4(), uuid4()
    async with _session(engine) as session:
        repo = MatchReportRepository(session)
        await repo.upsert(
            MatchReport(
                supplier_id=supplier,
                user_id=user,
                tender_id=tender,
                kind=MatchReportKind.MATCH,
                reason="No vendemos eso",
            )
        )
        second = await repo.upsert(
            MatchReport(
                supplier_id=supplier,
                user_id=user,
                tender_id=tender,
                kind=MatchReportKind.MATCH,
                reason="Otra razón",
            )
        )
        await repo.upsert(
            MatchReport(
                supplier_id=supplier,
                user_id=user,
                tender_id=tender,
                kind=MatchReportKind.ANALYSIS,
                reason="El análisis está mal",
            )
        )
        assert second.reason == "Otra razón"
        assert await repo.list_reported_tender_ids(
            supplier, MatchReportKind.MATCH
        ) == {tender}
        count = await session.execute(text("SELECT COUNT(*) FROM match_report"))
        assert count.scalar() == 2


@pytest.mark.asyncio
async def test_match_report_is_isolated_per_supplier_and_kind(engine):
    supplier, other, tender, user = uuid4(), uuid4(), uuid4(), uuid4()
    async with _session(engine) as session:
        repo = MatchReportRepository(session)
        await repo.upsert(
            MatchReport(
                supplier_id=supplier,
                user_id=user,
                tender_id=tender,
                kind=MatchReportKind.ANALYSIS,
                reason="Mal análisis",
            )
        )
        assert await repo.list_reported_tender_ids(other, MatchReportKind.ANALYSIS) == set()
        assert await repo.list_reported_tender_ids(supplier, MatchReportKind.MATCH) == set()


@pytest.mark.asyncio
async def test_assistant_feedback_is_replaced_per_message_and_user(engine):
    message, tender, user, supplier = uuid4(), uuid4(), uuid4(), uuid4()
    async with _session(engine) as session:
        repo = AssistantFeedbackRepository(session)
        await repo.upsert(
            AssistantMessageFeedback(
                message_id=message,
                user_id=user,
                supplier_id=supplier,
                tender_id=tender,
                reason="No respondió lo que pregunté",
            )
        )
        second = await repo.upsert(
            AssistantMessageFeedback(
                message_id=message,
                user_id=user,
                supplier_id=supplier,
                tender_id=tender,
                reason="Faltó el plazo",
            )
        )
        stored = await repo.get_by_message(message, user)
        assert stored is not None and stored.reason == "Faltó el plazo"
        assert stored.id == second.id
        assert await repo.get_by_message(message, uuid4()) is None
        count = await session.execute(
            text("SELECT COUNT(*) FROM assistant_message_feedback")
        )
        assert count.scalar() == 1


@pytest.mark.asyncio
async def test_app_feedback_stores_comments_and_reviews(engine):
    user = uuid4()
    async with _session(engine) as session:
        repo = AppFeedbackRepository(session)
        comment = await repo.add(
            AppFeedback(user_id=user, kind=AppFeedbackKind.COMMENT, message="Queja")
        )
        review = await repo.add(
            AppFeedback(
                user_id=user,
                kind=AppFeedbackKind.REVIEW,
                rating=0,
                anonymous=True,
            )
        )
        rows = await session.execute(
            text("SELECT kind, message, rating, anonymous FROM app_feedback ORDER BY kind")
        )
        assert [tuple(r) for r in rows] == [
            ("comment", "Queja", None, 0),
            ("review", None, 0, 1),
        ]
        assert comment.id != review.id


def test_reasons_and_messages_cannot_be_blank_or_oversized():
    ids = dict(supplier_id=uuid4(), user_id=uuid4(), tender_id=uuid4())
    with pytest.raises(ValidationError):
        MatchReport(**ids, kind=MatchReportKind.MATCH, reason="   ")
    with pytest.raises(ValidationError):
        MatchReport(**ids, kind=MatchReportKind.MATCH, reason="x" * 1001)
    with pytest.raises(ValidationError):
        AssistantMessageFeedback(
            message_id=uuid4(), user_id=uuid4(), tender_id=uuid4(), reason=""
        )
    assert (
        MatchReport(**ids, kind=MatchReportKind.MATCH, reason="  razón  ").reason
        == "razón"
    )


def test_app_feedback_rules():
    user = uuid4()
    with pytest.raises(ValidationError):  # un comentario necesita mensaje
        AppFeedback(user_id=user, kind=AppFeedbackKind.COMMENT, message=" ")
    with pytest.raises(ValidationError):  # un comentario no lleva estrellas
        AppFeedback(
            user_id=user, kind=AppFeedbackKind.COMMENT, message="hola", rating=3
        )
    with pytest.raises(ValidationError):  # reseña vacía
        AppFeedback(user_id=user, kind=AppFeedbackKind.REVIEW)
    for rating in (-1, 6):
        with pytest.raises(ValidationError):
            AppFeedback(user_id=user, kind=AppFeedbackKind.REVIEW, rating=rating)
    # estrellas y/o comentario: cualquiera de los dos alcanza, y 0 es válido
    AppFeedback(user_id=user, kind=AppFeedbackKind.REVIEW, rating=0)
    AppFeedback(user_id=user, kind=AppFeedbackKind.REVIEW, message="Bien")
    review = AppFeedback(
        user_id=user, kind=AppFeedbackKind.REVIEW, rating=5, message="Genial"
    )
    assert review.anonymous is False

@pytest.mark.asyncio
async def test_assistant_feedback_list_by_tender_and_supplier(engine):
    tender, supplier, other_supplier, user = uuid4(), uuid4(), uuid4(), uuid4()
    async with _session(engine) as session:
        repo = AssistantFeedbackRepository(session)
        msg1, msg2, msg3 = uuid4(), uuid4(), uuid4()
        await repo.upsert(
            AssistantMessageFeedback(
                message_id=msg1,
                user_id=user,
                supplier_id=supplier,
                tender_id=tender,
                reason="Faltaron las fechas",
            )
        )
        await repo.upsert(
            AssistantMessageFeedback(
                message_id=msg2,
                user_id=user,
                supplier_id=supplier,
                tender_id=tender,
                reason="Requisito de garantía incorrecto",
            )
        )
        # Otro supplier
        await repo.upsert(
            AssistantMessageFeedback(
                message_id=msg3,
                user_id=user,
                supplier_id=other_supplier,
                tender_id=tender,
                reason="Otro motivo",
            )
        )
        # Consulta
        res = await repo.list_by_tender_and_supplier(tender, supplier)
        assert len(res) == 2
        assert [r.reason for r in res] == ["Faltaron las fechas", "Requisito de garantía incorrecto"]
