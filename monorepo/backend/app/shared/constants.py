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

# Estados que se consideran activos/abiertos para efectos de recomendación.
ACTIVE_TENDER_STATUSES = {TENDER_STATUSES["PUBLISHED"]}

# Mapeo del CodigoEstado numérico de Mercado Público al código semántico.
# Fuente de verdad única: la usan la ingesta (payload de Qdrant) y el
# repositorio SQL al construir la entidad Tender, para que el filtro de
# matching compare siempre contra los mismos valores.
TENDER_STATUS_CODE_BY_ID = {
    1: TENDER_STATUSES["PUBLISHED"],
    2: TENDER_STATUSES["PUBLISHED"],
    6: TENDER_STATUSES["PUBLISHED"],
    7: TENDER_STATUSES["CLOSED"],
    8: TENDER_STATUSES["DESERTED"],
    18: "adjudicada",
}

# Valores por defecto para la API de Mercado Público
DEFAULT_MERCADOPUBLICO_FETCHING_LIMIT = 2000
DEFAULT_MERCADOPUBLICO_DETAIL_DELAY = 2.0

