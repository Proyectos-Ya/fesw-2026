import unicodedata
from datetime import date
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, StringConstraints, field_validator

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


def format_rut(rut: str) -> str:
    """Devuelve el RUT en formato canónico XX.XXX.XXX-X.

    Se guarda siempre así para que la búsqueda de duplicados, que compara el
    texto exacto, no dependa de cómo lo escribió el cliente.
    """
    cleaned = rut.strip().replace(".", "").replace("-", "").upper()
    body, check_digit = cleaned[:-1], cleaned[-1]
    return f"{int(body):,}".replace(",", ".") + f"-{check_digit}"


class CertificationItem(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    expires_at: date | None = None


def normalize_certifications(value: object) -> object:
    """Convierte los strings sueltos de registros antiguos en CertificationItem.

    Los strings en blanco se descartan: rechazarlos impediría leer la empresa.
    Lo demás (dicts, instancias, None) pasa tal cual para que Pydantic lo valide.
    """
    if not isinstance(value, list):
        return value
    return [
        {"name": item} if isinstance(item, str) else item
        for item in value
        if not (isinstance(item, str) and not item.strip())
    ]


def _clave_certificacion(name: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", name).encode("ascii", "ignore")
    return sin_tildes.decode().casefold()


def dedupe_certifications(
    items: list[CertificationItem] | None,
) -> list[CertificationItem] | None:
    """Quita las certificaciones repetidas, sin distinguir mayúsculas ni tildes.

    Conserva la primera aparición, que es la que trae la fecha que el usuario vio.
    """
    if items is None:
        return None
    vistas: set[str] = set()
    unicas = []
    for item in items:
        clave = _clave_certificacion(item.name)
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(item)
    return unicas


class Supplier(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID | None = None  # ID del usuario propietario de esta cuenta proveedor
    rut: str
    legal_name: str
    trade_name: str | None = None
    description: str | None = None
    regions: list[str] | None = None
    sectors: list[str] | None = None
    certifications: list[CertificationItem] | None = None
    keywords: list[str] | None = None
    years_experience: int | None = None
    num_employees: int | None = None
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)
    # Última vez que cambió el contenido que alimenta el matching (embedding)
    profile_changed_at: UtcDateTime | None = None

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

    @property
    def certification_names(self) -> list[str]:
        """Nombres de las certificaciones, para prompts, texto y catálogos."""
        return [item.name for item in self.certifications or []]

    @field_validator("rut")
    @classmethod
    def validate_rut(cls, value: str) -> str:
        """Valida el dígito verificador y deja el RUT en formato canónico."""
        if not is_valid_rut(value.strip()):
            raise ValueError("RUT format is invalid")
        return format_rut(value)
