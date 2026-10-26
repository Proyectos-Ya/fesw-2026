"""Filtro de Qdrant y índices de payload compartidos por las colecciones de licitaciones.

Las colecciones "tenders" (un vector por licitación) y "tender_items" (un
multivector por licitación, con un vector por partida) guardan el MISMO payload y
se filtran con los MISMOS criterios: son dos canales para recuperar licitaciones y
el usuario espera que un filtro de estado, región o plazo signifique lo mismo en
ambos. Tener la traducción en un solo lugar evita que dos copias diverjan y que la
misma búsqueda devuelva cosas distintas según el canal.
"""

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Condition,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    Range,
)

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.shared.datetime_utils import to_utc_epoch

# Campos del payload por los que se pre-filtra, con el tipo que Qdrant usa para
# indexarlos. El tipo importa: un rango sobre un campo indexado como `keyword` no
# compara como número.
PAYLOAD_INDEXES: dict[str, str] = {
    "status_code": "keyword",
    "region_id": "integer",
    "provincia_id": "integer",
    "comuna_id": "integer",
    "available_amount_clp": "float",
    "closing_at": "integer",
    "published_at": "integer",
}


async def ensure_payload_indexes(client: AsyncQdrantClient, collection_name: str) -> None:
    """Crea en la colección los índices de payload de los campos por los que se filtra.

    Sin índice de payload, Qdrant no puede estimar la cardinalidad de un filtro, y
    esa estimación es la que decide entre recorrer el grafo HNSW enmascarando o
    hacer fuerza bruta sobre los puntos que pasan el filtro. Sin ella elige mal y
    el rendimiento se degrada en silencio, sin que ninguna consulta falle.

    Es idempotente en Qdrant, así que se puede llamar siempre, también cuando la
    colección ya existía: crearlos solo al crearla significaría que ningún entorno
    existente los tendría nunca sin borrar y reindexar.
    """
    for field_name, field_schema in PAYLOAD_INDEXES.items():
        await client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=field_schema,  # type: ignore[arg-type]
        )


def build_filter(criteria: TenderFilterCriteria | None) -> Filter | None:
    """Traduce el criterio de la capa de aplicación al `Filter` de Qdrant.

    Es el único punto donde el vocabulario de negocio se convierte en tipos
    de Qdrant, y donde las fechas pasan a epoch.
    """
    if criteria is None:
        return None

    # `Condition` y no `FieldCondition`: `Filter.must` es invariante en el
    # tipo del elemento y no acepta la lista del subtipo.
    conditions: list[Condition] = []

    # Listas -> MatchAny. `MatchValue` compara contra un único valor, así que
    # no sirve para "estado publicada o cerrada".
    if criteria.status_codes:
        conditions.append(
            FieldCondition(
                key="status_code", match=MatchAny(any=list(criteria.status_codes))
            )
        )
    if criteria.region_ids:
        conditions.append(
            FieldCondition(key="region_id", match=MatchAny(any=list(criteria.region_ids)))
        )
    # `MatchValue`, no `MatchAny`: a diferencia de región, provincia/comuna
    # son un solo valor (el frontend las selecciona de a una, en cascada).
    if criteria.province_id is not None:
        conditions.append(
            FieldCondition(
                key="provincia_id", match=MatchValue(value=criteria.province_id)
            )
        )
    if criteria.commune_id is not None:
        conditions.append(
            FieldCondition(key="comuna_id", match=MatchValue(value=criteria.commune_id))
        )

    # Rangos. `gte`/`lte` mantienen ambos extremos inclusivos, igual que el
    # filtro de presupuesto del frontend.
    rangos = (
        ("closing_at", criteria.closing_from, criteria.closing_to),
        ("published_at", criteria.published_from, criteria.published_to),
    )
    for key, desde, hasta in rangos:
        if desde is None and hasta is None:
            continue
        conditions.append(
            FieldCondition(
                key=key,
                range=Range(
                    gte=to_utc_epoch(desde) if desde else None,
                    lte=to_utc_epoch(hasta) if hasta else None,
                ),
            )
        )

    if criteria.min_amount is not None or criteria.max_amount is not None:
        conditions.append(
            FieldCondition(
                key="available_amount_clp",
                range=Range(gte=criteria.min_amount, lte=criteria.max_amount),
            )
        )

    # `Filter(must=[])` en Qdrant no equivale a "sin filtro": devolver None
    # es lo que deja la búsqueda sin restricciones.
    return Filter(must=conditions) if conditions else None
