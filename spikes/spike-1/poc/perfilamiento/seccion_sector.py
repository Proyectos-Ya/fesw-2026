"""Sección real del SII → rubro(s) del producto. NO conectada al pipeline actual.

**Estado: no se usa.** `diccionario.sectores_de` usaba esta tabla como
respaldo, agrupando por sección (21 posibles). Se reemplazó por
`clasificador_rubro.py`, que mira la glosa de cada actividad puntual en vez de
su sección: agrupar por sección resultó demasiado grueso — una sola sección de
"comercio" mete 105 códigos reales sin relación entre sí en el mismo rubro,
perdiendo justo la información que la glosa sí tiene. El clasificador da menos
cobertura automática (67% contra el 92% de esto) pero más precisión, y era lo
que se pidió: preferir la actividad puntual a la sección.

Se deja el archivo porque la tabla en sí sigue siendo correcta y podría volver
a servir — por ejemplo, como tercer nivel de respaldo para los códigos que el
clasificador no logra resolver (`Concordancia.sin_rubro_determinado` en
`diccionario.py`), si en una iteración futura se decide que un rubro
aproximado ahí es mejor que ninguno.

Por qué existía como respaldo por sección
-------------------------------------------------
`diccionario.py` mapea código por código, y eso da el mejor resultado posible
—términos de compra propios— pero curarlo a mano para las 674 actividades del
catálogo real no es razonable. Esta capa resuelve lo contrario: **cobertura
total, un rubro por sección**, para que `sectors` nunca quede vacío solo por
falta de tiempo para escribir la entrada fina de un código puntual.

La clave es el título de sección **tal como aparece en el catálogo del SII**
(`catalogo_glosas.seccion_titulo`) — 21 valores fijos, leídos del xlsx, no
calculados. La primera versión de esto calculaba la sección con una tabla de
rangos de división que escribí de memoria (estándar CIIU Rev.4); funcionaba,
pero era una capa de cálculo que podía tener errores propios — y los tuvo (la
división 04 del cobre, una extensión chilena fuera del estándar internacional,
que no se detectó hasta comparar contra el catálogo real). Con el título real
como clave, esa clase de error ya no puede pasar: es una búsqueda en un
diccionario de 21 entradas, no una cuenta con rangos.

El criterio "mandalos todo"
---------------------------
La sección **"COMERCIO AL POR MAYOR Y AL POR MENOR; REPARACIÓN DE VEHICULOS
AUTOMOTORES Y MOTOCICLETAS"** tiene 105 códigos en el catálogo real, desde
venta de maquinaria hasta reparación de motocicletas. Los 19 rubros del front
no tienen una categoría de "comercio", así que no hay un calce natural para
ninguno. Decisión: **toda la sección apunta a `Equipos e Insumos
Industriales`**, la más cercana a "provee bienes". No es un calce fino —una
ferretería y una importadora de repuestos caen en el mismo rubro— pero es
preferible a dejarlas fuera de alcance.

Secciones sin rubro
--------------------
Quedan sin mapear las que no compiten en compras públicas orientadas a
servicios y obras: actividades financieras y de seguros, inmobiliarias,
administración pública, hogares como empleadores, organizaciones
extraterritoriales. Se marcan `()` explícitamente — fuera de alcance, no
pendiente — siguiendo el mismo criterio que ya usa
`diccionario.esta_fuera_de_alcance` para códigos puntuales curados a mano.
"""

from __future__ import annotations

# Título exacto de sección (como aparece en el catálogo del SII) -> rubro(s)
# del producto. Los 21 títulos están verificados contra las 674 filas reales
# del catálogo — no hay título "sin mapear" salvo que el catálogo cambie.
TITULO_A_SECTORES: dict[str, tuple[str, ...]] = {
    "AGRICULTURA, GANADERÍA, SILVICULTURA Y PESCA": ("Alimentación y Gastronomía",),
    "EXPLOTACIÓN DE MINAS Y CANTERAS": ("Equipos e Insumos Industriales",),
    "INDUSTRIA MANUFACTURERA": ("Equipos e Insumos Industriales",),
    "SUMINISTRO DE ELECTRICIDAD, GAS, VAPOR Y AIRE ACONDICIONADO": ("Energía y Electricidad",),
    "SUMINISTRO DE AGUA; EVACUACIÓN DE AGUAS RESIDUALES, GESTIÓN DE DESECHOS Y DESCONTAMINACIÓN": (
        "Medio Ambiente y Sustentabilidad",
    ),
    "CONSTRUCCIÓN": ("Obras de Construcción e Infraestructura",),
    # "mandalos todo": ver docstring.
    "COMERCIO AL POR MAYOR Y AL POR MENOR; REPARACIÓN DE VEHICULOS AUTOMOTORES Y MOTOCICLETAS": (
        "Equipos e Insumos Industriales",
    ),
    "TRANSPORTE Y ALMACENAMIENTO": ("Transporte y Logística",),
    "ACTIVIDADES DE ALOJAMIENTO Y DE SERVICIO DE COMIDAS": ("Alimentación y Gastronomía",),
    "INFORMACIÓN Y COMUNICACIONES": ("Tecnología y Telecomunicaciones", "Desarrollo de Software"),
    "ACTIVIDADES FINANCIERAS Y DE SEGUROS": (),  # sin lugar en compras públicas
    "ACTIVIDADES INMOBILIARIAS": (),  # ídem
    "ACTIVIDADES PROFESIONALES, CIENTIFICAS Y TÉCNICAS": (
        "Consultoría y Asesoría Técnica",
        "Arquitectura e Ingeniería",
    ),
    "ACTIVIDADES DE SERVICIOS ADMINISTRATIVOS Y DE APOYO": (
        "Recursos Humanos",
        "Seguridad y Vigilancia",
        "Limpieza y Aseo Industrial",
    ),
    "ADMINISTRACIÓN PÚBLICA Y DEFENSA; PLANES DE SEGURIDAD SOCIAL DE AFILIACIÓN OBLIGATORIA": (),
    "ENSEÑANZA": ("Educación y Capacitación",),
    "ACTIVIDADES DE ATENCIÓN DE LA SALUD HUMANA Y DE ASISTENCIA SOCIAL": ("Salud y Equipamiento Médico",),
    "ACTIVIDADES ARTÍSTICAS, DE ENTRETENIMIENTO Y RECREATIVAS": ("Servicios de Imprenta y Diseño",),
    "OTRAS ACTIVIDADES DE SERVICIOS": ("Mantención y Reparación",),
    "ACTIVIDADES DE LOS HOGARES COMO EMPLEADORES; ACTIVIDADES NO DIFERENCIADAS DE LOS HOGARES": (),
    "ACTIVIDADES DE ORGANIZACIONES Y ÓRGANOS EXTRATERRITORIALES": (),
}


def sectores_por_titulo(titulo: str) -> tuple[str, ...]:
    """Rubros del producto para un título de sección real. `()` si no hay calce."""
    return TITULO_A_SECTORES.get(titulo, ())
