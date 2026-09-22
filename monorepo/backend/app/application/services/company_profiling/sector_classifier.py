"""Rubro del producto intuido desde la glosa de una actividad puntual.

Portado de `spikes/spike-1/poc/perfilamiento/clasificador_rubro.py`. Es el respaldo
para los códigos que no están en `activity_dictionary` (cubre 454 de los 674 del
catálogo, un 67%).

Mira la glosa de la actividad y no la sección del catálogo: la sección "comercio"
junta 105 códigos sin relación entre sí, y ponerlos a todos en el mismo rubro
pierde lo que la glosa sí dice. Las reglas que calzan se acumulan; el comodín de
comercio/fabricación solo aplica si ninguna otra calzó. Una glosa sin coincidencias
no fuerza un rubro.

Los rubros son los provisionales de `app/shared/sectors.py`.
"""

import re
import unicodedata

# (palabras clave, excepciones, rubros). Se compara contra la glosa en mayúsculas
# y sin tildes. Una excepción presente anula la regla aunque haya palabra clave.
_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (("REPARACION", "MANTENCION", "MANTENIMIENTO"), (), ("Mantención y Reparación",)),
    (
        ("CONSTRUCCION", "EDIFICACION", "OBRA GRUESA", "TERMINACION Y ACABADO", "ALBANIL"),
        (),
        ("Obras de Construcción e Infraestructura",),
    ),
    (("ARQUITECTURA", "INGENIERIA"), (), ("Arquitectura e Ingeniería",)),
    (
        (
            "PROGRAMACION INFORMATICA",
            "SOFTWARE",
            "DESARROLLO DE APLICACIONES",
            "SISTEMAS INFORMATICOS",
        ),
        (),
        ("Desarrollo de Software",),
    ),
    (
        (
            "TELECOMUNICACION",
            "TELEFONIA",
            "RADIODIFUSION",
            "TRANSMISION DE TELEVISION",
            "PROVEEDORES DE ACCESO A INTERNET",
        ),
        (),
        ("Tecnología y Telecomunicaciones",),
    ),
    (("CONSULTORIA", "ASESORIA", "ASESORAMIENTO"), (), ("Consultoría y Asesoría Técnica",)),
    (
        ("SALUD", "MEDIC", "ENFERMERIA", "HOSPITAL", "CLINICA", "ODONTOLOG", "FARMAC", "VETERINARI"),
        (),
        ("Salud y Equipamiento Médico",),
    ),
    (
        ("ENSENANZA", "EDUCACION", "CAPACITACION", "FORMACION TECNICA", "ACADEMIA"),
        (),
        ("Educación y Capacitación",),
    ),
    (
        ("TRANSPORTE", "CARGA", "FLETE", "LOGISTIC", "ALMACENAMIENTO"),
        (),
        ("Transporte y Logística",),
    ),
    (
        (
            "ALIMENT", "COMIDA", "RESTAURANT", "GASTRONOM", "PESCA", "CULTIVO",
            "GANADERIA", "AVICOLA", "CARNE", "LACTEO", "LECHE", "PAN ", "PANADERIA",
            "BEBIDAS", "PISCO", "VINO", "CERVEZ", "FRUTAS", "VERDURAS",
        ),  # fmt: skip
        # 476301 vende artículos de caza y pesca, no pescado.
        ("CAZA Y PESCA",),
        ("Alimentación y Gastronomía",),
    ),
    (
        ("LIMPIEZA", "ASEO", "SANITIZACION", "DESINFECCION"),
        (),
        ("Limpieza y Aseo Industrial",),
    ),
    (("SEGURIDAD", "VIGILANCIA", "GUARDIA"), (), ("Seguridad y Vigilancia",)),
    (
        ("RESIDUOS", "DESECHOS", "RECICLAJE", "AMBIENTAL", "DESCONTAMINACION", "AGUAS RESIDUALES"),
        (),
        ("Medio Ambiente y Sustentabilidad",),
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
        ("Energía y Electricidad",),
    ),
    (
        ("IMPRENTA", "IMPRESION", "EDICION", "DISENO GRAFICO", "FOTOCOPIADO", "PUBLICIDAD", "FOTOGRAFIA"),
        (),
        ("Servicios de Imprenta y Diseño",),
    ),
    (("JARDIN", "PAISAJISMO"), (), ("Jardinería y Paisajismo",)),
    (
        ("RECURSOS HUMANOS", "RECLUTAMIENTO", "SUMINISTRO DE PERSONAL", "AGENCIAS DE EMPLEO"),
        (),
        ("Recursos Humanos",),
    ),
    (("CONTABILIDAD", "AUDITORIA", "TENEDURIA DE LIBROS"), (), ("Contabilidad y Auditoría",)),
)

_CATCHALL_WORDS = ("VENTA", "COMERCIO", "FABRICACION", "ELABORACION", "PRODUCCION", "DISTRIBUCION")
_CATCHALL_SECTORS = ("Equipos e Insumos Industriales",)


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
