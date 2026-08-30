"""Diccionario de actividad económica → rubro del producto y términos de compra.

Los tres ejes
-------------
La idea natural es `código → [palabras clave]` y quedarse con la **intersección**
de las actividades de la empresa. Con un solo eje eso casi siempre da vacío, y el
ejemplo real lo muestra:

    433000  terminación y acabado de edificios     → pintura, revestimiento, obras
    479100  venta al por menor por internet        → venta, distribución, despacho
    952200  reparación de aparatos domésticos      → reparación, mantención

Intersección: **∅**. No es culpa del diccionario. La CIIU está organizada por
**qué se hace** (fabricar, vender, reparar, construir), no por **sobre qué se
hace**. Esas tres actividades no comparten operación; comparten objeto — el
hogar.

Separando los ejes, cada operación de conjuntos sirve para algo distinto:

| Eje | Operación | Para qué |
|---|---|---|
| `sectores` | unión | `Supplier.sectors`, con el vocabulario cerrado del front |
| `terminos` | unión | `Supplier.keywords`: todo lo que la empresa sabe hacer |
| `objeto` | **intersección** | la concordancia: sobre qué trabaja, aunque haga cosas distintas |

Intersección vacía **no es un error**: es el hallazgo de que la empresa es
multirubro y no hay hilo común que declarar. Se reporta y decide el usuario.

El vocabulario de `sectores` no es libre
----------------------------------------
Son los 19 rubros de `frontend/.../data/sectors.ts`, leídos del archivo original
(ver `vocabulario.py`). Nada en el sistema impide guardar un sector inventado —
`Supplier.sectors` es `list[str]` sin validar— así que un rubro mal escrito no
falla: simplemente aparece sin marcar en el wizard. La prueba
`test_todo_sector_del_diccionario_existe_en_el_front` es lo que sostiene esa
invariante.

**`sectores` vacío significa fuera de alcance**: una actividad que no le
corresponde a ningún rubro del producto porque no aparece en compras públicas
(hogares como empleadores, organizaciones religiosas). Se registra igual, para
distinguir "no está en el diccionario" de "está y no aplica".

Procedencia de los datos
------------------------
**Las entradas de acá son provisionales y escritas a mano.** Los códigos
433000, 479100 y 952200 vienen de un payload real; el resto se escribió de
memoria y hay que verificarlo contra el catálogo oficial del SII antes de
apoyarse en ellos. La estructura es la que se está probando, no la tabla.

Cuando llegue el catálogo oficial, `cargar_catalogo.py` genera las entradas a
partir de él y `sin_entrada` reporta lo que falte. No hace falta cubrir las ~1000
subclases: basta con los códigos que aparecen entre los usuarios reales.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import catalogo
from .clasificador_rubro import rubro_por_glosa


@dataclass(frozen=True)
class Entrada:
    """Los tres ejes de una actividad económica."""

    # Rubros del producto. DEBEN existir en `vocabulario.sectores()`.
    # Vacío = la actividad no tiene lugar en compras públicas.
    sectores: tuple[str, ...] = ()
    # Sobre qué trabaja: el eje donde la intersección tiene sentido.
    objeto: tuple[str, ...] = ()
    # Cómo lo pediría un comprador público: el puente entre el lenguaje
    # tributario de la glosa y el lenguaje de compra de las bases.
    terminos: tuple[str, ...] = ()


# Semilla provisional. Ver "Procedencia de los datos" arriba.
CATALOGO: dict[int, Entrada] = {
    # --- Verificados contra un payload real de la API ---
    433000: Entrada(  # Terminación y acabado de edificios
        sectores=("Obras de Construcción e Infraestructura",),
        objeto=("edificios", "inmuebles", "hogar", "oficinas"),
        terminos=(
            "pintura",
            "revestimiento",
            "habilitación de oficinas",
            "terminaciones",
            "obras menores",
        ),
    ),
    479100: Entrada(  # Venta al por menor por correo, internet y teléfono
        sectores=("Equipos e Insumos Industriales",),
        objeto=("hogar", "bienes de consumo"),
        terminos=("venta en línea", "distribución", "despacho a domicilio", "suministro"),
    ),
    952200: Entrada(  # Reparación de aparatos de uso doméstico y de jardinería
        sectores=("Mantención y Reparación",),
        objeto=("hogar", "electrodomésticos", "jardinería"),
        terminos=(
            "reparación de electrodomésticos",
            "mantención de equipos",
            "servicio técnico",
        ),
    ),
    # --- Provisionales: códigos escritos de memoria, por verificar ---
    620100: Entrada(  # Programación informática
        sectores=("Desarrollo de Software",),
        objeto=("software", "sistemas", "plataformas"),
        terminos=(
            "desarrollo de software",
            "plataforma web",
            "mantención de sistemas",
            "aplicación móvil",
        ),
    ),
    620200: Entrada(  # Consultoría informática
        sectores=("Tecnología y Telecomunicaciones", "Consultoría y Asesoría Técnica"),
        objeto=("software", "sistemas", "infraestructura tecnológica"),
        terminos=("consultoría informática", "soporte TI", "mesa de ayuda"),
    ),
    702000: Entrada(  # Consultoría de gestión
        sectores=("Consultoría y Asesoría Técnica",),
        objeto=("gestión", "empresas", "procesos"),
        terminos=("consultoría de gestión", "asesoría organizacional", "estudios"),
    ),
    812100: Entrada(  # Limpieza general de edificios
        sectores=("Limpieza y Aseo Industrial",),
        objeto=("edificios", "oficinas", "inmuebles"),
        terminos=("servicio de aseo", "limpieza de dependencias", "sanitización"),
    ),
    492300: Entrada(  # Transporte de carga por carretera
        sectores=("Transporte y Logística",),
        objeto=("carga", "mercancías"),
        terminos=("transporte de carga", "flete", "distribución logística"),
    ),
    # --- Fuera de alcance: existe, pero no aparece en compras públicas ---
    970000: Entrada(  # Actividades de hogares como empleadores
        sectores=(),
        objeto=(),
        terminos=(),
    ),
}


def entrada(codigo: int | str) -> Entrada | None:
    """Busca el código en el diccionario. `None` si todavía no está."""
    try:
        return CATALOGO.get(int(str(codigo).strip()))
    except (TypeError, ValueError):
        return None


def esta_fuera_de_alcance(codigo: int | str) -> bool:
    """¿Está en el diccionario y marcada como sin lugar en compras públicas?"""
    registro = entrada(codigo)
    return registro is not None and not registro.sectores


def sin_entrada(codigos: list[int]) -> list[int]:
    """Códigos que aún no tienen entrada. Es la lista de trabajo del diccionario."""
    return [codigo for codigo in codigos if entrada(codigo) is None]


def _unir(codigos: list[int], eje: str) -> list[str]:
    """Unión conservando el orden de aparición y sin repetir."""
    unidos: list[str] = []
    for codigo in codigos:
        registro = entrada(codigo)
        if registro is None:
            continue
        for termino in getattr(registro, eje):
            if termino not in unidos:
                unidos.append(termino)
    return unidos


def sectores_de(codigos: list[int]) -> list[str]:
    """**Unión** de los rubros: todos aquellos en los que la empresa puede competir.

    Dos niveles de cobertura, en orden:

    1. **Por código** (`CATALOGO`): curado a mano, el resultado más confiable.
    2. **Por la glosa de la actividad puntual** (`clasificador_rubro.py`):
       respaldo para cualquier código del catálogo del SII que todavía no se
       curó a mano. Busca palabras clave en el texto de esa actividad
       específica, no en el título de su sección — la sección agrupa
       demasiado grueso (p. ej. "COMERCIO AL POR MAYOR Y AL POR MENOR..."
       junta 105 códigos reales, desde maquinaria hasta motocicletas, y
       ponerlos todos en el mismo rubro pierde la información que la glosa
       puntual sí tiene).

    Este nivel 2 es deliberadamente **más preciso pero de menor cobertura**
    que agrupar por sección: una glosa sin ninguna palabra reconocida no
    fuerza un rubro, queda sin uno (ver `sin_rubro_determinado` en
    `Concordancia`). Es un punto de partida para iterar, no el mapeo final.

    Un código que no existe en ningún lado (ni en `CATALOGO` ni en el catálogo
    real del SII) no aporta nada acá; queda en `sin_catalogo_sii`.
    """
    directos = _unir(codigos, "sectores")

    respaldo: list[str] = []
    for codigo in codigos:
        if entrada(codigo) is not None:
            continue  # ya cubierto por el nivel 1, incluidas las genéricas vacías
        glosa = catalogo.glosa_oficial(codigo)
        if not glosa:
            continue
        for sector in rubro_por_glosa(glosa):
            if sector not in directos and sector not in respaldo:
                respaldo.append(sector)

    return directos + respaldo


def terminos_de(codigos: list[int]) -> list[str]:
    """**Unión** de los términos de compra: todo lo que la empresa sabe hacer.

    Unión y no intersección, a propósito. Lo que engancha con una licitación es
    la capacidad específica —"pintura", "reparación de electrodomésticos"—, no
    lo que esa capacidad tenga en común con las otras. Intersectar acá borraría
    justamente el término que iba a producir la coincidencia.

    **Solo por código curado** (`CATALOGO`): términos en lenguaje de compra,
    escritos a mano. A propósito **no hay respaldo con la glosa oficial** del
    SII: es lenguaje tributario, no de compra (ver "El problema real: dos
    vocabularios distintos" en `1.1-onboarding.md`), y se prefirió no aportar
    nada antes que aportar una palabra que describe mal. Un código sin
    curación fina simplemente no aporta a `keywords` — ver `sin_palabra_clave`
    para poder avisarlo en vez de que pase inadvertido.
    """
    return _unir(codigos, "terminos")


def sin_palabra_clave(codigos: list[int]) -> list[int]:
    """Códigos que no aportaron ningún término a `terminos_de`.

    Dos causas posibles, y a esta función le da lo mismo cuál fue: no está
    curado en `CATALOGO`, o está curado pero marcado fuera de alcance (con
    `terminos=()`, como `970000`). Ese segundo caso ya tiene su propio aviso
    (`fuera_de_alcance`) con su propia explicación, así que se excluye acá
    para no duplicar el mensaje sobre el mismo código.
    """
    return [
        codigo
        for codigo in codigos
        if not _unir([codigo], "terminos") and not esta_fuera_de_alcance(codigo)
    ]


def dominio_comun(codigos: list[int]) -> list[str]:
    """**Intersección** del eje objeto: sobre qué trabaja la empresa.

    Es la concordancia entre actividades dispares. En el ejemplo real
    —terminación de edificios, venta por internet y reparación de
    electrodomésticos— da `["hogar"]`, que es el hilo que une a las tres y que
    ninguna sección CIIU expresa.

    Devuelve lista vacía cuando no hay hilo común. Eso **no es un error**: es el
    hallazgo de que la empresa es multirubro.

    Los códigos sin entrada, y los fuera de alcance, se **ignoran** en vez de
    vaciar la intersección: ni un diccionario incompleto ni una actividad
    irrelevante deben borrar una concordancia que sí existe entre las demás.
    """
    conjuntos = [
        set(registro.objeto)
        for codigo in codigos
        if (registro := entrada(codigo)) is not None and registro.objeto
    ]
    if not conjuntos:
        return []

    comunes = set.intersection(*conjuntos)
    # Orden estable: dos corridas con los mismos datos deben dar la misma lista.
    for codigo in codigos:
        registro = entrada(codigo)
        if registro is not None and registro.objeto:
            orden = registro.objeto
            break
    else:
        orden = ()
    ordenados = [termino for termino in orden if termino in comunes]
    ordenados += sorted(comunes - set(ordenados))
    return ordenados


@dataclass
class Concordancia:
    """Lo que el diccionario puede decir de un conjunto de actividades."""

    sectores: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    dominio: list[str] = field(default_factory=list)
    sin_diccionario: list[int] = field(default_factory=list)
    fuera_de_alcance: list[int] = field(default_factory=list)
    # Códigos que no existen en el catálogo real del SII. Genuinamente
    # desconocidos: no hay glosa, no hay rubro posible desde acá.
    sin_catalogo_sii: list[int] = field(default_factory=list)
    # Códigos que sí existen en el catálogo (tienen glosa), pero cuyo texto no
    # calzó con ninguna palabra clave del clasificador. No es un error: una
    # glosa sin rubro forzado es mejor que un rubro inventado, y es la lista de
    # trabajo para agregar reglas al clasificador más adelante.
    sin_rubro_determinado: list[int] = field(default_factory=list)
    # Códigos que no aportaron ningún término a `keywords` — no curados y sin
    # respaldo de glosa (se quitó a propósito, ver `terminos_de`).
    sin_palabra_clave: list[int] = field(default_factory=list)

    @property
    def hay_hilo_comun(self) -> bool:
        return bool(self.dominio)


def analizar(codigos: list[int]) -> Concordancia:
    """Aplica los tres ejes de una vez."""
    sin_catalogo = [c for c in codigos if entrada(c) is None and not catalogo.glosa_oficial(c)]
    sin_rubro = [
        c
        for c in codigos
        if entrada(c) is None
        and catalogo.glosa_oficial(c)
        and not rubro_por_glosa(catalogo.glosa_oficial(c))
    ]
    return Concordancia(
        sectores=sectores_de(codigos),
        keywords=terminos_de(codigos),
        dominio=dominio_comun(codigos),
        sin_diccionario=sin_entrada(codigos),
        fuera_de_alcance=[c for c in codigos if esta_fuera_de_alcance(c)],
        sin_catalogo_sii=sin_catalogo,
        sin_rubro_determinado=sin_rubro,
        sin_palabra_clave=sin_palabra_clave(codigos),
    )
