from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# from uuid import UUID
from app.shared.constants import UNKNOWN_TENDER_STATUS
from app.shared.datetime_utils import to_utc_naive


class ItemLicitacionDTO(BaseModel):
    "Mapeo de la tabla item_licitacion"

    correlativo: int | None = None
    codigo_unspsc: int | None = None
    codigo_categoria: str | None = None
    categoria: str | None = None
    nombre_producto: str
    descripcion: str | None = None
    cantidad: float
    unidad_medida: str


class TenderIngestaDTO(BaseModel):
    code: str = Field(..., alias="CodigoExterno")
    name: str = Field(..., alias="Nombre")
    description: str | None = Field(None, alias="Descripcion")
    # El id numérico se conserva porque `tender.status_id` es un FK entero, pero
    # ya no decide nada: la guía de la API no publica su significado y el mapa
    # que se usaba venía de la API de Licitaciones, que numera distinto.
    status_code: int = Field(..., alias="CodigoEstado")
    # `estado.codigo` de la API: el enum documentado (publicada, cerrada,
    # desierta, cancelada, proveedor_seleccionado, oc_emitida). Es la fuente de
    # verdad del estado.
    status_semantic_code: str = Field(UNKNOWN_TENDER_STATUS, alias="EstadoCodigo")
    published_at: datetime = Field(..., alias="FechaPublicacion")
    closing_at: datetime = Field(..., alias="FechaCierre")
    buyer_rut: str = Field(..., alias="RutComprador")
    buyer_name: str = Field(..., alias="NombreOrganismo")
    buyer_unit: str = Field(..., alias="UnidadCompra")
    # La API entrega el id de región como entero (`institucion.region`). Se toma
    # ese dato en vez de deducirlo del nombre: deducirlo obligaba a mantener una
    # tabla de alias con acentos y variantes, y a inventar un valor por defecto
    # cuando ninguna calzaba.
    region_id: int = Field(..., alias="RegionId")
    region_name: str = Field(..., alias="RegionUnidad")

    available_amount_clp: float | None = Field(None, alias="MontoEstimado")
    items: list[ItemLicitacionDTO] = []

    class Config:
        populate_by_name = True

    @field_validator("status_semantic_code", mode="before")
    @classmethod
    def _normalizar_estado(cls, valor: str | None) -> str:
        """Minúsculas y sin espacios, y el vacío equivale a ausente.

        `desconocido` no está en ACTIVE_TENDER_STATUSES, así que una licitación
        sin código no se recomienda: ante la duda no se afirma que esté abierta.
        """
        if valor is None:
            return UNKNOWN_TENDER_STATUS
        return valor.strip().lower() or UNKNOWN_TENDER_STATUS

    @field_validator("region_name", mode="after")
    @classmethod
    def strip_region_name(cls, value: str) -> str:
        """La API entrega el nombre con espacios sobrantes ("Región de Tarapacá  ")."""
        return value.strip()

    @field_validator("published_at", "closing_at", mode="after")
    @classmethod
    def normalize_to_utc(cls, value: datetime) -> datetime:
        """Mercado Público entrega estas fechas en hora local de Chile y sin
        offset. Se normalizan a UTC naive aquí, en el borde de entrada, para que
        toda la base de datos comparta una única zona horaria."""
        normalized = to_utc_naive(value)
        assert normalized is not None  # el campo es obligatorio, nunca es None
        return normalized
