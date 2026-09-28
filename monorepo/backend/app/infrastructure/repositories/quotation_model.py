from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel


class QuotationModel(SQLModel, table=True):
    __tablename__ = "quotation"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "tender_id", name="uq_quotation_company_tender"
        ),
    )

    id: UUID = Field(primary_key=True)
    supplier_id: UUID = Field(foreign_key="supplier.id", index=True)
    tender_id: UUID = Field(foreign_key="tender.id", index=True)
    currency: str = Field(max_length=3)
    updated_at: datetime


class QuotationMaterialModel(SQLModel, table=True):
    __tablename__ = "quotation_material"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quotation_material_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_quotation_material_price"),
    )

    id: UUID = Field(primary_key=True)
    quotation_id: UUID = Field(
        foreign_key="quotation.id", index=True, ondelete="CASCADE"
    )
    position: int
    description: str = Field(max_length=500)
    unit: str = Field(max_length=40)
    quantity: Decimal = Field(max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(max_digits=14, decimal_places=2)
