"""Entrega y requisitos de una Compra Ágil, tal como los documenta el detalle.

Forma según la guía oficial de la API (v3.0, mayo de 2026, §6.3 y §6.6), sin
verificar todavía con una petición real (#294):

    entrega: {"direccion_entrega": "SERVIU REGION DE AYSEN RAMON FREIRE 5",
              "plazo_entrega_dias": 5}
    flags: {"considera_requisitos_medioambientales": true,
            "considera_requisitos_impacto_social_economico": false}

Solo el detalle los trae; el listado no. Ante cualquier forma rara el campo
queda en None, y la ingesta no borra con eso lo que ya estaba guardado.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EntregaMp:
    direccion: str | None
    plazo_dias: int | None


@dataclass(frozen=True)
class RequisitosMp:
    medioambientales: bool | None
    impacto_social: bool | None


def leer_entrega(detail: dict[str, Any]) -> EntregaMp:
    entrega = _objeto(detail.get("entrega"))
    return EntregaMp(
        direccion=_texto(entrega.get("direccion_entrega")),
        plazo_dias=_dias(entrega.get("plazo_entrega_dias")),
    )


def leer_requisitos(detail: dict[str, Any]) -> RequisitosMp:
    flags = _objeto(detail.get("flags"))
    return RequisitosMp(
        medioambientales=_booleano(flags.get("considera_requisitos_medioambientales")),
        impacto_social=_booleano(
            flags.get("considera_requisitos_impacto_social_economico")
        ),
    )


def _objeto(valor: object) -> dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def _texto(valor: object) -> str | None:
    """Sin espacios al borde; vacía es None, porque no dice dónde entregar."""
    if not isinstance(valor, str):
        return None
    return valor.strip() or None


def _dias(valor: object) -> int | None:
    # `bool` es subclase de `int`: `type(...) is int` deja fuera a `True`.
    return valor if type(valor) is int and valor >= 0 else None


def _booleano(valor: object) -> bool | None:
    """Solo `true` o `false`: un 1 o un "true" no se toman por un sí."""
    return valor if isinstance(valor, bool) else None
