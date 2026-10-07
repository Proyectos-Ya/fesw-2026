"""Pruebas unitarias para SqlMatchingShadowRepository (Plan 233, Decisión 9)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.entities.matching_shadow import (
    MatchingShadowScore,
    TenderAttachmentItem,
)
from app.infrastructure.repositories.matching_shadow_model import (
    MatchingShadowScoreModel,
    TenderAttachmentItemModel,
)
from app.infrastructure.repositories.sql_matching_shadow_repository import (
    SqlMatchingShadowRepository,
)


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_save_shadow_scores(mock_session):
    repo = SqlMatchingShadowRepository(mock_session)
    score = MatchingShadowScore(
        id=uuid4(),
        ranking_id=uuid4(),
        supplier_id=uuid4(),
        tender_id=uuid4(),
        variant="att-text-v1",
        baseline_score=0.72,
        shadow_score=0.88,
        reranker_score=0.85,
        best_match=0.90,
        coverage=0.80,
        model_version="v1",
    )

    await repo.save_shadow_scores([score])

    mock_session.merge.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_shadow_scores_by_ranking(mock_session):
    repo = SqlMatchingShadowRepository(mock_session)
    ranking_id = uuid4()
    model = MatchingShadowScoreModel(
        id=uuid4(),
        ranking_id=ranking_id,
        supplier_id=uuid4(),
        tender_id=uuid4(),
        variant="att-text-v1",
        baseline_score=0.70,
        shadow_score=0.82,
        model_version="v1",
        calculated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_result = MagicMock()
    mock_result.all.return_value = [model]
    mock_session.exec.return_value = mock_result

    scores = await repo.get_shadow_scores_by_ranking(ranking_id)

    assert len(scores) == 1
    assert scores[0].ranking_id == ranking_id
    assert scores[0].shadow_score == 0.82


@pytest.mark.asyncio
async def test_get_shadow_scores_by_supplier(mock_session):
    repo = SqlMatchingShadowRepository(mock_session)
    supplier_id = uuid4()
    model = MatchingShadowScoreModel(
        id=uuid4(),
        ranking_id=None,
        supplier_id=supplier_id,
        tender_id=uuid4(),
        variant="att-items-v1",
        baseline_score=0.60,
        shadow_score=0.75,
        model_version="v1",
        calculated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_result = MagicMock()
    mock_result.all.return_value = [model]
    mock_session.exec.return_value = mock_result

    scores = await repo.get_shadow_scores_by_supplier(
        supplier_id, variant="att-items-v1", limit=10
    )

    assert len(scores) == 1
    assert scores[0].supplier_id == supplier_id
    assert scores[0].variant == "att-items-v1"


@pytest.mark.asyncio
async def test_save_and_get_attachment_items(mock_session):
    repo = SqlMatchingShadowRepository(mock_session)
    tender_id = uuid4()
    item = TenderAttachmentItem(
        id=uuid4(),
        tender_id=tender_id,
        title="Partida de anexo",
        description="Detalle de partida",
        quantity=5.0,
        unit="UN",
    )

    await repo.save_attachment_items([item])
    mock_session.merge.assert_awaited_once()
    mock_session.commit.assert_awaited_once()

    item_model = TenderAttachmentItemModel(
        id=item.id,
        tender_id=tender_id,
        title=item.title,
        description=item.description,
        quantity=item.quantity,
        unit=item.unit,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    mock_result = MagicMock()
    mock_result.all.return_value = [item_model]
    mock_session.exec.return_value = mock_result

    fetched = await repo.get_attachment_items(tender_id)
    assert len(fetched) == 1
    assert fetched[0].id == item.id
    assert fetched[0].title == "Partida de anexo"
