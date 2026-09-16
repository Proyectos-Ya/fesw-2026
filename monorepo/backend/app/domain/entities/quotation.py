from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

from app.shared.datetime_utils import UtcDateTime


class MaterialItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    unit: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
    ]
    quantity: Decimal = Field(
        gt=0, max_digits=12, decimal_places=3, allow_inf_nan=False
    )
    unit_price: Decimal = Field(
        ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False
    )

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


class QuotationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: Literal["CLP", "USD", "EUR", "UF"] = "CLP"
    items: list[MaterialItem] = Field(min_length=1, max_length=200)

    @computed_field
    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0.00"))


class Quotation(QuotationInput):
    id: UUID
    supplier_id: UUID
    tender_id: UUID
    updated_at: UtcDateTime
