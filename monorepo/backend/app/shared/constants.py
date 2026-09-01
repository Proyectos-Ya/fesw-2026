"""Constantes compartidas del dominio de licitaciones.

Las regiones viven en `app.shared.regions`, que es su fuente de verdad única.
"""

# Diccionario con los códigos de estado de las licitaciones (Compra Ágil v2)
# Las claves están en inglés y los valores correspondientes en español según la API.
TENDER_STATUSES = {
    "PUBLISHED": "publicada",
    "CLOSED": "cerrada",
    "DESERTED": "desierta",
    "CANCELLED": "cancelada",
    "SUPPLIER_SELECTED": "proveedor_seleccionado",
    "PO_ISSUED": "oc_emitida",
}

# Estado para una licitación cuyo `estado.codigo` no llegó o no se reconoce.
# Deliberadamente fuera de ACTIVE_TENDER_STATUSES: sin saber el estado, no se
# afirma que esté abierta.
UNKNOWN_TENDER_STATUS = "desconocido"

# Estados que se consideran activos/abiertos para efectos de recomendación.
ACTIVE_TENDER_STATUSES = {TENDER_STATUSES["PUBLISHED"]}

# Mapeo del `id_estado` numérico de Compra Ágil v2 al código semántico.
# Fuente de verdad única: la usan la ingesta (payload de Qdrant), el seeder y el
# repositorio SQL al construir la entidad Tender, para que el filtro de matching
# compare siempre contra los mismos valores.
#
# **Medido, no supuesto.** La guía oficial documenta `estado.codigo` como enum de
# strings pero no publica la numeración. El 28 de agosto de 2026 se consultó el
# listado con `estado=<valor>` y una ventana de 7 días, registrando qué
# `id_estado` devolvía cada uno. Los valores anteriores —1, 7, 8 y 18— venían
# heredados de la API de Licitaciones, que usa otra numeración, y tenían el 6
# mapeado a "publicada" cuando en realidad es "desierta".
#
# `proveedor_seleccionado` devolvió 0 resultados y `oc_emitida` un 400, así que
# sus ids siguen sin observarse. No se inventan: un id desconocido cae en
# "desconocido" y queda fuera de las recomendaciones, que es lo prudente.
TENDER_STATUS_CODE_BY_ID = {
    2: TENDER_STATUSES["PUBLISHED"],
    3: TENDER_STATUSES["CLOSED"],
    5: TENDER_STATUSES["CANCELLED"],
    6: TENDER_STATUSES["DESERTED"],
}


# Ids de estado que el código necesita nombrar. Se derivan del mapa de arriba en
# vez de repetirse como literales: si la numeración medida vuelve a cambiar —ya
# pasó una vez, ver la migración b9e6574f8007— se corrige en un solo lugar.
PUBLICADA_STATUS_ID = next(
    i for i, c in TENDER_STATUS_CODE_BY_ID.items() if c == TENDER_STATUSES["PUBLISHED"]
)
CERRADA_STATUS_ID = next(
    i for i, c in TENDER_STATUS_CODE_BY_ID.items() if c == TENDER_STATUSES["CLOSED"]
)


# Valores por defecto para la API de Mercado Público
DEFAULT_MERCADOPUBLICO_FETCHING_LIMIT = 2000
DEFAULT_MERCADOPUBLICO_DETAIL_DELAY = 2.0
# Detalles en vuelo a la vez. Más del 85% del tiempo por licitación es red y una
# pausa artificial, así que solapar las descargas es lo único que mueve la aguja.
# Cinco es conservador a propósito: la API aplica un balde de tokens de capacidad
# pequeña y responde 429 cuando se la aprieta, aunque el backoff del cliente lo
# absorbe. Subirlo sin medir es la forma rápida de gastar la cuota en reintentos.
DEFAULT_MERCADOPUBLICO_DETAIL_CONCURRENCY = 5


# Umbral "verde" de compatibilidad (HdU 03 y HdU 08). Se expresa en la misma
# escala 0..1 que `MatchingResult.final_score`, no en porcentaje: quien muestre
# un porcentaje multiplica por 100 en el borde.
#
# Es el valor por defecto de las alertas; cada usuario puede fijar el suyo en
# `notification_preference.threshold`.
HIGH_COMPATIBILITY_THRESHOLD = 0.70
