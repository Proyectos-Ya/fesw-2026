import uuid
from typing import Any

from pydantic import BaseModel, Field


class ProviderPayload(BaseModel):
    """Metadata del proveedor que se almacena junto al vector en Qdrant."""

    provider_id: uuid.UUID
    company_name: str
    description: str
    rubros: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    experience_years: int = 0
    employee_count: int = 0
    keywords: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convierte el payload a un diccionario serializable para Qdrant."""
        return {
            "provider_id": str(self.provider_id),
            "company_name": self.company_name,
            "description": self.description,
            "rubros": self.rubros,
            "regions": self.regions,
            "experience_years": self.experience_years,
            "employee_count": self.employee_count,
            "keywords": self.keywords,
        }


class Vector(BaseModel):
    """Modelo de dominio que representa un vector listo para almacenar en la base vectorial."""

    # Identificador único del punto en Qdrant (debe ser UUID o entero)
    id: uuid.UUID = Field(default_factory=uuid.uuid4)

    # Nombre de la colección donde se guardará el vector
    collection_name: str

    # El embedding generado por el modelo (ej: BGE-M3 produce 1024 dimensiones)
    embedding: list[float]

    # Metadata adicional almacenada junto al vector para filtros y recuperación
    payload: ProviderPayload