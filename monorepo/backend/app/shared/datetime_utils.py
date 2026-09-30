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

from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import PlainSerializer

CHILE_TZ = ZoneInfo("America/Santiago")


def utc_now_naive() -> datetime:
    """Instante actual en UTC, sin tzinfo, listo para persistir."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_utc_naive(value: datetime | None) -> datetime | None:
    """Normaliza una fecha a UTC naive.

    Un valor naive se asume en hora de Chile (el caso de Mercado Público);
    `ZoneInfo` aplica el horario de verano que corresponda a esa fecha. Un valor
    con tzinfo se convierte desde su propio offset.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=CHILE_TZ)
    return value.astimezone(UTC).replace(tzinfo=None)


def leer_fecha_mp(valor: str | None) -> datetime | None:
    """Lee una fecha de Mercado Público como hora de Chile, naive.

    **Ignora la "Z" y cualquier offset.** Verificado contra la API real el
    2026-09-28: el listado etiqueta con "Z" fechas que están en hora de Chile
    (`fecha_ultimo_cambio`, `fecha_cierre_primer_llamado`), mientras que
    `fecha_cierre` y el detalle vienen sin zona. Tomar la Z como UTC corría esas
    fechas 3-4 h. La hora de pared es siempre la de Chile.

    Devuelve `None` si no hay valor o no se puede leer: la decisión de qué hacer
    ante la duda es de quien llama.
    """
    if not valor:
        return None
    try:
        # `fromisoformat` (3.11+) lee tanto "2026-09-29 13:30" como
        # "2026-09-28T13:20:00.353Z".
        return datetime.fromisoformat(valor.strip()).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def fecha_mp_a_utc(valor: str | None) -> datetime | None:
    """Una fecha de Mercado Público convertida a UTC naive, lista para persistir."""
    return to_utc_naive(leer_fecha_mp(valor))


def to_utc_epoch(value: datetime) -> int:
    """Convierte a segundos epoch UTC, para los filtros de rango de Qdrant.

    El payload de Qdrant no guarda `datetime`: guarda enteros comparables.

    Un valor naive se asume ya en UTC (invariante de persistencia). El
    `replace(tzinfo=UTC)` no es redundante: `datetime.timestamp()` sobre un naive
    lo interpreta en la zona horaria **del sistema**, así que en Chile el
    resultado se correría 3 o 4 horas y el mismo dato daría epochs distintos en
    una máquina local y en el contenedor.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp())


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
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


# Tipo para los campos datetime de las entidades expuestas por la API.
# `when_used="json"` deja intacto el `model_dump()` en modo Python, que los
# repositorios usan para escribir en la base de datos.
UtcDateTime = Annotated[
    datetime,
    PlainSerializer(serialize_utc, return_type=str, when_used="json"),
]
