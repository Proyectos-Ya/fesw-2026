from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column, Index, text
from sqlmodel import Field, SQLModel


class SupplierModel(SQLModel, table=True):
    __tablename__ = "supplier"  # type: ignore
    __table_args__ = (
        # Un mismo RUT no puede registrarse dos veces, escriba como se escriba:
        # la expresión quita puntos y guion antes de comparar. Lo crea la
        # migración d7f2a9c41b58; se declara también acá para que el modelo y
        # el esquema coincidan. Sin esto, `alembic revision --autogenerate`
        # proponía borrarlo, y `create_all` no lo creaba en las pruebas.
        # El repositorio traduce su violación buscando este nombre.
        Index(
            "ix_supplier_rut_normalizado",
            text("upper(replace(replace(rut, '.', ''), '-', ''))"),
            unique=True,
        ),
    )
    id: UUID = Field(primary_key=True)
    user_id: UUID | None = Field(
        default=None, foreign_key="users.id", index=True, unique=True
    )
    rut: str
    legal_name: str
    trade_name: str | None = None
    description: str | None = None
    regions: list[str] | None = Field(default=None, sa_column=Column(JSON))
    sectors: list[str] | None = Field(default=None, sa_column=Column(JSON))
    certifications: list[str] | None = Field(default=None, sa_column=Column(JSON))
    keywords: list[str] | None = Field(default=None, sa_column=Column(JSON))
    years_experience: int | None = None
    num_employees: int | None = None
    created_at: datetime
    updated_at: datetime
    profile_changed_at: datetime | None = None
