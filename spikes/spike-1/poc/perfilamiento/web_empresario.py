"""Del payload de **Web Empresario** a un borrador de perfil de proveedor.

**No hace red.** Recibe el JSON ya obtenido y lo interpreta. Consultar la API es
una decisión aparte, con sus propios términos de uso y su costo, y no algo que
este módulo haga de paso.

Nota sobre el nombre
---------------------
Este módulo se llamó `ruts_info.py` en una primera versión: el payload de
ejemplo se etiquetó como ruts.info por error. Verificado que es de
**Web Empresario** — el esquema real de ruts.info está en `ruts_info.py`, con
nombres de campo en inglés y una estructura distinta. Los dos comparten la
lógica de perfilamiento en `perfil.py`; acá solo queda el parseo de este
formato particular.

Lo que se descubrió leyendo un payload real
-------------------------------------------
1. **La vigencia sí está**, y era la pregunta abierta de 1.1: `FECHA_TG_VIG`
   vacío significa que no hay término de giro registrado. `BuscarProveedor` de
   Mercado Público no entrega esto.
2. **La codificación viene rota** en algunos campos (`"VALPARAÃSO"`): UTF-8
   interpretado como Latin-1 en el origen. Se repara acá, porque un perfil con
   basura en el nombre de la ciudad es visible para el usuario.
3. **Los domicilios se repiten** casi idénticos, con distinta fecha de vigencia.
   Interesa la región, no la dirección, así que se deduplica por región.
4. **Una empresa puede tener actividades de rubros sin relación entre sí.** El
   ejemplo real trae construcción, comercio al por menor por internet y
   reparación de electrodomésticos. Es el riesgo de ruido del plan, y por eso el
   borrador reporta *todos* los rubros en vez de elegir uno: elegir sería
   inventar una precisión que el dato no tiene.
"""

from __future__ import annotations

from typing import Any

from .ciiu import Actividad
from .perfil import PerfilSugerido, construir_perfil

FUENTE = "web-empresario"


def reparar_mojibake(texto: str) -> str:
    """Arregla el texto UTF-8 que fue decodificado como Latin-1 en el origen.

    `"VALPARAÃSO"` debería ser `"VALPARAÍSO"`. Se intenta la reparación solo si
    aparece alguna de las secuencias delatoras; si el intento falla, se devuelve
    el texto tal cual — es preferible mostrar el original a romper un texto que
    estaba bien.
    """
    if not any(marca in texto for marca in ("Ã", "Â", "â€")):
        return texto
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def _texto(datos: dict[str, Any], clave: str) -> str:
    valor = datos.get(clave, "")
    return reparar_mojibake(str(valor)).strip() if valor else ""


def _leer_actividades(crudas: Any, avisos: list[str]) -> list[Actividad]:
    if not isinstance(crudas, list):
        return []

    actividades: list[Actividad] = []
    for cruda in crudas:
        if not isinstance(cruda, dict):
            continue
        codigo = cruda.get("CODIGO_ACTIVIDAD")
        glosa = _texto(cruda, "DESC_ACTIVIDAD")
        try:
            codigo_int = int(codigo)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            avisos.append(f"código de actividad ilegible: {codigo!r}")
            continue

        actividades.append(
            Actividad(
                codigo=codigo_int,
                glosa=glosa,
                afecta_iva=str(cruda.get("AFECTA_IVA", "")).upper() == "S",
                desde=_texto(cruda, "FECHA_ACTECO"),
            )
        )

    return actividades


def _leer_domicilios(crudos: Any) -> tuple[list[str], list[str]]:
    """Regiones (sin normalizar todavía) y comunas de la lista de domicilios."""
    if not isinstance(crudos, list):
        return [], []

    regiones: list[str] = []
    comunas: list[str] = []
    for crudo in crudos:
        if not isinstance(crudo, dict):
            continue
        region = _texto(crudo, "REGION")
        if region and region not in regiones:
            regiones.append(region)
        comuna = _texto(crudo, "COMUNA")
        if comuna and comuna not in comunas:
            comunas.append(comuna)

    return regiones, comunas


def desde_web_empresario(payload: dict[str, Any]) -> PerfilSugerido:
    """Interpreta la respuesta de Web Empresario. No hace ninguna llamada de red."""
    if not payload.get("success"):
        raise ValueError("la respuesta no indica éxito (`success` no es verdadero)")

    datos = payload.get("data")
    if not isinstance(datos, dict):
        raise ValueError("la respuesta no trae un objeto `data`")

    avisos: list[str] = []

    cuerpo = str(datos.get("RUT", "")).strip()
    dv = str(datos.get("DV", "")).strip().upper()
    rut = f"{cuerpo}-{dv}" if cuerpo and dv else ""

    termino_giro = _texto(datos, "FECHA_TG_VIG")
    # Hallazgo: sin término de giro registrado, la empresa está vigente. Es el
    # dato que `BuscarProveedor` de Mercado Público no entrega.
    vigente = not termino_giro if "FECHA_TG_VIG" in datos else None
    if vigente is None:
        avisos.append("la respuesta no trae `FECHA_TG_VIG`: la vigencia queda sin determinar")

    actividades = _leer_actividades(datos.get("actividades"), avisos)
    regiones_brutas, comunas = _leer_domicilios(datos.get("domicilios"))

    return construir_perfil(
        fuente=FUENTE,
        rut=rut,
        legal_name=_texto(datos, "RAZON_SOCIAL"),
        vigente=vigente,
        fecha_inicio=_texto(datos, "FECHA_INICIO_VIG"),
        fecha_termino_giro=termino_giro,
        tipo=_texto(datos, "TIPO"),
        actividades=actividades,
        regiones_brutas=regiones_brutas,
        comunas=comunas,
        avisos=avisos,
    )
