"""El borrador de perfil y la lógica común a cualquier fuente de datos.

Por qué esto vive separado de cada fuente
------------------------------------------
Web Empresario y ruts.info entregan la misma información —identidad, vigencia,
actividades, domicilio— en dos esquemas completamente distintos (nombres de
campo, mayúsculas vs. inglés, `null` vs. string vacío para "sin término de
giro"). Lo que hacen con esa información una vez extraída es idéntico: validar
el RUT contra el dominio, pasar las actividades por el diccionario de tres ejes,
normalizar la región al vocabulario del backend. Esa parte se escribe una sola
vez acá; cada fuente solo se encarga de su propio formato de entrada.

Esto es lo que deja "fácil de cambiar de fuente": agregar una tercera API es
escribir un adaptador que parsee su JSON a los parámetros de `construir_perfil`,
no reimplementar el diccionario ni la normalización de región.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from puente_backend import asegurar_path

from . import catalogo_glosas
from .ciiu import Actividad
from .diccionario import analizar

asegurar_path()

from app.domain.entities.supplier import is_valid_rut  # noqa: E402
from app.shared.regions import (  # noqa: E402
    canonical_region_name,
    normalize_region_name,
)


@dataclass
class PerfilSugerido:
    """Borrador de perfil derivado del RUT. Todo esto es editable por el usuario."""

    rut: str
    rut_valido: bool
    legal_name: str
    vigente: bool | None
    fuente: str = ""
    fecha_inicio: str = ""
    fecha_termino_giro: str = ""
    tipo: str = ""
    # Regiones canónicas del backend, listas para `Supplier.regions`.
    regions: list[str] = field(default_factory=list)
    comunas: list[str] = field(default_factory=list)
    # `Supplier.sectors`, con el vocabulario cerrado del front (19 rubros).
    sectors: list[str] = field(default_factory=list)
    # Sección CIIU de cada actividad. Auxiliar: sirve de respaldo y para medir
    # cobertura, pero NO es lo que se guarda — el front no conoce estos nombres.
    rubros_ciiu: list[str] = field(default_factory=list)
    # `Supplier.keywords`: términos de compra del diccionario, y las glosas no
    # genéricas como respaldo para los códigos que aún no están en él.
    keywords: list[str] = field(default_factory=list)
    # Lo que las actividades tienen en común: la intersección del eje objeto.
    # Vacío significa empresa multirubro, no falta de datos.
    dominio: list[str] = field(default_factory=list)
    # Códigos que todavía no están en el diccionario. Es la lista de trabajo.
    sin_diccionario: list[int] = field(default_factory=list)
    # Códigos que están en el diccionario y no aplican a compras públicas.
    fuera_de_alcance: list[int] = field(default_factory=list)
    actividades: list[Actividad] = field(default_factory=list)
    # Lo que quedó fuera o no se pudo interpretar. Se reporta en vez de
    # descartarse en silencio: es la mitad del hallazgo del spike.
    avisos: list[str] = field(default_factory=list)

    @property
    def aporta_al_matching(self) -> bool:
        """¿Este borrador sirve para algo más que autocompletar el nombre?

        Es la pregunta que decide si el onboarding automático "ahorra tipeo" o
        "arranca el matching". Sin `sectors` ni `keywords`, el proveedor se
        representa por su razón social y el ranking no tiene de dónde agarrarse.
        """
        return bool(self.sectors or self.keywords)


def construir_perfil(
    *,
    fuente: str,
    rut: str,
    legal_name: str,
    vigente: bool | None,
    fecha_inicio: str = "",
    fecha_termino_giro: str = "",
    tipo: str = "",
    actividades: list[Actividad],
    regiones_brutas: list[str],
    comunas: list[str],
    avisos: list[str] | None = None,
) -> PerfilSugerido:
    """Arma el borrador a partir de campos ya extraídos de una fuente cualquiera.

    Cada fuente resuelve su propio formato (nombres de campo, fechas, mojibake)
    y llega hasta acá con los datos ya en la forma común: un RUT con guion, una
    lista de `Actividad` y una lista de nombres de región tal como los escriba
    esa fuente. De ahí para adelante la lógica es idéntica sin importar de dónde
    vino el dato.
    """
    avisos = list(avisos) if avisos else []

    rut_valido = bool(rut) and is_valid_rut(rut)
    if rut and not rut_valido:
        avisos.append(f"el RUT {rut} no pasa la validación de dígito verificador")

    regiones: list[str] = []
    for bruta in regiones_brutas:
        if not bruta:
            continue
        # Se reusa el normalizador del backend en vez de escribir uno por
        # fuente: cada una escribe la región distinto ("V REGION VALPARAISO"
        # vs. "XIII REGION METROPOLITANA"), y una segunda numeración paralela es
        # un problema que este repositorio ya tuvo una vez.
        region_id = normalize_region_name(bruta)
        if region_id is None:
            avisos.append(f"región no reconocida: {bruta!r}")
            continue
        nombre = canonical_region_name(region_id)
        if nombre not in regiones:
            regiones.append(nombre)

    # Diccionario: unión de rubros y términos de compra (cada uno con su
    # propio respaldo por código no curado), intersección del objeto para el
    # dominio común. Ver `diccionario.py` y `clasificador_rubro.py`.
    concordancia = analizar([a.codigo for a in actividades])
    sectors: list[str] = list(concordancia.sectores)
    keywords: list[str] = list(concordancia.keywords)

    # Título de sección real del catálogo del SII, como dato auxiliar de
    # diagnóstico — NO es lo que se guarda en `Supplier.sectors` (el front no
    # conoce estos títulos), sirve para que un humano audite si el rubro
    # asignado tiene sentido. Se lee directo del catálogo, no se calcula.
    rubros_ciiu: list[str] = []
    for actividad in actividades:
        titulo = catalogo_glosas.seccion_titulo(actividad.codigo)
        if titulo and titulo not in rubros_ciiu:
            rubros_ciiu.append(titulo)

    if concordancia.sin_catalogo_sii:
        avisos.append(
            "código no encontrado en el catálogo del SII, sin glosa ni rubro "
            "posible: " + ", ".join(str(c) for c in concordancia.sin_catalogo_sii)
        )

    if concordancia.sin_diccionario:
        avisos.append(
            "sin curación fina en el diccionario, el rubro se intuyó con el "
            "clasificador por palabras clave sobre la glosa oficial: "
            + ", ".join(str(c) for c in concordancia.sin_diccionario)
        )

    if concordancia.sin_palabra_clave:
        avisos.append(
            "sin ninguna palabra clave que coincida para estos códigos: "
            + ", ".join(str(c) for c in concordancia.sin_palabra_clave)
        )

    if concordancia.sin_rubro_determinado:
        avisos.append(
            "la glosa de estos códigos no calzó con ninguna palabra clave del "
            "clasificador, quedan sin rubro determinado: "
            + ", ".join(str(c) for c in concordancia.sin_rubro_determinado)
        )

    if concordancia.fuera_de_alcance:
        avisos.append(
            "actividades sin lugar en compras públicas, excluidas del perfil: "
            + ", ".join(str(c) for c in concordancia.fuera_de_alcance)
        )

    if len(actividades) > 1 and not concordancia.hay_hilo_comun:
        avisos.append(
            "las actividades no comparten dominio: no hay un hilo común que "
            "declarar y conviene que el usuario elija a qué se dedica realmente"
        )

    if len(sectors) > 2:
        # No es un error: es el riesgo de ruido del plan, hecho visible. Una
        # empresa con rubros dispares va a atraer licitaciones de todos ellos, y
        # el usuario tiene que poder desmarcar los que no correspondan.
        avisos.append(
            f"la empresa declara {len(sectors)} rubros distintos "
            f"({', '.join(sectors)}): conviene que el usuario confirme cuáles aplican"
        )

    if actividades and not keywords:
        avisos.append(
            "todas las actividades son genéricas: para esta empresa la fuente no "
            "aporta nada al matching"
        )

    return PerfilSugerido(
        rut=rut,
        rut_valido=rut_valido,
        legal_name=legal_name,
        vigente=vigente,
        fuente=fuente,
        fecha_inicio=fecha_inicio,
        fecha_termino_giro=fecha_termino_giro,
        tipo=tipo,
        regions=regiones,
        comunas=comunas,
        sectors=sectors,
        rubros_ciiu=rubros_ciiu,
        keywords=keywords,
        dominio=concordancia.dominio,
        sin_diccionario=concordancia.sin_diccionario,
        fuera_de_alcance=concordancia.fuera_de_alcance,
        actividades=actividades,
        avisos=avisos,
    )
