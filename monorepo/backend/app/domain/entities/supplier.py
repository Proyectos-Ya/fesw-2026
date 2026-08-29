from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.shared.datetime_utils import UtcDateTime, utc_now_naive


def is_valid_rut(rut: str) -> bool:
    """Valida el formato y dígito verificador de un RUT chileno."""
    # Limpia puntos y guión
    cleaned = rut.replace(".", "").replace("-", "").upper()

    if len(cleaned) < 2:
        return False

    body = cleaned[:-1]
    check_digit = cleaned[-1]

    if not body.isdigit():
        return False

    # Calcula el dígito verificador con módulo 11
    reversed_digits = [int(d) for d in reversed(body)]
    multipliers = [2, 3, 4, 5, 6, 7]
    total = sum(d * multipliers[i % 6] for i, d in enumerate(reversed_digits))
    remainder = 11 - (total % 11)

    if remainder == 11:
        expected = "0"
    elif remainder == 10:
        expected = "K"
    else:
        expected = str(remainder)

    return check_digit == expected


class Supplier(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID | None = None  # ID del usuario propietario de esta cuenta proveedor
    rut: str
    legal_name: str
    trade_name: str | None = None
    description: str | None = None
    regions: list[str] | None = None
    sectors: list[str] | None = None
    certifications: list[str] | None = None
    keywords: list[str] | None = None
    years_experience: int | None = None
    num_employees: int | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)
    # Última vez que cambió el contenido que alimenta el matching (embedding)
    profile_changed_at: UtcDateTime | None = None

    @field_validator("rut")
    @classmethod
    def validate_rut(cls, value: str) -> str:
        """Valida que el RUT tenga formato y dígito verificador correcto."""
        if not is_valid_rut(value):
            raise ValueError("RUT format is invalid")
        return value
