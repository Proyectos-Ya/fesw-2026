"""Utilidades de fecha/hora con una sola fuente de verdad para la zona horaria.

Regla del proyecto: **toda** fecha persistida en PostgreSQL se guarda como
`datetime` naive en **UTC**. Las columnas son `TIMESTAMP WITHOUT TIME ZONE`, por
lo que el offset no viaja con el dato; la convención lo suple.

Las conversiones ocurren únicamente en los bordes del sistema:

* **Entrada**: la API de Mercado Público entrega fechas naive en hora de Chile.
  `to_utc_naive` las normaliza a UTC durante la ingesta.
* **Salida**: `serialize_utc` emite ISO-8601 con sufijo ``Z`` para que el
  frontend pueda convertir a la zona horaria del navegador. Sin ese sufijo,
  JavaScript interpreta el string como hora local y muestra la hora corrida.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional
from zoneinfo import ZoneInfo

from pydantic import PlainSerializer

CHILE_TZ = ZoneInfo("America/Santiago")


def utc_now_naive() -> datetime:
    """Instante actual en UTC, sin tzinfo, listo para persistir."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    """Normaliza una fecha a UTC naive.

    Un valor naive se asume en hora de Chile (el caso de Mercado Público);
    `ZoneInfo` aplica el horario de verano que corresponda a esa fecha. Un valor
    con tzinfo se convierte desde su propio offset.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=CHILE_TZ)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def serialize_utc(value: datetime) -> str:
    """Serializa a ISO-8601 UTC con sufijo ``Z``.

    Un valor naive se asume ya en UTC (invariante de persistencia).
    """
    if not isinstance(value, datetime):
        # Guarda de runtime: Pydantic podría entregar un valor sin validar.
        raise TypeError(  # pyright: ignore[reportUnreachable]
            f"serialize_utc espera un datetime, recibió {type(value).__name__}"
        )
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Tipo para los campos datetime de las entidades expuestas por la API.
# `when_used="json"` deja intacto el `model_dump()` en modo Python, que los
# repositorios usan para escribir en la base de datos.
UtcDateTime = Annotated[
    datetime,
    PlainSerializer(serialize_utc, return_type=str, when_used="json"),
]
