from pydantic import BaseModel, Field, field_validator

from app.domain.entities.supplier import (
    CertificationItem,
    dedupe_certifications,
    normalize_certifications,
)


class CreateSupplierSchema(BaseModel):
    rut: str = Field(max_length=12)
    legal_name: str = Field(min_length=2, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=30, max_length=1000)
    regions: list[str] = Field(min_length=1)
    sectors: list[str] = Field(min_length=1)
    certifications: list[CertificationItem] | None = None
    keywords: list[str] | None = None
    years_experience: int = Field(ge=0, le=100)
    num_employees: int = Field(ge=1, le=100000)

    @field_validator("certifications", mode="before")
    @classmethod
    def coerce_certifications(cls, value: object) -> object:
        return normalize_certifications(value)

    @field_validator("certifications")
    @classmethod
    def unique_certifications(
        cls, value: list[CertificationItem] | None
    ) -> list[CertificationItem] | None:
        return dedupe_certifications(value)


class UpdateSupplierSchema(BaseModel):
    """Edición parcial de la empresa: solo se actualizan los campos enviados.

    El RUT no es editable (identidad tributaria de la empresa).
    """

    legal_name: str | None = Field(default=None, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    regions: list[str] | None = None
    sectors: list[str] | None = None
    certifications: list[CertificationItem] | None = None
    keywords: list[str] | None = None
    years_experience: int | None = Field(default=None, ge=0)
    num_employees: int | None = Field(default=None, ge=1)

    @field_validator("certifications", mode="before")
    @classmethod
    def coerce_certifications(cls, value: object) -> object:
        return normalize_certifications(value)

    @field_validator("certifications")
    @classmethod
    def unique_certifications(
        cls, value: list[CertificationItem] | None
    ) -> list[CertificationItem] | None:
        return dedupe_certifications(value)


class RutExistsResponse(BaseModel):
    """Respuesta de la verificación temprana de RUT duplicado."""

    exists: bool


class SuggestKeywordsRequest(BaseModel):
    """Descripción de la empresa de la que se sacan palabras clave."""

    # Mismo largo máximo que la descripción de la empresa en `CreateSupplierSchema`.
    description: str = Field(max_length=1000)
    # Las que el usuario ya eligió; no se vuelven a sugerir.
    existing_keywords: list[str] = Field(default_factory=list, max_length=200)


class SuggestKeywordsResponse(BaseModel):
    suggested_keywords: list[str]
