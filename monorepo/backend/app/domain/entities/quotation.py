from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints, computed_field, field_serializer,
)

from app.shared.datetime_utils import UtcDateTime


class StoredMaterialItem(BaseModel):
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

    @field_serializer("quantity", "unit_price")
    def serialize_number(self, value: Decimal) -> str:
        if value == value.to_integral_value():
            value = value.quantize(Decimal("1"))
        return format(value, "f")

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        integral = (
            self.quantity == self.quantity.to_integral_value()
            and self.unit_price == self.unit_price.to_integral_value()
        )
        # Solo las cotizaciones históricas conservan el cálculo fraccionario.
        precision = Decimal("1") if integral else Decimal("0.01")
        return (self.quantity * self.unit_price).quantize(precision, rounding=ROUND_HALF_UP)


class MaterialItem(StoredMaterialItem):
    # Nuevas escrituras: enteros; el modelo de lectura admite datos históricos.
    quantity: Decimal = Field(gt=0, max_digits=9, decimal_places=0, allow_inf_nan=False)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=0, allow_inf_nan=False)


class QuotationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: Literal["CLP"] = "CLP"
    items: list[StoredMaterialItem] = Field(min_length=1, max_length=200)

    @computed_field
    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0"))


class QuotationInput(QuotationData):
    items: list[MaterialItem] = Field(min_length=1, max_length=200)


class Quotation(QuotationData):
    # Lectura compatible con cotizaciones anteriores, sin convertir sus importes.
    currency: Literal["CLP", "USD", "EUR", "UF"] = "CLP"
    id: UUID
    supplier_id: UUID
    tender_id: UUID
    updated_at: UtcDateTime
