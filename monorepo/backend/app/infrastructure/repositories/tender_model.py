from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from app.shared.datetime_utils import utc_now_naive


class RegionModel(SQLModel, table=True):
    __tablename__ = "region"  # type: ignore
    id: int = Field(primary_key=True)
    name: str

    institutions: list["BuyerInstitutionModel"] = Relationship(back_populates="region")
    provincias: list["ProvinciaModel"] = Relationship(back_populates="region")


class ProvinciaModel(SQLModel, table=True):
    __tablename__ = "provincia"  # type: ignore
    id: int = Field(primary_key=True)
    name: str
    region_id: int = Field(foreign_key="region.id")

    region: RegionModel | None = Relationship(back_populates="provincias")
    comunas: list["ComunaModel"] = Relationship(back_populates="provincia")


class ComunaModel(SQLModel, table=True):
    __tablename__ = "comuna"  # type: ignore
    id: int = Field(primary_key=True)
    name: str
    provincia_id: int = Field(foreign_key="provincia.id")

    provincia: ProvinciaModel | None = Relationship(back_populates="comunas")
    institutions: list["BuyerInstitutionModel"] = Relationship(back_populates="comuna")


class TenderStatusModel(SQLModel, table=True):
    __tablename__ = "tender_status"  # type: ignore
    id: int = Field(primary_key=True)
    code: str = Field(unique=True, index=True)
    name: str

    tenders: list["TenderModel"] = Relationship(back_populates="status")


class BuyerInstitutionModel(SQLModel, table=True):
    __tablename__ = "buyer_institution"  # type: ignore
    rut: str = Field(primary_key=True)
    name: str
    region_id: int = Field(foreign_key="region.id")
    # Nullable: no todos los organismos se resuelven (ver
    # app/shared/comunas.py). La provincia sale del join comuna -> provincia,
    # no se guarda una columna separada para no poder desincronizarse.
    comuna_id: int | None = Field(default=None, foreign_key="comuna.id")
    # Qué heurística resolvió comuna_id ("organismo_name" por ahora). Sirve
    # para auditar/depurar cuando se sumen más caminos de resolución.
    comuna_resolution_source: str | None = None
    created_at: datetime
    updated_at: datetime

    region: RegionModel | None = Relationship(back_populates="institutions")
    comuna: ComunaModel | None = Relationship(back_populates="institutions")
    tenders: list["TenderModel"] = Relationship(back_populates="buyer")


class TenderModel(SQLModel, table=True):
    __tablename__ = "tender"  # type: ignore
    id: UUID = Field(primary_key=True)
    code: str = Field(unique=True, index=True)
    name: str
    description: str | None = None
    status_id: int = Field(foreign_key="tender_status.id")
    published_at: datetime
    closing_at: datetime
    last_change_at: datetime
    buyer_rut: str = Field(foreign_key="buyer_institution.rut")
    buyer_unit: str
    available_amount_clp: float | None = None
    created_at: datetime
    updated_at: datetime

    status: TenderStatusModel | None = Relationship(back_populates="tenders")
    buyer: BuyerInstitutionModel | None = Relationship(back_populates="tenders")
    items: list["TenderItemModel"] = Relationship(back_populates="tender")
    ai_analysis: Optional["TenderAIAnalysisModel"] = Relationship(
        back_populates="tender"
    )


class TenderItemModel(SQLModel, table=True):
    __tablename__ = "tender_item"  # type: ignore
    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id")
    product_code: str
    name: str
    description: str | None = None
    quantity: float
    unit_of_measure: str

    tender: TenderModel | None = Relationship(back_populates="items")


class TenderAIAnalysisModel(SQLModel, table=True):
    __tablename__ = "tender_ai_analysis"  # type: ignore
    id: UUID = Field(primary_key=True)
    tender_id: UUID = Field(foreign_key="tender.id", unique=True)
    supplier_id: UUID = Field(foreign_key="supplier.id")  # References 'supplier' table
    match_score: float
    match_justification: dict = Field(default=None, sa_column=Column(JSON))
    generated_at: datetime

    tender: TenderModel | None = Relationship(back_populates="ai_analysis")


# Cola de ingesta: guarda qué licitaciones se detectaron y cuáles ya se
# procesaron. Al ser persistente, una caída o un 429 de Mercado Público no
# pierde el rastro de lo que falta bajar.
class TenderMetadataModel(SQLModel, table=True):
    __tablename__ = "tender_metadata"  # type: ignore
    id: UUID = Field(primary_key=True)
    code: str = Field(unique=True, index=True)
    is_processed: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now_naive)
    updated_at: datetime = Field(default_factory=utc_now_naive)
