"""Vocabulario de la búsqueda de licitaciones, en la capa de aplicación.

Los tipos de Qdrant (`Filter`, `Range`, `FieldCondition`) y los de SQLModel no
cruzan hacia acá: el caso de uso arma un criterio y cada adaptador lo traduce a
su dialecto. Por eso las fechas viajan como `datetime` y no como epoch — el
epoch es un detalle de cómo Qdrant almacena, no vocabulario de negocio.
"""

from datetime import datetime

from pydantic import BaseModel

from app.domain.entities.tender import Tender


class TenderFilterCriteria(BaseModel):
    """Condiciones absolutas que una licitación debe cumplir para ser elegible.

    Se aplican **dentro** de la búsqueda vectorial, no antes ni después. Filtrar
    el top-K ya devuelto rompe el resultado: con un filtro que deja pasar el 4%
    del corpus, un top-50 entrega ~2 resultados habiendo cientos que califican, y
    empeora mientras más específico sea el filtro — justo al revés de lo que
    espera quien filtra.

    Estas condiciones son binarias, no señales de relevancia: una licitación de
    otra región no es "menos relevante", simplemente no califica. Por eso no
    entran al ranking sino al conjunto elegible, cuyo tamaño es el total de
    coincidencias que se le muestra al usuario.

    No incluye el texto de búsqueda ni la paginación a propósito: el texto se
    convierte en vector y la paginación recorta el resultado ya ordenado. Son
    etapas distintas, y mezclarlas permitiría que el total dependiera de la
    página.
    """

    region_ids: list[int] | None = None
    status_codes: list[str] | None = None
    closing_from: datetime | None = None
    closing_to: datetime | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    # Límites inclusivos, igual que `tenderMatchesBudget` en el frontend. Una
    # licitación sin monto queda fuera cuando el filtro está activo: Qdrant no
    # hace calzar una condición de rango contra un campo ausente o nulo, que es
    # el mismo criterio que ya aplica el dashboard.
    min_amount: float | None = None
    max_amount: float | None = None


class TenderSearchResult(BaseModel):
    """Respuesta de una búsqueda manual.

    `total` no es `len(items)`: sale de contar cuántas licitaciones pasan los
    filtros, así que no cambia aunque el resultado venga recortado. Es el número
    de coincidencias que se le muestra al usuario.

    `is_truncated` avisa que quedaron licitaciones fuera del corte. Sin él, el
    frontend mostraría "137 coincidencias" junto a 500 tarjetas sin explicación;
    con él puede sugerir afinar los filtros, que es lo correcto cuando alguien
    pide un universo tan amplio.
    """

    items: list[Tender]
    total: int
    is_truncated: bool = False
