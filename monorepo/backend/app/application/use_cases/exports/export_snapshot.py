"""Los datos de una exportación, ya reunidos (HdU 19).

Los renderers de PDF y Excel reciben esto y nada más: no tocan la base, así que
pueden correr en un hilo aparte —o terminar después de que la petición respondió—
sin cargar con una sesión abierta.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.quotation import Quotation
from app.domain.entities.tender import Tender


class ExportSection(StrEnum):
    """Lo que el usuario puede marcar o desmarcar antes de generar el Excel (criterio 5)."""

    DATOS_GENERALES = "datos_generales"
    MONTOS = "montos"
    ITEMS = "items"
    HITOS = "hitos"
    ANALISIS_IA = "analisis_ia"


@dataclass(frozen=True)
class KeyDate:
    label: str
    # UTC naive, como todas las fechas del dominio.
    at: datetime


def key_dates_for(tender: Tender) -> list[KeyDate]:
    """Los hitos de la licitación.

    Hoy son las fechas oficiales de Mercado Público. Es el único punto que cambia
    cuando los hitos extraídos por IA (HU-16) lleguen a develop.
    """
    return [
        KeyDate(label="Publicación", at=tender.published_at),
        KeyDate(label="Cierre de postulación", at=tender.closing_at),
    ]


@dataclass(frozen=True)
class ExportSnapshot:
    tender: Tender
    supplier_name: str
    score_pct: int | None
    analysis: DeepAnalysis | None
    quotation: Quotation | None
    key_dates: list[KeyDate]
    generated_at: datetime
