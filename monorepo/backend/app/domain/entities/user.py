import re
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.shared.datetime_utils import UtcDateTime, utc_now_naive

# Validación de email simple y suficiente (evita sumar dependencia email-validator).
# Exige un dominio con punto y TLD de al menos 2 caracteres.
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def is_valid_email(email: str) -> bool:
    """Valida el formato básico de un correo electrónico."""
    return bool(_EMAIL_REGEX.match(email))


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str
    hashed_password: str
    full_name: str
    phone: str | None = None
    active: bool = True
    email_verified: bool = False
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normaliza a minúsculas y valida el formato del correo."""
        normalized = value.strip().lower()
        if not is_valid_email(normalized):
            raise ValueError("Email format is invalid")
        return normalized
