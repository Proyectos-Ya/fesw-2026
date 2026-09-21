from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.use_cases.quotation import QuotationNotFound, QuotationUseCase
from app.domain.entities.quotation import MaterialItem, QuotationInput


def material(**changes):
    return MaterialItem(
        **dict(description="Cemento", unit="saco", quantity="2.5", unit_price="100.25")
        | changes
    )


def test_decimal_totals_round_each_line():
    data = QuotationInput(items=[material(), material(quantity="1", unit_price="0")])
    assert data.items[0].subtotal == Decimal("250.63")
    assert data.total == Decimal("250.63")


@pytest.mark.parametrize(
    "changes",
    [
        {"description": "  "},
        {"unit": ""},
        {"quantity": "0"},
        {"quantity": "-1"},
        {"unit_price": "-0.01"},
        {"quantity": "NaN"},
        {"unit_price": "Infinity"},
    ],
)
def test_invalid_material(changes):
    with pytest.raises(ValidationError):
        material(**changes)


def test_empty_quotation_rejected():
    with pytest.raises(ValidationError):
        QuotationInput(items=[])


def test_clp_default_and_unit_required():
    item = MaterialItem(description="Cemento", unit="saco", quantity="2", unit_price="1500")
    with pytest.raises(ValidationError):
        MaterialItem(description="Cemento", quantity="2", unit_price="1500")
    data = QuotationInput(items=[item])
    assert data.currency == "CLP"
    assert data.total == Decimal("3000.00")
    with pytest.raises(ValidationError):
        QuotationInput(currency="USD", items=[item])


@pytest.mark.asyncio
async def test_company_is_resolved_from_authenticated_user():
    supplier_id, user_id, tender_id = uuid4(), uuid4(), uuid4()
    repo, suppliers, tenders = AsyncMock(), AsyncMock(), AsyncMock()
    suppliers.get_by_user_id.return_value = SimpleNamespace(id=supplier_id)
    tenders.get_tenders.return_value = [SimpleNamespace(id=tender_id)]
    data = QuotationInput(items=[material()])
    await QuotationUseCase(repo, suppliers, tenders).save(user_id, tender_id, data)
    suppliers.get_by_user_id.assert_awaited_once_with(user_id)
    repo.save.assert_awaited_once_with(supplier_id, tender_id, data)


@pytest.mark.asyncio
async def test_read_is_scoped_to_company():
    supplier_id, tender_id = uuid4(), uuid4()
    repo, suppliers, tenders = AsyncMock(), AsyncMock(), AsyncMock()
    suppliers.get_by_user_id.return_value = SimpleNamespace(id=supplier_id)
    tenders.get_tenders.return_value = [SimpleNamespace(id=tender_id)]
    repo.get.return_value = None
    with pytest.raises(QuotationNotFound):
        await QuotationUseCase(repo, suppliers, tenders).get(uuid4(), tender_id)
    repo.get.assert_awaited_once_with(supplier_id, tender_id)
