from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Column, Index
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


# Historial de sincronizaciones. Su única razón de ser es el cursor: hasta dónde
# llegó la última corrida que sí alcanzó a listar su ventana completa.
#
# Sin esto, cada corrida pedía "las últimas 24 h contadas desde ahora". Con el
# scheduler dentro del proceso web casi nunca fallaba, porque el proceso está
# siempre vivo; con un cron diario sí, porque una ejecución que no corre deja un
# hueco que nadie vuelve a mirar. De paso, la tabla es el registro de qué hizo
# el cron cada día sin tener que leer logs.
class IngestionRunModel(SQLModel, table=True):
    __tablename__ = "ingestion_run"  # type: ignore
    id: UUID = Field(primary_key=True)
    started_at: datetime = Field(default_factory=utc_now_naive)
    finished_at: datetime | None = Field(default=None)
    # Ventana consultada. `window_to` de la última corrida `ok` es el cursor.
    window_from: datetime
    window_to: datetime
    # Cuántas quedaron encoladas, cuántas se procesaron y cuántas fallaron. No
    # alimentan ninguna decisión: son para mirar el historial y entender.
    listed: int = Field(default=0)
    processed: int = Field(default=0)
    failed: int = Field(default=0)
    # "running" | "ok" | "partial" | "failed".
    #
    # `ok` significa **que se listó la ventana entera**, no que se procesara
    # todo. Son cosas distintas a propósito: una vez que los códigos están en
    # `tender_metadata` ya no se pierden, así que el detalle pendiente lo retoma
    # la corrida siguiente desde la cola. Lo que no se puede perder es un tramo
    # de la ventana sin listar, y eso es justo lo que marca `partial`.
    status: str = Field(default="running")
    created_at: datetime = Field(default_factory=utc_now_naive)

    # El cursor se lee como MAX(window_to) WHERE status = 'ok'.
    __table_args__ = (Index("ix_ingestion_run_cursor", "status", "window_to"),)


# Cola de ingesta: guarda qué licitaciones se detectaron y cuáles ya se
# procesaron. Al ser persistente, una caída o un 429 de Mercado Público no
# pierde el rastro de lo que falta bajar.
class TenderMetadataModel(SQLModel, table=True):
    __tablename__ = "tender_metadata"  # type: ignore
    # El SELECT de pendientes filtra por is_processed y ordena por attempts y
    # created_at. Se declara acá y no solo en la migración para que el
    # autogenerate de Alembic no lo vea como un índice de más y proponga
    # borrarlo en la migración siguiente.
    __table_args__ = (
        Index(
            "ix_tender_metadata_cola", "is_processed", "attempts", "created_at"
        ),
    )
    id: UUID = Field(primary_key=True)
    code: str = Field(unique=True, index=True)
    is_processed: bool = Field(default=False, index=True)
    # Veces que se intentó bajar el detalle y falló. Existe por dos razones:
    # ordena la cola —una licitación que falla siempre se va al final en vez de
    # acaparar cada lote— y permite rendirse tras unos cuantos intentos en vez de
    # descartar al primero. Descartar al primero perdía la licitación para
    # siempre, porque el listado deduplica por código y no la vuelve a ofrecer.
    # `server_default` y no solo el default de Python: la columna se agregó a una
    # tabla que ya tenía filas en producción, y un NOT NULL sin default las
    # habría rechazado. Se declara acá además de en la migración para que el
    # autogenerate de Alembic no proponga quitarlo en la migración siguiente.
    attempts: int = Field(
        default=0, nullable=False, sa_column_kwargs={"server_default": "0"}
    )
    # Último error, para saber por qué quedó atrás sin tener que reproducirlo.
    last_error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now_naive)
    updated_at: datetime = Field(default_factory=utc_now_naive)
