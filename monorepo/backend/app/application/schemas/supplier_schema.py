from pydantic import BaseModel, Field


class CreateSupplierSchema(BaseModel):
    rut: str = Field(max_length=12)
    legal_name: str = Field(min_length=2, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=30, max_length=1000)
    regions: list[str] = Field(min_length=1)
    sectors: list[str] = Field(min_length=1)
    certifications: list[str] | None = None
    keywords: list[str] | None = None
    years_experience: int = Field(ge=0, le=100)
    num_employees: int = Field(ge=1, le=100000)


class UpdateSupplierSchema(BaseModel):
    """Edición parcial de la empresa: solo se actualizan los campos enviados.

    El RUT no es editable (identidad tributaria de la empresa).
    """

    legal_name: str | None = Field(default=None, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    regions: list[str] | None = None
    sectors: list[str] | None = None
    certifications: list[str] | None = None
    keywords: list[str] | None = None
    years_experience: int | None = Field(default=None, ge=0)
    num_employees: int | None = Field(default=None, ge=1)


class RutExistsResponse(BaseModel):
    """Respuesta de la verificación temprana de RUT duplicado."""

    exists: bool
