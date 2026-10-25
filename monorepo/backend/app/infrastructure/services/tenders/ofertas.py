"""Total de ofertas recibidas de cada licitación, tal como lo entrega Mercado Público.

Forma verificada en el listado real del 2026-09-28
(`tests/fixtures/mp_listado_cambios.json`):

    resumen: {"total_ofertas_recibidas": 0}

Lo usan el listado (cron de estados) y el detalle (ingesta): si cada ruta leyera
distinto, una sobrescribiría a la otra en cada pasada. Un 0 es un dato real
(nadie ha cotizado); None significa que la cifra no vino o no es creíble.
"""

from typing import Any


def leer_total_ofertas(item: dict[str, Any]) -> int | None:
    """Entero mayor o igual a 0; cualquier otra cosa es None. Ante la duda no se afirma una cifra."""
    resumen = item.get("resumen")
    if not isinstance(resumen, dict):
        return None
    total = resumen.get("total_ofertas_recibidas")
    # `bool` es subclase de `int`: `type(...) is int` deja fuera a `True` y `False`.
    return total if type(total) is int and total >= 0 else None
