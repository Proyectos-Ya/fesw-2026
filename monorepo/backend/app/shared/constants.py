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
