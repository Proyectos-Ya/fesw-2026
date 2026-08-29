"""Rubro del producto, intuido desde la glosa de **la actividad específica**.

Por qué no basta con la sección
--------------------------------
La sección del SII es demasiado gruesa para decidir un rubro. La sección
"COMERCIO AL POR MAYOR Y AL POR MENOR..." tiene 105 códigos reales —desde
venta de maquinaria hasta reparación de motocicletas— y ponerlos todos en el
mismo rubro del front pierde justo la información que la glosa de cada
actividad sí tiene. Este módulo mira **el texto de la actividad puntual**, no
el título de su sección, y busca en él las palabras que delatan de qué se
trata.

Cómo está armado
-----------------
Reglas ordenadas, de más específica a más genérica. Se recorren en orden y
**todas las que calcen se acumulan** (una glosa puede tocar más de un dominio:
"reparación y mantención de equipos de computación" toca reparación y
tecnología a la vez). La única excepción es el catch-all de comercio/fabricación
genérico: solo se aplica si **ninguna** regla específica calzó, para que no
tape una coincidencia más precisa que ya se encontró.

Es un punto de partida deliberadamente simple — coincidencia de texto, sin
NLP — para poder iterar. Una glosa que no calza con ninguna regla no se fuerza
a un rubro: queda sin sector desde este mecanismo, que es preferible a
inventar uno solo por rellenar.
"""

from __future__ import annotations

import re
import unicodedata

# (palabras clave, excepciones, rubro(es) del front). Se compara contra la
# glosa en mayúsculas y sin tildes, así que las palabras clave también van así.
# `excepciones`: si alguna aparece en la glosa, la regla NO calza aunque haya
# una palabra clave presente — existe porque una sola palabra puede significar
# dos cosas distintas ("pesca" como actividad productiva vs. como artículo de
# caza y pesca en venta al detalle).
_REGLAS: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("REPARACION", "MANTENCION", "MANTENIMIENTO"),
        (),
        ("Mantención y Reparación",),
    ),
    (
        ("CONSTRUCCION", "EDIFICACION", "OBRA GRUESA", "TERMINACION Y ACABADO", "ALBAÑIL"),
        (),
        ("Obras de Construcción e Infraestructura",),
    ),
    (
        ("ARQUITECTURA", "INGENIERIA"),
        (),
        ("Arquitectura e Ingeniería",),
    ),
    (
        ("PROGRAMACION INFORMATICA", "SOFTWARE", "DESARROLLO DE APLICACIONES", "SISTEMAS INFORMATICOS"),
        (),
        ("Desarrollo de Software",),
    ),
    (
        ("TELECOMUNICACION", "TELEFONIA", "RADIODIFUSION", "TRANSMISION DE TELEVISION", "PROVEEDORES DE ACCESO A INTERNET"),
        (),
        ("Tecnología y Telecomunicaciones",),
    ),
    (
        ("CONSULTORIA", "ASESORIA", "ASESORAMIENTO"),
        (),
        ("Consultoría y Asesoría Técnica",),
    ),
    (
        ("SALUD", "MEDIC", "ENFERMERIA", "HOSPITAL", "CLINICA", "ODONTOLOG", "FARMAC", "VETERINARI"),
        (),
        ("Salud y Equipamiento Médico",),
    ),
    (
        ("ENSEÑANZA", "EDUCACION", "CAPACITACION", "FORMACION TECNICA", "ACADEMIA"),
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
        ),
        # `476301 VENTA AL POR MENOR DE ARTÍCULOS DE CAZA Y PESCA...`: vende
        # equipo de pesca, no pescado. Detectado comparando contra el catálogo
        # real — es el único código de los 9 con "PESCA" que no es producción
        # de alimentos.
        ("CAZA Y PESCA",),
        ("Alimentación y Gastronomía",),
    ),
    (
        ("LIMPIEZA", "ASEO", "SANITIZACION", "DESINFECCION"),
        (),
        ("Limpieza y Aseo Industrial",),
    ),
    (
        ("SEGURIDAD", "VIGILANCIA", "GUARDIA"),
        (),
        ("Seguridad y Vigilancia",),
    ),
    (
        ("RESIDUOS", "DESECHOS", "RECICLAJE", "AMBIENTAL", "DESCONTAMINACION", "AGUAS RESIDUALES"),
        (),
        ("Medio Ambiente y Sustentabilidad",),
    ),
    (
        # Frases completas, no la raíz "ELECTRIC" sola: esa raíz aparece en
        # "aparatos eléctricos" (venta al detalle) y "equipo eléctrico"
        # (fabricación), que no son del rubro energía. Se detectó comparando
        # contra el catálogo real: `475909 VENTA AL POR MENOR DE APARATOS
        # ELÉCTRICOS...` calzaba mal con la raíz suelta.
        (
            "ENERGIA ELECTRICA", "GENERACION DE ENERGIA", "TRANSMISION DE ENERGIA",
            "DISTRIBUCION DE ENERGIA", "INSTALACIONES ELECTRICAS", "GAS NATURAL",
            "SUMINISTRO DE ELECTRICIDAD",
        ),
        (),
        ("Energía y Electricidad",),
    ),
    (
        ("IMPRENTA", "IMPRESION", "EDICION", "DISEÑO GRAFICO", "FOTOCOPIADO", "PUBLICIDAD", "FOTOGRAFIA"),
        (),
        ("Servicios de Imprenta y Diseño",),
    ),
    (
        ("JARDIN", "PAISAJISMO"),
        (),
        ("Jardinería y Paisajismo",),
    ),
    (
        ("RECURSOS HUMANOS", "RECLUTAMIENTO", "SUMINISTRO DE PERSONAL", "AGENCIAS DE EMPLEO"),
        (),
        ("Recursos Humanos",),
    ),
    (
        ("CONTABILIDAD", "AUDITORIA", "TENEDURIA DE LIBROS"),
        (),
        ("Contabilidad y Auditoría",),
    ),
)

# Catch-all: comercio y fabricación de bienes en general. Se aplica **solo si
# ninguna regla específica de arriba calzó** — ver docstring del módulo.
_CATCHALL_PALABRAS = ("VENTA", "COMERCIO", "FABRICACION", "ELABORACION", "PRODUCCION", "DISTRIBUCION")
_CATCHALL_RUBRO = ("Equipos e Insumos Industriales",)


def _normalizar(texto: str) -> str:
    """Mayúsculas y sin tildes, para comparar sin depender de la acentuación."""
    descompuesto = unicodedata.normalize("NFD", texto.upper())
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes)


def rubro_por_glosa(glosa: str) -> tuple[str, ...]:
    """Intuye el/los rubro(s) del front a partir del texto de una actividad puntual.

    Ejemplo: `"REPARACIÓN DE APARATOS DE USO DOMÉSTICO"` → contiene
    "REPARACION" → `("Mantención y Reparación",)`. No mira la sección ni el
    grupo del catálogo, solo esta glosa — es deliberadamente más fino que
    agrupar por sección, aunque cueste algo de cobertura: una glosa sin ninguna
    palabra reconocida devuelve `()`, no un rubro forzado.
    """
    if not glosa:
        return ()

    normalizada = _normalizar(glosa)
    encontrados: list[str] = []

    for palabras, excepciones, rubros in _REGLAS:
        if any(excepcion in normalizada for excepcion in excepciones):
            continue
        if any(palabra in normalizada for palabra in palabras):
            for rubro in rubros:
                if rubro not in encontrados:
                    encontrados.append(rubro)

    if not encontrados and any(p in normalizada for p in _CATCHALL_PALABRAS):
        encontrados.extend(_CATCHALL_RUBRO)

    return tuple(encontrados)
