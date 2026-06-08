from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


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
    id: UUID =  Field(default_factory=uuid4)
    rut: str
    legal_name: str
    trade_name: Optional[str] = None
    description: Optional[str] = None
    regions: Optional[list[str]] = None
    sectors: Optional[list[str]] = None
    certifications: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    years_experience: Optional[int] = None
    num_employees: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    @field_validator("rut")
    @classmethod
    def validate_rut(cls, value: str) -> str:
        """Valida que el RUT tenga formato y dígito verificador correcto."""
        if not is_valid_rut(value):
            raise ValueError("RUT format is invalid")
        return value