"""Diccionario curado: código de actividad económica → rubros y palabras clave.

Portado de `spikes/spike-1/poc/perfilamiento/diccionario.py` (rama
`155-spike-1-onboarding-y-validacion-documental`, commit `2ed42d7`).

El problema que resuelve
------------------------
La glosa del SII está en lenguaje tributario ("programación informática") y las
licitaciones en lenguaje de compra ("desarrollo de plataforma web"). Como el
matching de palabras clave es literal, sugerir la glosa no engancha con nada. Por
eso las palabras clave se escriben a mano, código por código, y **solo** salen de
acá: un código sin curar no aporta palabras clave (el spike quitó a propósito el
respaldo con la glosa oficial).

Rubros y palabras clave se **unen** entre actividades: lo que engancha con una
licitación es la capacidad puntual ("pintura", "servicio técnico"), no lo que las
actividades tengan en común.

Del diccionario original se omite el eje `objeto` (dominio común), que el producto
todavía no usa.

Procedencia y estado
--------------------
* 433000, 479100 y 952200: verificados contra un payload real.
* El resto: escritos leyendo la glosa oficial, sin verificar con empresas reales.
* **Los rubros son provisionales**: son los del wizard (`app/shared/sectors.py`),
  no las categorías de Mercado Público. Hay que revisarlos contra ellas y volver a
  curar esta tabla.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivityEntry:
    # Rubros del producto; deben existir en `PRODUCT_SECTORS`. Vacío significa que
    # la actividad no tiene lugar en compras públicas.
    sectors: tuple[str, ...] = ()
    # Cómo lo pediría un comprador público.
    keywords: tuple[str, ...] = ()


ACTIVITY_DICTIONARY: dict[int, ActivityEntry] = {
    # --- Verificados contra un payload real ---
    433000: ActivityEntry(  # Terminación y acabado de edificios
        sectors=("Obras de Construcción e Infraestructura",),
        keywords=(
            "pintura",
            "revestimiento",
            "habilitación de oficinas",
            "terminaciones",
            "obras menores",
        ),
    ),
    479100: ActivityEntry(  # Venta al por menor por correo, internet y teléfono
        sectors=("Equipos e Insumos Industriales",),
        keywords=("venta en línea", "distribución", "despacho a domicilio", "suministro"),
    ),
    952200: ActivityEntry(  # Reparación de aparatos de uso doméstico y de jardinería
        sectors=("Mantención y Reparación",),
        keywords=(
            "reparación de electrodomésticos",
            "mantención de equipos",
            "servicio técnico",
        ),
    ),
    # --- Provisionales, sin verificar contra empresas reales ---
    620100: ActivityEntry(  # Programación informática
        sectors=("Desarrollo de Software",),
        keywords=(
            "desarrollo de software",
            "plataforma web",
            "mantención de sistemas",
            "aplicación móvil",
        ),
    ),
    620200: ActivityEntry(  # Consultoría informática
        sectors=("Tecnología y Telecomunicaciones", "Consultoría y Asesoría Técnica"),
        keywords=("consultoría informática", "soporte TI", "mesa de ayuda"),
    ),
    702000: ActivityEntry(  # Consultoría de gestión
        sectors=("Consultoría y Asesoría Técnica",),
        keywords=("consultoría de gestión", "asesoría organizacional", "estudios"),
    ),
    812100: ActivityEntry(  # Limpieza general de edificios
        sectors=("Limpieza y Aseo Industrial",),
        keywords=("servicio de aseo", "limpieza de dependencias", "sanitización"),
    ),
    492300: ActivityEntry(  # Transporte de carga por carretera
        sectors=("Transporte y Logística",),
        keywords=("transporte de carga", "flete", "distribución logística"),
    ),
    801001: ActivityEntry(  # Servicios de seguridad privada prestados por empresas
        sectors=("Seguridad y Vigilancia",),
        keywords=(
            "guardias de seguridad",
            "vigilancia privada",
            "rondas de seguridad",
            "control de acceso",
        ),
    ),
    813000: ActivityEntry(  # Paisajismo, servicios de jardinería y conexos
        sectors=("Jardinería y Paisajismo",),
        keywords=("mantención de áreas verdes", "paisajismo", "poda", "jardinería"),
    ),
    561000: ActivityEntry(  # Restaurantes y servicio móvil de comidas
        sectors=("Alimentación y Gastronomía",),
        keywords=("servicio de alimentación", "catering", "banquetería", "comida preparada"),
    ),
    692000: ActivityEntry(  # Contabilidad, teneduría de libros y auditoría
        sectors=("Contabilidad y Auditoría",),
        keywords=(
            "servicios contables",
            "auditoría",
            "asesoría tributaria",
            "teneduría de libros",
        ),
    ),
    781000: ActivityEntry(  # Agencias de empleo
        sectors=("Recursos Humanos",),
        keywords=(
            "reclutamiento",
            "selección de personal",
            "búsqueda de talento",
            "agencia de empleo",
        ),
    ),
    464907: ActivityEntry(  # Venta al por mayor de productos farmacéuticos
        sectors=("Salud y Equipamiento Médico",),
        keywords=(
            "suministro de medicamentos",
            "insumos farmacéuticos",
            "distribución médica",
        ),
    ),
    181200: ActivityEntry(  # Servicios relacionados con la impresión
        sectors=("Servicios de Imprenta y Diseño",),
        keywords=(
            "servicios de impresión",
            "imprenta",
            "diseño gráfico",
            "material publicitario",
        ),
    ),
    351030: ActivityEntry(  # Distribución de energía eléctrica
        sectors=("Energía y Electricidad",),
        keywords=(
            "suministro eléctrico",
            "distribución de energía",
            "instalaciones eléctricas",
        ),
    ),
    390000: ActivityEntry(  # Descontaminación y gestión de desechos
        sectors=("Medio Ambiente y Sustentabilidad",),
        keywords=(
            "gestión de residuos",
            "descontaminación",
            "manejo ambiental",
            "disposición de desechos",
        ),
    ),
    855000: ActivityEntry(  # Apoyo a la enseñanza
        sectors=("Educación y Capacitación",),
        keywords=(
            "capacitación",
            "cursos de formación",
            "apoyo educativo",
            "material didáctico",
        ),
    ),
    # --- Fuera de alcance: existe, pero no aparece en compras públicas ---
    970000: ActivityEntry(),  # Hogares como empleadores de personal doméstico
}


def entry_for(code: int) -> ActivityEntry | None:
    return ACTIVITY_DICTIONARY.get(code)


def is_out_of_scope(code: int) -> bool:
    entry = entry_for(code)
    return entry is not None and not entry.sectors


def _union(codes: list[int], field: str) -> list[str]:
    """Unión conservando el orden de aparición y sin repetir."""
    result: list[str] = []
    for code in codes:
        entry = entry_for(code)
        if entry is None:
            continue
        for value in getattr(entry, field):
            if value not in result:
                result.append(value)
    return result


def curated_sectors(codes: list[int]) -> list[str]:
    return _union(codes, "sectors")


def keywords_for(codes: list[int]) -> list[str]:
    return _union(codes, "keywords")


def codes_without_keywords(codes: list[int]) -> list[int]:
    """Códigos que no aportan palabras clave, sin contar los fuera de alcance."""
    return [
        code for code in codes if not keywords_for([code]) and not is_out_of_scope(code)
    ]
