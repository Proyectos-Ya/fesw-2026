from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.application.use_cases.quotation import (
    QuotationCompanyRequired,
    QuotationNotFound,
)
from app.domain.entities.quotation import MaterialItem, Quotation
from app.infrastructure.routers.quotation import create_quotation_router
from app.shared.datetime_utils import utc_now_naive


@pytest.fixture
def api():
    user_id, tender_id, supplier_id = uuid4(), uuid4(), uuid4()
    use_case = AsyncMock()
    quotation = Quotation(
        id=uuid4(),
        supplier_id=supplier_id,
        tender_id=tender_id,
        updated_at=utc_now_naive(),
        items=[
            MaterialItem(
                description="Cemento", unit="saco", quantity="2", unit_price="100"
            )
        ],
    )
    use_case.get.return_value = quotation
    use_case.save.return_value = quotation
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=user_id)

    app.include_router(create_quotation_router(current_user, lambda: use_case))
    return (
        TestClient(app),
        use_case,
        f"/tenders/{tender_id}/quotation",
        app,
        current_user,
    )


def test_roundtrip_integer_response(api):
    client, use_case, path, *_ = api
    payload = {
        "currency": "CLP",
        "items": [
            {
                "description": "Cemento",
                "unit": "saco",
                "quantity": "2",
                "unit_price": "100",
            }
        ],
    }
    response = client.put(path, json=payload)
    assert response.status_code == 200
    assert response.json()["total"] == "200"
    assert client.get(path).json()["items"][0]["subtotal"] == "200"


def test_shipping_is_optional_integer_and_saved(api):
    client, use_case, path, *_ = api
    item = {"description": "Cemento", "unit": "saco", "quantity": "2", "unit_price": "100"}
    response = client.put(path, json={"items": [item], "shipping_clp": "25000"})
    assert response.status_code == 200
    saved = use_case.save.call_args.args[-1]
    assert saved.shipping_clp == 25000

    client.put(path, json={"items": [item]})
    assert use_case.save.call_args.args[-1].shipping_clp is None


@pytest.mark.parametrize("shipping", ["-1", "10.5"])
def test_invalid_shipping_is_rejected(api, shipping):
    client, use_case, path, *_ = api
    item = {"description": "Cemento", "unit": "saco", "quantity": "2", "unit_price": "100"}
    response = client.put(path, json={"items": [item], "shipping_clp": shipping})
    assert response.status_code in (400, 422)
    use_case.save.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"items": []},
        {"items": [{"description": "x", "unit": "u", "quantity": "1.5", "unit_price": "10"}]},
        {"items": [{"description": "x", "unit": "u", "quantity": "1", "unit_price": "10.5"}]},
        {"items": [{"description": "x", "unit": "u", "quantity": 0, "unit_price": 10}]},
        {"items": [{"description": "x", "unit": "u", "quantity": 1, "unit_price": -1}]},
        {
            "supplier_id": str(uuid4()),
            "items": [
                {"description": "x", "unit": "u", "quantity": 1, "unit_price": 1}
            ],
        },
    ],
)
def test_bad_request_never_saves(api, payload):
    client, use_case, path, *_ = api
    assert client.put(path, json=payload).status_code == 422
    use_case.save.assert_not_awaited()


def test_company_required_and_missing_quotation(api):
    client, use_case, path, *_ = api
    use_case.get.side_effect = QuotationCompanyRequired("Registra tu empresa")
    assert client.get(path).status_code == 403
    use_case.get.side_effect = QuotationNotFound("No existe")
    assert client.get(path).status_code == 404


def test_unauthenticated_request_is_rejected(api):
    client, use_case, path, app, current_user = api

    def denied():
        raise HTTPException(401, "No autenticado")

    app.dependency_overrides[current_user] = denied
    assert client.get(path).status_code == 401
    assert client.put(path, json={"items": []}).status_code == 401
    use_case.get.assert_not_awaited()
    use_case.save.assert_not_awaited()
