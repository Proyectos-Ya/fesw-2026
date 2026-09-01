"""Fuente de verdad única de la división provincia/comuna de Chile.

346 comunas en 56 provincias en 16 regiones, estable desde la creación de la
Región de Ñuble (2018). A diferencia de la región, ninguna de las tres APIs de
Mercado Público (Compra Ágil, Licitaciones, Órdenes de Compra) entrega comuna
ni provincia directamente — se resuelve por `resolve_comuna` (cascada de
heurísticas sobre el nombre del organismo) o queda sin dato. Ver
PENDIENTES.md 6.16/6.19.

Fuente del dataset: JSON público de
climoralesg/api-regiones-provincias-comunas-Chile, verificado contra los
totales oficiales (16/56/346, sin duplicados de nombre de comuna) y corregido
a mano (12 typos de transcripción del dataset original, ej. "Carahu"→"Carahue",
"Aisén"→"Aysén"). Los nombres de región ya están remapeados a los canónicos de
`regions.py::CHILE_REGIONS` para que `region_id_by_name` resuelva sin fallback.
"""

import re
import unicodedata

# id: (nombre_provincia, nombre_region_canonico)
CHILE_PROVINCIAS: dict[int, tuple[str, str]] = {
    1: ("Arica", "Arica y Parinacota"),
    2: ("Parinacota", "Arica y Parinacota"),
    3: ("Iquique", "Tarapacá"),
    4: ("Tamarugal", "Tarapacá"),
    5: ("Antofagasta", "Antofagasta"),
    6: ("El Loa", "Antofagasta"),
    7: ("Tocopilla", "Antofagasta"),
    8: ("Copiapó", "Atacama"),
    9: ("Chañaral", "Atacama"),
    10: ("Huasco", "Atacama"),
    11: ("Elqui", "Coquimbo"),
    12: ("Choapa", "Coquimbo"),
    13: ("Limarí", "Coquimbo"),
    14: ("Valparaíso", "Valparaíso"),
    15: ("Isla de Pascua", "Valparaíso"),
    16: ("Los Andes", "Valparaíso"),
    17: ("Petorca", "Valparaíso"),
    18: ("Quillota", "Valparaíso"),
    19: ("San Antonio", "Valparaíso"),
    20: ("San Felipe de Aconcagua", "Valparaíso"),
    21: ("Marga Marga", "Valparaíso"),
    22: ("Cachapoal", "Libertador General Bernardo O'Higgins"),
    23: ("Cardenal Caro", "Libertador General Bernardo O'Higgins"),
    24: ("Colchagua", "Libertador General Bernardo O'Higgins"),
    25: ("Talca", "Maule"),
    26: ("Cauquenes", "Maule"),
    27: ("Curicó", "Maule"),
    28: ("Linares", "Maule"),
    29: ("Concepción", "Biobío"),
    30: ("Arauco", "Biobío"),
    31: ("Biobío", "Biobío"),
    32: ("Diguillín", "Ñuble"),
    33: ("Itata", "Ñuble"),
    34: ("Punilla", "Ñuble"),
    35: ("Cautín", "La Araucanía"),
    36: ("Malleco", "La Araucanía"),
    37: ("Valdivia", "Los Ríos"),
    38: ("Ranco", "Los Ríos"),
    39: ("Llanquihue", "Los Lagos"),
    40: ("Chiloé", "Los Lagos"),
    41: ("Osorno", "Los Lagos"),
    42: ("Palena", "Los Lagos"),
    43: ("Coyhaique", "Aysén del General Carlos Ibáñez del Campo"),
    44: ("Aysén", "Aysén del General Carlos Ibáñez del Campo"),
    45: ("Capitán Prat", "Aysén del General Carlos Ibáñez del Campo"),
    46: ("General Carrera", "Aysén del General Carlos Ibáñez del Campo"),
    47: ("Magallanes", "Magallanes y de la Antártica Chilena"),
    48: ("Antártica Chilena", "Magallanes y de la Antártica Chilena"),
    49: ("Tierra del Fuego", "Magallanes y de la Antártica Chilena"),
    50: ("Última Esperanza", "Magallanes y de la Antártica Chilena"),
    51: ("Santiago", "Metropolitana de Santiago"),
    52: ("Cordillera", "Metropolitana de Santiago"),
    53: ("Chacabuco", "Metropolitana de Santiago"),
    54: ("Maipo", "Metropolitana de Santiago"),
    55: ("Melipilla", "Metropolitana de Santiago"),
    56: ("Talagante", "Metropolitana de Santiago"),
}

# id: (nombre_comuna, nombre_provincia)
CHILE_COMUNAS: dict[int, tuple[str, str]] = {
    1: ("Arica", "Arica"),
    2: ("Camarones", "Arica"),
    3: ("Putre", "Parinacota"),
    4: ("General Lagos", "Parinacota"),
    5: ("Iquique", "Iquique"),
    6: ("Alto Hospicio", "Iquique"),
    7: ("Pozo Almonte", "Tamarugal"),
    8: ("Camiña", "Tamarugal"),
    9: ("Colchane", "Tamarugal"),
    10: ("Huara", "Tamarugal"),
    11: ("Pica", "Tamarugal"),
    12: ("Antofagasta", "Antofagasta"),
    13: ("Mejillones", "Antofagasta"),
    14: ("Sierra Gorda", "Antofagasta"),
    15: ("Taltal", "Antofagasta"),
    16: ("Calama", "El Loa"),
    17: ("Ollagüe", "El Loa"),
    18: ("San Pedro de Atacama", "El Loa"),
    19: ("Tocopilla", "Tocopilla"),
    20: ("María Elena", "Tocopilla"),
    21: ("Copiapó", "Copiapó"),
    22: ("Caldera", "Copiapó"),
    23: ("Tierra Amarilla", "Copiapó"),
    24: ("Chañaral", "Chañaral"),
    25: ("Diego de Almagro", "Chañaral"),
    26: ("Vallenar", "Huasco"),
    27: ("Alto del Carmen", "Huasco"),
    28: ("Freirina", "Huasco"),
    29: ("Huasco", "Huasco"),
    30: ("La Serena", "Elqui"),
    31: ("Coquimbo", "Elqui"),
    32: ("Andacollo", "Elqui"),
    33: ("La Higuera", "Elqui"),
    34: ("Paiguano", "Elqui"),
    35: ("Vicuña", "Elqui"),
    36: ("Illapel", "Choapa"),
    37: ("Canela", "Choapa"),
    38: ("Los Vilos", "Choapa"),
    39: ("Salamanca", "Choapa"),
    40: ("Ovalle", "Limarí"),
    41: ("Combarbalá", "Limarí"),
    42: ("Monte Patria", "Limarí"),
    43: ("Punitaqui", "Limarí"),
    44: ("Río Hurtado", "Limarí"),
    45: ("Valparaíso", "Valparaíso"),
    46: ("Casablanca", "Valparaíso"),
    47: ("Concón", "Valparaíso"),
    48: ("Juan Fernández", "Valparaíso"),
    49: ("Puchuncaví", "Valparaíso"),
    50: ("Quintero", "Valparaíso"),
    51: ("Viña del Mar", "Valparaíso"),
    52: ("Isla de Pascua", "Isla de Pascua"),
    53: ("Los Andes", "Los Andes"),
    54: ("Calle Larga", "Los Andes"),
    55: ("Rinconada", "Los Andes"),
    56: ("San Esteban", "Los Andes"),
    57: ("La Ligua", "Petorca"),
    58: ("Cabildo", "Petorca"),
    59: ("Papudo", "Petorca"),
    60: ("Petorca", "Petorca"),
    61: ("Zapallar", "Petorca"),
    62: ("Quillota", "Quillota"),
    63: ("Calera", "Quillota"),
    64: ("Hijuelas", "Quillota"),
    65: ("La Cruz", "Quillota"),
    66: ("Nogales", "Quillota"),
    67: ("San Antonio", "San Antonio"),
    68: ("Algarrobo", "San Antonio"),
    69: ("Cartagena", "San Antonio"),
    70: ("El Quisco", "San Antonio"),
    71: ("El Tabo", "San Antonio"),
    72: ("Santo Domingo", "San Antonio"),
    73: ("San Felipe", "San Felipe de Aconcagua"),
    74: ("Catemu", "San Felipe de Aconcagua"),
    75: ("Llaillay", "San Felipe de Aconcagua"),
    76: ("Panquehue", "San Felipe de Aconcagua"),
    77: ("Putaendo", "San Felipe de Aconcagua"),
    78: ("Santa María", "San Felipe de Aconcagua"),
    79: ("Quilpué", "Marga Marga"),
    80: ("Limache", "Marga Marga"),
    81: ("Olmué", "Marga Marga"),
    82: ("Villa Alemana", "Marga Marga"),
    83: ("Rancagua", "Cachapoal"),
    84: ("Codegua", "Cachapoal"),
    85: ("Coinco", "Cachapoal"),
    86: ("Coltauco", "Cachapoal"),
    87: ("Doñihue", "Cachapoal"),
    88: ("Graneros", "Cachapoal"),
    89: ("Las Cabras", "Cachapoal"),
    90: ("Machalí", "Cachapoal"),
    91: ("Malloa", "Cachapoal"),
    92: ("Mostazal", "Cachapoal"),
    93: ("Olivar", "Cachapoal"),
    94: ("Peumo", "Cachapoal"),
    95: ("Pichidegua", "Cachapoal"),
    96: ("Quinta de Tilcoco", "Cachapoal"),
    97: ("Rengo", "Cachapoal"),
    98: ("Requínoa", "Cachapoal"),
    99: ("San Vicente", "Cachapoal"),
    100: ("Pichilemu", "Cardenal Caro"),
    101: ("La Estrella", "Cardenal Caro"),
    102: ("Litueche", "Cardenal Caro"),
    103: ("Marchihue", "Cardenal Caro"),
    104: ("Navidad", "Cardenal Caro"),
    105: ("Paredones", "Cardenal Caro"),
    106: ("San Fernando", "Colchagua"),
    107: ("Chépica", "Colchagua"),
    108: ("Chimbarongo", "Colchagua"),
    109: ("Lolol", "Colchagua"),
    110: ("Nancagua", "Colchagua"),
    111: ("Palmilla", "Colchagua"),
    112: ("Peralillo", "Colchagua"),
    113: ("Placilla", "Colchagua"),
    114: ("Pumanque", "Colchagua"),
    115: ("Santa Cruz", "Colchagua"),
    116: ("Talca", "Talca"),
    117: ("Constitución", "Talca"),
    118: ("Curepto", "Talca"),
    119: ("Empedrado", "Talca"),
    120: ("Maule", "Talca"),
    121: ("Pelarco", "Talca"),
    122: ("Pencahue", "Talca"),
    123: ("Río Claro", "Talca"),
    124: ("San Clemente", "Talca"),
    125: ("San Rafael", "Talca"),
    126: ("Cauquenes", "Cauquenes"),
    127: ("Chanco", "Cauquenes"),
    128: ("Pelluhue", "Cauquenes"),
    129: ("Curicó", "Curicó"),
    130: ("Hualañé", "Curicó"),
    131: ("Licantén", "Curicó"),
    132: ("Molina", "Curicó"),
    133: ("Rauco", "Curicó"),
    134: ("Romeral", "Curicó"),
    135: ("Sagrada Familia", "Curicó"),
    136: ("Teno", "Curicó"),
    137: ("Vichuquén", "Curicó"),
    138: ("Linares", "Linares"),
    139: ("Colbún", "Linares"),
    140: ("Longaví", "Linares"),
    141: ("Parral", "Linares"),
    142: ("Retiro", "Linares"),
    143: ("San Javier", "Linares"),
    144: ("Villa Alegre", "Linares"),
    145: ("Yerbas Buenas", "Linares"),
    146: ("Concepción", "Concepción"),
    147: ("Coronel", "Concepción"),
    148: ("Chiguayante", "Concepción"),
    149: ("Florida", "Concepción"),
    150: ("Hualqui", "Concepción"),
    151: ("Lota", "Concepción"),
    152: ("Penco", "Concepción"),
    153: ("San Pedro de la Paz", "Concepción"),
    154: ("Santa Juana", "Concepción"),
    155: ("Talcahuano", "Concepción"),
    156: ("Tomé", "Concepción"),
    157: ("Hualpén", "Concepción"),
    158: ("Lebu", "Arauco"),
    159: ("Arauco", "Arauco"),
    160: ("Cañete", "Arauco"),
    161: ("Contulmo", "Arauco"),
    162: ("Curanilahue", "Arauco"),
    163: ("Los Álamos", "Arauco"),
    164: ("Tirúa", "Arauco"),
    165: ("Los Ángeles", "Biobío"),
    166: ("Antuco", "Biobío"),
    167: ("Cabrero", "Biobío"),
    168: ("Laja", "Biobío"),
    169: ("Mulchén", "Biobío"),
    170: ("Nacimiento", "Biobío"),
    171: ("Negrete", "Biobío"),
    172: ("Quilaco", "Biobío"),
    173: ("Quilleco", "Biobío"),
    174: ("San Rosendo", "Biobío"),
    175: ("Santa Bárbara", "Biobío"),
    176: ("Tucapel", "Biobío"),
    177: ("Yumbel", "Biobío"),
    178: ("Alto Biobío", "Biobío"),
    179: ("Bulnes", "Diguillín"),
    180: ("Chillán", "Diguillín"),
    181: ("Chillán Viejo", "Diguillín"),
    182: ("El Carmen", "Diguillín"),
    183: ("Pemuco", "Diguillín"),
    184: ("Pinto", "Diguillín"),
    185: ("Quillón", "Diguillín"),
    186: ("San Ignacio", "Diguillín"),
    187: ("Yungay", "Diguillín"),
    188: ("Cobquecura", "Itata"),
    189: ("Coelemu", "Itata"),
    190: ("Ninhue", "Itata"),
    191: ("Portezuelo", "Itata"),
    192: ("Quirihue", "Itata"),
    193: ("Ránquil", "Itata"),
    194: ("Trehuaco", "Itata"),
    195: ("Coihueco", "Punilla"),
    196: ("Ñiquén", "Punilla"),
    197: ("San Carlos", "Punilla"),
    198: ("San Fabián", "Punilla"),
    199: ("San Nicolás", "Punilla"),
    200: ("Temuco", "Cautín"),
    201: ("Carahue", "Cautín"),
    202: ("Cunco", "Cautín"),
    203: ("Curarrehue", "Cautín"),
    204: ("Freire", "Cautín"),
    205: ("Galvarino", "Cautín"),
    206: ("Gorbea", "Cautín"),
    207: ("Lautaro", "Cautín"),
    208: ("Loncoche", "Cautín"),
    209: ("Melipeuco", "Cautín"),
    210: ("Nueva Imperial", "Cautín"),
    211: ("Padre Las Casas", "Cautín"),
    212: ("Perquenco", "Cautín"),
    213: ("Pitrufquén", "Cautín"),
    214: ("Pucón", "Cautín"),
    215: ("Saavedra", "Cautín"),
    216: ("Teodoro Schmidt", "Cautín"),
    217: ("Toltén", "Cautín"),
    218: ("Vilcún", "Cautín"),
    219: ("Villarrica", "Cautín"),
    220: ("Cholchol", "Cautín"),
    221: ("Angol", "Malleco"),
    222: ("Collipulli", "Malleco"),
    223: ("Curacautín", "Malleco"),
    224: ("Ercilla", "Malleco"),
    225: ("Lonquimay", "Malleco"),
    226: ("Los Sauces", "Malleco"),
    227: ("Lumaco", "Malleco"),
    228: ("Purén", "Malleco"),
    229: ("Renaico", "Malleco"),
    230: ("Traiguén", "Malleco"),
    231: ("Victoria", "Malleco"),
    232: ("Valdivia", "Valdivia"),
    233: ("Corral", "Valdivia"),
    234: ("Lanco", "Valdivia"),
    235: ("Los Lagos", "Valdivia"),
    236: ("Máfil", "Valdivia"),
    237: ("Mariquina", "Valdivia"),
    238: ("Paillaco", "Valdivia"),
    239: ("Panguipulli", "Valdivia"),
    240: ("La Unión", "Ranco"),
    241: ("Futrono", "Ranco"),
    242: ("Lago Ranco", "Ranco"),
    243: ("Río Bueno", "Ranco"),
    244: ("Puerto Montt", "Llanquihue"),
    245: ("Calbuco", "Llanquihue"),
    246: ("Cochamó", "Llanquihue"),
    247: ("Fresia", "Llanquihue"),
    248: ("Frutillar", "Llanquihue"),
    249: ("Los Muermos", "Llanquihue"),
    250: ("Llanquihue", "Llanquihue"),
    251: ("Maullín", "Llanquihue"),
    252: ("Puerto Varas", "Llanquihue"),
    253: ("Castro", "Chiloé"),
    254: ("Ancud", "Chiloé"),
    255: ("Chonchi", "Chiloé"),
    256: ("Curaco de Vélez", "Chiloé"),
    257: ("Dalcahue", "Chiloé"),
    258: ("Puqueldón", "Chiloé"),
    259: ("Queilén", "Chiloé"),
    260: ("Quellón", "Chiloé"),
    261: ("Quemchi", "Chiloé"),
    262: ("Quinchao", "Chiloé"),
    263: ("Osorno", "Osorno"),
    264: ("Puerto Octay", "Osorno"),
    265: ("Purranque", "Osorno"),
    266: ("Puyehue", "Osorno"),
    267: ("Río Negro", "Osorno"),
    268: ("San Juan de la Costa", "Osorno"),
    269: ("San Pablo", "Osorno"),
    270: ("Chaitén", "Palena"),
    271: ("Futaleufú", "Palena"),
    272: ("Hualaihué", "Palena"),
    273: ("Palena", "Palena"),
    274: ("Coyhaique", "Coyhaique"),
    275: ("Lago Verde", "Coyhaique"),
    276: ("Aysén", "Aysén"),
    277: ("Cisnes", "Aysén"),
    278: ("Guaitecas", "Aysén"),
    279: ("Cochrane", "Capitán Prat"),
    280: ("O'Higgins", "Capitán Prat"),
    281: ("Tortel", "Capitán Prat"),
    282: ("Chile Chico", "General Carrera"),
    283: ("Río Ibáñez", "General Carrera"),
    284: ("Punta Arenas", "Magallanes"),
    285: ("Laguna Blanca", "Magallanes"),
    286: ("Río Verde", "Magallanes"),
    287: ("San Gregorio", "Magallanes"),
    288: ("Cabo de Hornos (Ex. Navarino)", "Antártica Chilena"),
    289: ("Antártica", "Antártica Chilena"),
    290: ("Porvenir", "Tierra del Fuego"),
    291: ("Primavera", "Tierra del Fuego"),
    292: ("Timaukel", "Tierra del Fuego"),
    293: ("Puerto Natales", "Última Esperanza"),
    294: ("Torres del Paine", "Última Esperanza"),
    295: ("Santiago", "Santiago"),
    296: ("Cerrillos", "Santiago"),
    297: ("Cerro Navia", "Santiago"),
    298: ("Conchalí", "Santiago"),
    299: ("El Bosque", "Santiago"),
    300: ("Estación Central", "Santiago"),
    301: ("Huechuraba", "Santiago"),
    302: ("Independencia", "Santiago"),
    303: ("La Cisterna", "Santiago"),
    304: ("La Florida", "Santiago"),
    305: ("La Granja", "Santiago"),
    306: ("La Pintana", "Santiago"),
    307: ("La Reina", "Santiago"),
    308: ("Las Condes", "Santiago"),
    309: ("Lo Barnechea", "Santiago"),
    310: ("Lo Espejo", "Santiago"),
    311: ("Lo Prado", "Santiago"),
    312: ("Macul", "Santiago"),
    313: ("Maipú", "Santiago"),
    314: ("Ñuñoa", "Santiago"),
    315: ("Pedro Aguirre Cerda", "Santiago"),
    316: ("Peñalolén", "Santiago"),
    317: ("Providencia", "Santiago"),
    318: ("Pudahuel", "Santiago"),
    319: ("Quilicura", "Santiago"),
    320: ("Quinta Normal", "Santiago"),
    321: ("Recoleta", "Santiago"),
    322: ("Renca", "Santiago"),
    323: ("San Joaquín", "Santiago"),
    324: ("San Miguel", "Santiago"),
    325: ("San Ramón", "Santiago"),
    326: ("Vitacura", "Santiago"),
    327: ("Puente Alto", "Cordillera"),
    328: ("Pirque", "Cordillera"),
    329: ("San José de Maipo", "Cordillera"),
    330: ("Colina", "Chacabuco"),
    331: ("Lampa", "Chacabuco"),
    332: ("Tiltil", "Chacabuco"),
    333: ("San Bernardo", "Maipo"),
    334: ("Buin", "Maipo"),
    335: ("Calera de Tango", "Maipo"),
    336: ("Paine", "Maipo"),
    337: ("Melipilla", "Melipilla"),
    338: ("Alhué", "Melipilla"),
    339: ("Curacaví", "Melipilla"),
    340: ("María Pinto", "Melipilla"),
    341: ("San Pedro", "Melipilla"),
    342: ("Talagante", "Talagante"),
    343: ("El Monte", "Talagante"),
    344: ("Isla de Maipo", "Talagante"),
    345: ("Padre Hurtado", "Talagante"),
    346: ("Peñaflor", "Talagante"),
}

_MUNICIPALIDAD_RE = re.compile(r"municipalidad\s+de\s+(.+)", re.IGNORECASE)


def _clean(text: str) -> str:
    """Baja a minúsculas y quita tildes — Mercado Público suele mandar los
    nombres de organismo sin acentuar (ej. "SANTA BARBARA")."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().casefold()


_COMUNA_NAMES_BY_NORMALIZED: dict[str, str] = {
    _clean(name): name for name, _prov in CHILE_COMUNAS.values()
}
# De más largo a más corto, para no sobrecapturar cuando el nombre del
# organismo sigue con más texto después de la comuna (ej. "...DE CABRERO
# DEPARTAMENTO DE SALUD" no debe perder contra un match parcial más corto).
_COMUNA_NAMES_SORTED: list[tuple[str, str]] = sorted(
    _COMUNA_NAMES_BY_NORMALIZED.items(), key=lambda kv: -len(kv[0])
)


def resolve_comuna_from_organismo_name(raw_organismo_name: str | None) -> str | None:
    """Heurística barata: "(I.) Municipalidad de <comuna>" -> nombre canónico de comuna.

    Sin llamadas HTTP: opera sobre `institucion.organismo_comprador`, que ya
    viene en el listado de Compra Ágil. `None` si no es una municipalidad
    reconocible o la comuna no está en el dataset.
    """
    if not raw_organismo_name:
        return None
    match = _MUNICIPALIDAD_RE.search(raw_organismo_name)
    if not match:
        return None
    resto = _clean(match.group(1))
    for normalized, canonical in _COMUNA_NAMES_SORTED:
        if resto == normalized or resto.startswith(normalized + " "):
            return canonical
    return None


# Un match se descarta si viene precedido de la palabra "región" (sola, no
# "regional" — la Delegación Presidencial *Regional* sí puede resolver a la
# comuna de su sede). Sin este resguardo, "CENTRO DE FORMACION TECNICA DE LA
# REGION METROPOLITANA DE SANTIAGO" resolvía a "Santiago" porque el nombre
# completo de la región termina justo así — no porque el organismo esté en esa
# comuna. La ventana de 25 caracteres alcanza para "región metropolitana de ".
_REGION_CONTEXT_RE = re.compile(r"\bregion\b[\w\s']{0,25}$")


def resolve_comuna_from_organismo_name_generic(
    raw_organismo_name: str | None,
) -> str | None:
    """Respaldo de `resolve_comuna_from_organismo_name`: busca el nombre de
    cualquier comuna en cualquier parte del texto, no solo tras "Municipalidad
    de". Cubre patrones reales de `buyer_institution` que la heurística
    específica no ve: "Hospital de X", "Corporación (Municipal) de X",
    "Departamento Provincial de X", "Dirección Regional ... - X",
    "Universidad de X", etc. (ver PENDIENTES.md 6.19).

    Menos confiable que el camino específico — por eso es un respaldo, no el
    primer intento — con un resguardo adicional al de `_REGION_CONTEXT_RE`:
    **gana el match más a la derecha, no el más largo**. Con "más largo gana",
    "SERVICIO DE SALUD DEL LIBERTADOR B O'HIGGINS HOSPITAL REG RANCAGUA"
    resolvía a "O'Higgins" (una comuna real, pero de Aysén, sin relación) en
    vez de "Rancagua" — la comuna correcta, que aparece al final. El patrón
    habitual en estos nombres pone el lugar específico al final, no en medio
    del nombre de una región.

    `None` si ningún nombre de comuna aparece como palabra completa fuera de
    ese contexto.
    """
    if not raw_organismo_name:
        return None
    limpio = _clean(raw_organismo_name)
    candidatos: list[tuple[int, int, str]] = []
    for normalized, canonical in _COMUNA_NAMES_SORTED:
        for m in re.finditer(r"(?<!\w)" + re.escape(normalized) + r"(?!\w)", limpio):
            if _REGION_CONTEXT_RE.search(limpio[: m.start()]):
                continue
            candidatos.append((m.start(), len(normalized), canonical))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: (c[0], c[1]))
    return candidatos[-1][2]


def resolve_comuna(
    raw_organismo_name: str | None, *, use_generic_fallback: bool = True
) -> tuple[str | None, str | None]:
    """Comuna canónica y la heurística que la resolvió, en cascada:

    1. `resolve_comuna_from_organismo_name` (nombre de municipalidad) — alta
       confianza, se intenta primero, siempre.
    2. `resolve_comuna_from_organismo_name_generic` (comuna en cualquier parte
       del texto) — respaldo, mayor cobertura, algo más de riesgo. Se salta
       por completo si `use_generic_fallback=False` (ver
       `settings.enable_comuna_generic_heuristic`, apagado por defecto hasta
       decidir si el riesgo de falso positivo vale la pena).

    Devuelve `(None, None)` si ninguna resuelve (o si la única que resolvía
    era la genérica y está desactivada). El segundo valor
    (`"organismo_name"` / `"organismo_name_generic"`) es lo que se guarda en
    `buyer_institution.comuna_resolution_source`, para poder auditar o revisar
    por separado los casos que vinieron del camino menos confiable.
    """
    comuna = resolve_comuna_from_organismo_name(raw_organismo_name)
    if comuna:
        return comuna, "organismo_name"
    if not use_generic_fallback:
        return None, None
    comuna = resolve_comuna_from_organismo_name_generic(raw_organismo_name)
    if comuna:
        return comuna, "organismo_name_generic"
    return None, None
