"""Formatos comunes del PDF y el Excel: moneda y hora de Chile."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote

from app.shared.datetime_utils import CHILE_TZ

NO_INFORMADO = "No informado"


def to_chile(value: datetime) -> datetime:
    """UTC naive → hora de Chile naive, que es lo que Excel y el lector esperan ver."""
    return value.replace(tzinfo=UTC).astimezone(CHILE_TZ).replace(tzinfo=None)


def format_chile(value: datetime) -> str:
    return to_chile(value).strftime("%d-%m-%Y %H:%M")


def _miles(entero: int) -> str:
    return f"{entero:,}".replace(",", ".")


def format_money(amount: Decimal | float | None, currency: str = "CLP") -> str:
    """`$1.234.567` en pesos; `USD 1.234,50` en otras monedas."""
    if amount is None:
        return NO_INFORMADO
    valor = Decimal(str(amount))
    if currency == "CLP":
        entero = int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return f"${_miles(entero)}"
    centavos = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    entero, _, decimales = f"{centavos:.2f}".partition(".")
    return f"{currency} {_miles(int(entero))},{decimales}"


def mercado_publico_url(code: str) -> str:
    # Misma ficha que enlaza el frontend (`compraAgilFichaUrl`).
    return f"https://buscador.mercadopublico.cl/ficha?code={quote(code, safe='')}"
