"""Rubro del producto intuido desde la glosa de una actividad puntual.

Portado de `spikes/spike-1/poc/perfilamiento/clasificador_rubro.py`. Es el respaldo
para los códigos que no están en `activity_dictionary` (cubre 454 de los 674 del
catálogo, un 67%).

Mira la glosa de la actividad y no la sección del catálogo: la sección "comercio"
junta 105 códigos sin relación entre sí, y ponerlos a todos en el mismo rubro
pierde lo que la glosa sí dice. Las reglas que calzan se acumulan; el comodín de
comercio/fabricación solo aplica si ninguna otra calzó. Una glosa sin coincidencias
no fuerza un rubro.

Los rubros son los de Mercado Público (`app/shared/sectors.py`), reapuntados desde
los provisionales con la tabla de correspondencia del plan 311 (§2.1).
"""

import re
import unicodedata

# (palabras clave, excepciones, rubros). Se compara contra la glosa en mayúsculas
# y sin tildes. Una excepción presente anula la regla aunque haya palabra clave.
_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("REPARACION", "MANTENCION", "MANTENIMIENTO"),
        # Esta regla apunta a un rubro de construcción, y con él la empresa recibe
        # las preguntas MOP/MINVU del banco. La reparación de vehículos, máquinas,
        # equipos informáticos o aparatos domésticos no es de ese rubro.
        (
            "VEHICULO", "AUTOMOTOR", "MOTOCICLETA", "MAQUINARIA", "MAQUINAS",
            "ELECTRODOMESTICO", "USO DOMESTICO", "COMPUTADOR", "INFORMATIC",
            "SOFTWARE", "EFECTOS PERSONALES",
        ),  # fmt: skip
        ("Servicios de construcción y mantenimiento",),
    ),
    (
        ("REPARACION DE APARATOS DE USO DOMESTICO", "REPARACION DE ELECTRODOMESTICOS"),
        (),
        ("Servicios de cuidado personal y domésticos",),
    ),
    (
        ("CONSTRUCCION", "EDIFICACION", "OBRA GRUESA", "TERMINACION Y ACABADO", "ALBANIL"),
        (),
        ("Servicios de construcción y mantenimiento",),
    ),
    (
        ("ARQUITECTURA", "INGENIERIA"),
        (),
        ("Servicios basados en ingeniería, ciencias sociales y tecnología de la información",),
    ),
    (
        (
            "PROGRAMACION INFORMATICA",
            "SOFTWARE",
            "DESARROLLO DE APLICACIONES",
            "SISTEMAS INFORMATICOS",
            "TELECOMUNICACION",
            "TELEFONIA",
            "RADIODIFUSION",
            "TRANSMISION DE TELEVISION",
            "PROVEEDORES DE ACCESO A INTERNET",
        ),
        (),
        ("Tecnologías de la información, telecomunicaciones y radiodifusión",),
    ),
    (("CONSULTORIA", "ASESORIA", "ASESORAMIENTO"), (), ("Servicios profesionales, administrativos y consultorías de gestión empresarial",)),
    (
        ("SALUD", "MEDIC", "ENFERMERIA", "HOSPITAL", "CLINICA", "ODONTOLOG", "VETERINARI"),
        (),
        ("Salud, servicios sanitarios y alimentación",),
    ),
    (("FARMAC",), (), ("Medicamentos y productos farmacéuticos",)),
    (
        ("ENSENANZA", "EDUCACION", "CAPACITACION", "FORMACION TECNICA", "ACADEMIA"),
        (),
        ("Educación, formación, entrenamiento y capacitación",),
    ),
    (
        ("TRANSPORTE", "CARGA", "FLETE", "LOGISTIC", "ALMACENAMIENTO"),
        (),
        ("Servicios de transporte, almacenaje y correo",),
    ),
    (
        ("COMIDA", "RESTAURANT", "GASTRONOM", "BANQUETE", "CASINO DE ALIMENTACION"),
        (),
        ("Servicios de Viajes, alimentación, alojamiento y entretenimiento",),
    ),
    (
        (
            "ALIMENT", "PESCA", "CULTIVO", "GANADERIA", "AVICOLA", "CARNE", "LACTEO",
            "LECHE", "PAN ", "PANADERIA", "BEBIDAS", "PISCO", "VINO", "CERVEZ",
            "FRUTAS", "VERDURAS",
        ),  # fmt: skip
        # 476301 vende artículos de caza y pesca, no pescado. Los restaurantes van
        # a la regla anterior, que es de servicios.
        ("CAZA Y PESCA", "RESTAURANT", "COMIDA"),
        ("Alimentos, bebidas y tabaco",),
    ),
    (
        ("LIMPIEZA", "ASEO", "SANITIZACION", "DESINFECCION"),
        (),
        ("Servicios de limpieza industrial",),
    ),
    (
        ("SEGURIDAD", "VIGILANCIA", "GUARDIA"),
        (),
        ("Servicios de defensa nacional, orden público y seguridad",),
    ),
    (
        ("RESIDUOS", "DESECHOS", "RECICLAJE", "AMBIENTAL", "DESCONTAMINACION", "AGUAS RESIDUALES"),
        (),
        ("Servicios medioambientales",),
    ),
    (
        # Frases completas y no la raíz "ELECTRIC": esa raíz calzaba con "venta al
        # por menor de aparatos eléctricos", que no es del rubro energía.
        (
            "ENERGIA ELECTRICA", "GENERACION DE ENERGIA", "TRANSMISION DE ENERGIA",
            "DISTRIBUCION DE ENERGIA", "INSTALACIONES ELECTRICAS", "GAS NATURAL",
            "SUMINISTRO DE ELECTRICIDAD",
        ),  # fmt: skip
        (),
        ("Maquinaria para generación y distribución de energía",),
    ),
    (
        ("IMPRENTA", "IMPRESION", "EDICION", "DISENO GRAFICO", "FOTOCOPIADO", "PUBLICIDAD", "FOTOGRAFIA"),
        (),
        ("Servicios editoriales, de diseño, publicidad, gráficos y artistas",),
    ),
    (
        ("JARDIN", "PAISAJISMO"),
        (),
        ("Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",),
    ),
    (
        ("RECURSOS HUMANOS", "RECLUTAMIENTO", "SUMINISTRO DE PERSONAL", "AGENCIAS DE EMPLEO"),
        (),
        ("Servicios profesionales, administrativos y consultorías de gestión empresarial",),
    ),
    (
        ("CONTABILIDAD", "AUDITORIA", "TENEDURIA DE LIBROS"),
        (),
        ("Servicios financieros, pensiones y seguros",),
    ),
)

_CATCHALL_WORDS = ("VENTA", "COMERCIO", "FABRICACION", "ELABORACION", "PRODUCCION", "DISTRIBUCION")
_CATCHALL_SECTORS = ("Artículos de fabricación y producción",)


def _normalize(text: str) -> str:
    """Mayúsculas y sin tildes (la Ñ queda como N)."""
    decomposed = unicodedata.normalize("NFD", text.upper())
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_marks)


def sectors_from_description(description: str) -> tuple[str, ...]:
    if not description:
        return ()

    normalized = _normalize(description)
    found: list[str] = []
    for words, exceptions, sectors in _RULES:
        if any(exception in normalized for exception in exceptions):
            continue
        if any(word in normalized for word in words):
            found.extend(s for s in sectors if s not in found)

    if not found and any(word in normalized for word in _CATCHALL_WORDS):
        found.extend(_CATCHALL_SECTORS)
    return tuple(found)


def all_sectors() -> set[str]:
    """Todos los rubros que el clasificador puede devolver."""
    return {s for _, _, sectors in _RULES for s in sectors} | set(_CATCHALL_SECTORS)
