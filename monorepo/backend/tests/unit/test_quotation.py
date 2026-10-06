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
        **dict(description="Cemento", unit="saco", quantity="2", unit_price="100")
        | changes
    )


def test_integer_totals():
    data = QuotationInput(items=[material(), material(quantity="1", unit_price="0")])
    assert data.items[0].subtotal == Decimal("200")
    assert data.total == Decimal("200")


@pytest.mark.parametrize(
    "changes",
    [
        {"description": "  "},
        {"unit": ""},
        {"quantity": "0"},
        {"quantity": "-1"},
        {"unit_price": "-0.01"},
        {"quantity": "NaN"},
        {"quantity": "1.5"},
        {"unit_price": "10.5"},
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


@pytest.mark.asyncio
async def test_company_is_the_active_one_when_given():
    active_id, user_id, tender_id = uuid4(), uuid4(), uuid4()
    repo, suppliers, tenders = AsyncMock(), AsyncMock(), AsyncMock()
    suppliers.get_by_id.return_value = SimpleNamespace(id=active_id)
    tenders.get_tenders.return_value = [SimpleNamespace(id=tender_id)]
    data = QuotationInput(items=[material()])
    await QuotationUseCase(repo, suppliers, tenders).save(
        user_id, tender_id, data, supplier_id=active_id
    )
    suppliers.get_by_id.assert_awaited_once_with(active_id)
    suppliers.get_by_user_id.assert_not_awaited()
    repo.save.assert_awaited_once_with(active_id, tender_id, data)


def test_legacy_fractional_quotation_can_be_read_but_not_saved():
    from app.domain.entities.quotation import Quotation
    from app.shared.datetime_utils import utc_now_naive
    data = dict(currency="CLP", items=[dict(description="Arena", unit="m3", quantity="2.5", unit_price="100.25")])
    old = Quotation(id=uuid4(), supplier_id=uuid4(), tender_id=uuid4(), updated_at=utc_now_naive(), **data)
    assert old.total == Decimal("250.63")
    with pytest.raises(ValidationError):
        QuotationInput(**data)
