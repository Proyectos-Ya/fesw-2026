from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.domain.entities.saved_tender import SavedTender
from app.domain.entities.tender import Tender
from app.domain.errors.saved_tender_errors import SavedTenderNotFound
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import (
    InMemorySavedTenderRepository,
    InMemoryTenderRepository,
)


def create_dummy_tender(tender_id: UUID) -> Tender:
    """Helper para crear una licitación dummy con parámetros de prueba."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"COT-{tender_id}",
        name="Licitación de Prueba",
        description="Descripción de prueba",
        status_id=1,
        published_at=now - timedelta(days=1),
        closing_at=now + timedelta(hours=24),
        last_change_at=now,
        buyer_rut="12.345.678-9",
        buyer_name="Municipalidad de Santiago",
        buyer_unit="TI",
        items=[],
    )


def build_repos(
    tender_ids: list[UUID],
) -> tuple[InMemorySavedTenderRepository, InMemoryTenderRepository]:
    """Arma los dos repositorios en memoria con las licitaciones indicadas."""
    tender_repo = InMemoryTenderRepository()
    for tender_id in tender_ids:
        tender_repo.tenders[tender_id] = create_dummy_tender(tender_id)
    return InMemorySavedTenderRepository(), tender_repo


# ---------------------------------------------------------------------------
# ListSavedTendersUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_only_tenders_saved_by_the_user() -> None:
    """Valida que el listado incluya las licitaciones que el usuario marcó, ya hidratadas."""
    user_id = uuid4()
    tender_id = uuid4()
    saved_repo, tender_repo = build_repos([tender_id, uuid4()])
    await saved_repo.save(SavedTender(user_id=user_id, tender_id=tender_id))

    result = await ListSavedTendersUseCase(saved_repo, tender_repo).execute(user_id)

    assert len(result) == 1
    assert result[0].tender is not None
    assert result[0].tender.id == tender_id
    assert result[0].tender.buyer_name == "Municipalidad de Santiago"


@pytest.mark.asyncio
async def test_list_without_saved_tenders_returns_empty_without_querying() -> None:
    """Valida que un usuario sin guardadas reciba una lista vacía y no se consulte la BD.

    Es la protección contra el filtro `ids=[]`: `get_tenders` solo aplica el
    filtro cuando la lista trae elementos, así que consultar con una lista vacía
    devolvería todas las licitaciones de la base.
    """
    saved_repo, tender_repo = build_repos([uuid4(), uuid4()])

    result = await ListSavedTendersUseCase(saved_repo, tender_repo).execute(uuid4())

    assert result == []
    assert tender_repo.get_tenders_calls == []


@pytest.mark.asyncio
async def test_list_excludes_tenders_saved_by_another_user() -> None:
    """Valida que el listado no filtre hacia dentro las guardadas de otro usuario."""
    user_id = uuid4()
    other_user_id = uuid4()
    own_tender_id = uuid4()
    other_tender_id = uuid4()
    saved_repo, tender_repo = build_repos([own_tender_id, other_tender_id])
    await saved_repo.save(SavedTender(user_id=user_id, tender_id=own_tender_id))
    await saved_repo.save(SavedTender(user_id=other_user_id, tender_id=other_tender_id))

    result = await ListSavedTendersUseCase(saved_repo, tender_repo).execute(user_id)

    assert [t.tender.id for t in result if t.tender] == [own_tender_id]


@pytest.mark.asyncio
async def test_list_is_ordered_by_saved_at_descending() -> None:
    """Valida que la licitación guardada más recientemente aparezca primero."""
    user_id = uuid4()
    older_id, newer_id = uuid4(), uuid4()
    saved_repo, tender_repo = build_repos([older_id, newer_id])
    now = datetime.now(UTC).replace(tzinfo=None)
    await saved_repo.save(
        SavedTender(
            user_id=user_id, tender_id=older_id, saved_at=now - timedelta(days=2)
        )
    )
    await saved_repo.save(
        SavedTender(user_id=user_id, tender_id=newer_id, saved_at=now)
    )

    result = await ListSavedTendersUseCase(saved_repo, tender_repo).execute(user_id)

    assert [t.tender.id for t in result if t.tender] == [newer_id, older_id]



# ---------------------------------------------------------------------------
# SaveTenderUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_associates_the_tender_with_the_user() -> None:
    """Valida que marcar una licitación la asocie a la lista del usuario."""
    user_id = uuid4()
    tender_id = uuid4()
    saved_repo, tender_repo = build_repos([tender_id])

    saved = await SaveTenderUseCase(saved_repo, tender_repo).execute(user_id, tender_id)

    assert saved.user_id == user_id
    assert saved.tender_id == tender_id
    assert await saved_repo.get(user_id, tender_id) is not None


@pytest.mark.asyncio
async def test_save_twice_does_not_duplicate_the_entry() -> None:
    """Valida que guardar dos veces la misma licitación sea idempotente."""
    user_id = uuid4()
    tender_id = uuid4()
    saved_repo, tender_repo = build_repos([tender_id])
    use_case = SaveTenderUseCase(saved_repo, tender_repo)

    first = await use_case.execute(user_id, tender_id)
    second = await use_case.execute(user_id, tender_id)

    assert first.id == second.id
    assert len(await saved_repo.get_by_user_id(user_id)) == 1


@pytest.mark.asyncio
async def test_save_unknown_tender_raises_tender_not_found() -> None:
    """Valida que guardar una licitación inexistente levante TenderNotFound."""
    saved_repo, tender_repo = build_repos([])

    with pytest.raises(TenderNotFound):
        await SaveTenderUseCase(saved_repo, tender_repo).execute(uuid4(), uuid4())


# ---------------------------------------------------------------------------
# UnsaveTenderUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsave_removes_the_tender_from_the_list() -> None:
    """Valida que quitar una licitación la retire de la lista del usuario."""
    user_id = uuid4()
    tender_id = uuid4()
    saved_repo, _ = build_repos([tender_id])
    await saved_repo.save(SavedTender(user_id=user_id, tender_id=tender_id))

    await UnsaveTenderUseCase(saved_repo).execute(user_id, tender_id)

    assert await saved_repo.get(user_id, tender_id) is None


@pytest.mark.asyncio
async def test_unsave_tender_that_was_not_saved_raises_not_found() -> None:
    """Valida que quitar algo que no estaba guardado levante SavedTenderNotFound."""
    saved_repo, _ = build_repos([])

    with pytest.raises(SavedTenderNotFound):
        await UnsaveTenderUseCase(saved_repo).execute(uuid4(), uuid4())
