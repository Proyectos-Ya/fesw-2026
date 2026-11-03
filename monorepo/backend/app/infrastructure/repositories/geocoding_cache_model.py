from datetime import datetime

from sqlalchemy import Double, Text
from sqlmodel import Field, SQLModel

from app.shared.datetime_utils import utc_now_naive


class GeocodingCacheModel(SQLModel, table=True):
    """Respuestas de Nominatim ya pedidas, por consulta (HU-22, #314).

    Los organismos repiten la misma dirección en muchas licitaciones, y la
    política de uso de Nominatim pide no repetir consultas. `lat`/`lng` nulos =
    Nominatim respondió y no encontró nada, que también se guarda para no
    volver a preguntarlo.
    """

    __tablename__ = "geocoding_cache"  # type: ignore
    # La consulta normalizada (ver `GeocodePendingTendersUseCase`).
    query: str = Field(primary_key=True, sa_type=Text)
    lat: float | None = Field(default=None, sa_type=Double)
    lng: float | None = Field(default=None, sa_type=Double)
    geocoded_at: datetime = Field(default_factory=utc_now_naive)
