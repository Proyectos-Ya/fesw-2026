# Regiones de Chile en la numeración administrativa, que es la que Mercado
# Público entrega en `institucion.region`. Verificado contra la API el 21 de
# agosto de 2026: las 16 regiones aparecen con estos ids.
#
# Fuente de verdad única para el seeder y para cualquier traducción entre
# nombre e id. Antes existían dos numeraciones —el seeder ordenaba de norte a
# sur y la ingesta usaba esta— que no coincidían en ninguna región, así que una
# licitación de la Metropolitana terminaba etiquetada como "Los Ríos".
CHILE_REGIONS: dict[int, str] = {
    1: "Tarapacá",
    2: "Antofagasta",
    3: "Atacama",
    4: "Coquimbo",
    5: "Valparaíso",
    6: "Libertador General Bernardo O'Higgins",
    7: "Maule",
    8: "Biobío",
    9: "La Araucanía",
    10: "Los Lagos",
    11: "Aysén del General Carlos Ibáñez del Campo",
    12: "Magallanes y de la Antártica Chilena",
    13: "Metropolitana de Santiago",
    14: "Los Ríos",
    15: "Arica y Parinacota",
    16: "Ñuble",
}

# Fila de respaldo para licitaciones cuya región no llega en la respuesta.
# `buyer_institution.region_id` es clave foránea, así que necesita apuntar a algo;
# un id propio deja el caso visible en vez de disfrazarlo de una región real.
UNKNOWN_REGION_ID = 0
UNKNOWN_REGION_NAME = "Desconocida"

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
