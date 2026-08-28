"""Los tres adaptadores de fuente: cada uno traduce el JSON de una API al
mismo `PerfilSugerido`, vía `perfil.construir_perfil`.

**Ninguno hace red.** Cada uno recibe el payload ya obtenido y lo interpreta.
Consultar la API de verdad es una decisión aparte, con sus propios términos de
uso y su costo, y no algo que estos módulos hagan de paso.

Por qué viven en un solo archivo
---------------------------------
Antes eran tres archivos (`web_empresario.py`, `ruts_info.py`, `sre.py`), uno
por fuente. Cada uno resuelve el mismo problema —parsear un esquema JSON
distinto hasta los mismos parámetros de `construir_perfil`— así que verlos uno
al lado del otro hace más fácil comparar cómo cada API resuelve lo mismo
(vigencia, actividades, domicilio) de forma distinta, que es justamente el
contenido de la tabla comparativa en `1.1-onboarding.md`. Agregar una cuarta
fuente es sumar una función `desde_<fuente>` más acá, no crear un archivo
nuevo.

Las tres devuelven un `PerfilSugerido`: un **borrador**, no el perfil final —
ver "Lo que hay que decidir aparte del experimento" en `1.1-onboarding.md`.
"""

from __future__ import annotations

from typing import Any

from .perfil import PerfilSugerido, construir_perfil
from .tipos import Actividad

# --------------------------------------------------------------------------
# Web Empresario
# --------------------------------------------------------------------------
#
# Nota sobre el nombre: este esquema se atribuyó primero a ruts.info por un
# error de etiquetado al copiar el payload de ejemplo. Es de **Web
# Empresario** — el esquema real de ruts.info es el de más abajo, con nombres
# de campo en inglés y una estructura distinta.
#
# Lo que se descubrió leyendo un payload real de esta fuente:
#
# 1. **La vigencia sí está**, y era la pregunta abierta de 1.1: `FECHA_TG_VIG`
#    vacío significa que no hay término de giro registrado. `BuscarProveedor`
#    de Mercado Público no entrega esto.
# 2. **La codificación viene rota** en algunos campos (`"VALPARAÃSO"`): UTF-8
#    interpretado como Latin-1 en el origen. Se repara acá, porque un perfil
#    con basura en el nombre de la ciudad es visible para el usuario.
# 3. **Los domicilios se repiten** casi idénticos, con distinta fecha de
#    vigencia. Interesa la región, no la dirección, así que se deduplica.
# 4. **Una empresa puede tener actividades de rubros sin relación entre sí.**
#    El ejemplo real trae construcción, comercio al por menor por internet y
#    reparación de electrodomésticos. Es el riesgo de ruido del plan, y por
#    eso el borrador reporta *todos* los rubros en vez de elegir uno: elegir
#    sería inventar una precisión que el dato no tiene.

FUENTE_WEB_EMPRESARIO = "web-empresario"


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


def _texto_we(datos: dict[str, Any], clave: str) -> str:
    valor = datos.get(clave, "")
    return reparar_mojibake(str(valor)).strip() if valor else ""


def _leer_actividades_we(crudas: Any, avisos: list[str]) -> list[Actividad]:
    if not isinstance(crudas, list):
        return []

    actividades: list[Actividad] = []
    for cruda in crudas:
        if not isinstance(cruda, dict):
            continue
        codigo = cruda.get("CODIGO_ACTIVIDAD")
        glosa = _texto_we(cruda, "DESC_ACTIVIDAD")
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
                desde=_texto_we(cruda, "FECHA_ACTECO"),
            )
        )

    return actividades


def _leer_domicilios_we(crudos: Any) -> tuple[list[str], list[str]]:
    """Regiones (sin normalizar todavía) y comunas de la lista de domicilios."""
    if not isinstance(crudos, list):
        return [], []

    regiones: list[str] = []
    comunas: list[str] = []
    for crudo in crudos:
        if not isinstance(crudo, dict):
            continue
        region = _texto_we(crudo, "REGION")
        if region and region not in regiones:
            regiones.append(region)
        comuna = _texto_we(crudo, "COMUNA")
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

    termino_giro = _texto_we(datos, "FECHA_TG_VIG")
    # Hallazgo: sin término de giro registrado, la empresa está vigente. Es el
    # dato que `BuscarProveedor` de Mercado Público no entrega.
    vigente = not termino_giro if "FECHA_TG_VIG" in datos else None
    if vigente is None:
        avisos.append("la respuesta no trae `FECHA_TG_VIG`: la vigencia queda sin determinar")

    actividades = _leer_actividades_we(datos.get("actividades"), avisos)
    regiones_brutas, comunas = _leer_domicilios_we(datos.get("domicilios"))

    return construir_perfil(
        fuente=FUENTE_WEB_EMPRESARIO,
        rut=rut,
        legal_name=_texto_we(datos, "RAZON_SOCIAL"),
        vigente=vigente,
        fecha_inicio=_texto_we(datos, "FECHA_INICIO_VIG"),
        fecha_termino_giro=termino_giro,
        tipo=_texto_we(datos, "TIPO"),
        actividades=actividades,
        regiones_brutas=regiones_brutas,
        comunas=comunas,
        avisos=avisos,
    )


# --------------------------------------------------------------------------
# ruts.info
# --------------------------------------------------------------------------
#
# Esquema completamente distinto al de Web Empresario — campos en inglés,
# estructura plana, sin el envoltorio `{"success", "data"}`:
#
#     {
#       "code": 77073851, "verification_digit": "2",
#       "business_name": "STARLINK CHILE SPA",
#       "valid_from_date": "26-09-2019", "valid_until_date": null,
#       "activities": [{"activity_code": "619090",
#                        "activity_description": "...",
#                        "iva_affects": true, "tax_category": "1"}],
#       "addresses": [{"region": "XIII REGION METROPOLITANA",
#                       "district": "LAS CONDES", "city": "SANTIAGO"}]
#     }
#
# Tres diferencias concretas con Web Empresario, encontradas al escribir este
# adaptador:
#
# 1. **La vigencia se expresa al revés.** Web Empresario tiene término de giro
#    como string vacío cuando la empresa está vigente (`FECHA_TG_VIG: ""`).
#    ruts.info usa **`null`** para lo mismo (`valid_until_date: null`).
#    Confundir los dos formatos —tratar `null` como "dato ausente" en vez de
#    "vigente sin fecha de término"— dejaría vigente a toda empresa
#    indeterminada, que es el error opuesto al que hay que evitar.
# 2. **`activity_code` es texto, no entero.** Web Empresario lo manda como
#    `433000` (int); acá llega `"619090"` (string). Ambos se normalizan al
#    mismo `Actividad.codigo: int`.
# 3. **`iva_affects` ya es booleano**, no `"S"`/`"N"` como en Web Empresario.
#
# Duda abierta, no resuelta a favor de ninguna opción: `district` en el
# ejemplo (`"LAS CONDES"`) tiene forma de comuna, no de "distrito" en el
# sentido administrativo chileno. Se trata como comuna acá porque es lo que
# calza con `Supplier`, pero un solo ejemplo no alcanza para estar seguro.

FUENTE_RUTS_INFO = "ruts-info"


def _texto_ri(datos: dict[str, Any], clave: str) -> str:
    valor = datos.get(clave)
    return str(valor).strip() if valor else ""


def _leer_actividades_ri(crudas: Any, avisos: list[str]) -> list[Actividad]:
    if not isinstance(crudas, list):
        return []

    actividades: list[Actividad] = []
    for cruda in crudas:
        if not isinstance(cruda, dict):
            continue
        codigo = cruda.get("activity_code")
        glosa = _texto_ri(cruda, "activity_description")
        try:
            codigo_int = int(str(codigo).strip())
        except (TypeError, ValueError):
            avisos.append(f"código de actividad ilegible: {codigo!r}")
            continue

        actividades.append(
            Actividad(
                codigo=codigo_int,
                glosa=glosa,
                # Ya es booleano en este esquema, a diferencia de Web
                # Empresario ("S"/"N"). `bool(None)` es `False`, que es lo
                # correcto si el campo no viene.
                afecta_iva=bool(cruda.get("iva_affects")),
                desde=_texto_ri(cruda, "activity_date"),
            )
        )

    return actividades


def _leer_domicilios_ri(crudos: Any) -> tuple[list[str], list[str]]:
    """Regiones (sin normalizar todavía) y comunas de `addresses[]`."""
    if not isinstance(crudos, list):
        return [], []

    regiones: list[str] = []
    comunas: list[str] = []
    for crudo in crudos:
        if not isinstance(crudo, dict):
            continue
        region = _texto_ri(crudo, "region")
        if region and region not in regiones:
            regiones.append(region)
        # `district` tiene forma de comuna en el único ejemplo visto ("LAS
        # CONDES"). Ver advertencia arriba.
        comuna = _texto_ri(crudo, "district")
        if comuna and comuna not in comunas:
            comunas.append(comuna)

    return regiones, comunas


def desde_ruts_info(payload: dict[str, Any]) -> PerfilSugerido:
    """Interpreta la respuesta de ruts.info. No hace ninguna llamada de red."""
    if not isinstance(payload, dict) or "code" not in payload:
        raise ValueError(
            "la respuesta no tiene el esquema esperado de ruts.info "
            "(falta la clave `code` en el nivel superior)"
        )

    avisos: list[str] = []

    cuerpo = str(payload.get("code", "")).strip()
    dv = str(payload.get("verification_digit", "")).strip().upper()
    rut = f"{cuerpo}-{dv}" if cuerpo and dv else ""

    # Al revés que Web Empresario: acá `null` explícito es "vigente", y la
    # ausencia de la clave es lo indeterminado.
    if "valid_until_date" not in payload:
        vigente = None
        avisos.append(
            "la respuesta no trae `valid_until_date`: la vigencia queda sin determinar"
        )
    else:
        vigente = payload.get("valid_until_date") is None

    actividades = _leer_actividades_ri(payload.get("activities"), avisos)
    regiones_brutas, comunas = _leer_domicilios_ri(payload.get("addresses"))

    return construir_perfil(
        fuente=FUENTE_RUTS_INFO,
        rut=rut,
        legal_name=_texto_ri(payload, "business_name"),
        vigente=vigente,
        fecha_inicio=_texto_ri(payload, "valid_from_date"),
        fecha_termino_giro=_texto_ri(payload, "valid_until_date"),
        actividades=actividades,
        regiones_brutas=regiones_brutas,
        comunas=comunas,
        avisos=avisos,
    )


# --------------------------------------------------------------------------
# SRE (sre.cl/api/company_info)
# --------------------------------------------------------------------------
#
# Esquema real (POST, respuesta confirmada en vivo el 26-08-2026):
#
#     {
#       "razon_social": "Planeta Libre Soluciones Sustentables Limitada",
#       "rut": "76668304-5",
#       "dte_email": "cl.empresas@defontanadte.com",
#       "fecha_resol": "22-08-2014", "numero_resol": 80,
#       "actecos": ["433000", "479100", "952200"],
#       "url": "", "actualizado": "2026-08-25",
#       "glosa_giro": null, "es_mipyme": false,
#       "consultas_restantes": 48
#     }
#
# Es la fuente **más pobre de las tres** para el perfil, y la más rica para
# otra cosa que ninguna de las otras dos tiene.
#
# Lo que NO entrega, y que sí entregan Web Empresario o ruts.info:
#
# 1. **Ninguna glosa por actividad.** `actecos` es una lista de códigos
#    pelados (`"433000"`, como texto). Sin esto, no hay texto sobre el cual
#    correr el clasificador de rubro (`clasificador_rubro.py`) — necesita una
#    glosa, no un número. Se resuelve con el catálogo del SII ya cargado en
#    este mismo PoC (`catalogo.py`, construido desde el xlsx que se procesó
#    para 1.1): la glosa no se inventa ni se pide a otra API, se recupera de
#    una fuente que ya se tiene y ya se verificó. `keywords`, en cambio, no
#    usa la glosa para nada —ver `diccionario.terminos_de`—, así que en eso
#    SRE no está en desventaja frente a las otras dos fuentes.
# 2. **Cero datos de domicilio.** Ni región, ni comuna, ni dirección. **SRE
#    no puede aportar nada a `Supplier.regions`.**
# 3. **Ninguna señal de vigencia.** No hay equivalente a `FECHA_TG_VIG` (Web
#    Empresario) ni a `valid_until_date` (ruts.info).
# 4. **Ninguna actividad marcada como principal**, igual que las otras dos.
#
# Lo que SÍ entrega y las otras dos no:
#
# - **`dte_email`**: correo de facturación electrónica. Sin campo propio en
#   `Supplier` hoy, pero vale la pena anotarlo como candidato a futuro.
# - **`es_mipyme`**: clasificación oficial MIPYME. Podría ser un criterio de
#   segmentación (hay licitaciones con criterios preferentes para MIPYME).
# - **`glosa_giro`**: giro declarado en texto libre, cuando existe (acá viene
#   `null`). Con una muestra de uno no se sabe qué tan seguido viene poblado.
# - **`consultas_restantes`**: la API expone su propia cuota en cada
#   respuesta — útil para decidir si aguanta el volumen de un onboarding
#   masivo sin pedirlo aparte.
#
# Sobre `fecha_resol`/`numero_resol`: **no está claro qué acto administrativo
# es**. Se guarda como dato auxiliar (`fecha_inicio`) sin afirmar más de lo
# que se sabe con un solo ejemplo.

FUENTE_SRE = "sre"

# Claves que identifican esta respuesta como la de SRE y no otra cosa. Sirve
# para fallar rápido y claro si alguien pasa el payload equivocado.
_CLAVES_ESPERADAS_SRE = ("razon_social", "rut", "actecos")


def _texto_sre(payload: dict[str, Any], clave: str) -> str:
    valor = payload.get(clave)
    return str(valor).strip() if valor else ""


def _leer_actividades_sre(crudos: Any, avisos: list[str]) -> list[Actividad]:
    from .catalogo import glosa_oficial

    if not isinstance(crudos, list):
        return []

    actividades: list[Actividad] = []
    for crudo in crudos:
        try:
            codigo = int(str(crudo).strip())
        except (TypeError, ValueError):
            avisos.append(f"código de actividad ilegible: {crudo!r}")
            continue

        glosa = glosa_oficial(codigo)
        if not glosa:
            avisos.append(
                f"actividad {codigo}: SRE no entrega glosa y el código no está "
                "en el catálogo local del SII — queda sin descripción"
            )
        actividades.append(Actividad(codigo=codigo, glosa=glosa))

    return actividades


def desde_sre(payload: dict[str, Any]) -> PerfilSugerido:
    """Interpreta la respuesta de SRE. No hace ninguna llamada de red."""
    if not isinstance(payload, dict) or not all(
        c in payload for c in _CLAVES_ESPERADAS_SRE
    ):
        raise ValueError(
            "la respuesta no tiene el esquema esperado de SRE "
            f"(faltan una o más de: {', '.join(_CLAVES_ESPERADAS_SRE)})"
        )

    avisos: list[str] = [
        "SRE no entrega domicilio: la región queda sin dato desde esta fuente",
        "SRE no entrega término de giro ni vigencia: queda sin determinar",
    ]

    rut = str(payload.get("rut", "")).strip()
    actividades = _leer_actividades_sre(payload.get("actecos"), avisos)

    perfil = construir_perfil(
        fuente=FUENTE_SRE,
        rut=rut,
        legal_name=_texto_sre(payload, "razon_social"),
        vigente=None,
        fecha_inicio=_texto_sre(payload, "fecha_resol"),
        actividades=actividades,
        regiones_brutas=[],
        comunas=[],
        avisos=avisos,
    )

    # Datos que SRE sí trae y ninguna otra fuente entrega, sin campo propio en
    # `PerfilSugerido` todavía. Se dejan en avisos para que no se pierdan del
    # informe, sin inventarles un campo del dominio que no existe.
    email = _texto_sre(payload, "dte_email")
    if email:
        perfil.avisos.append(f"dato adicional (sin campo en Supplier): dte_email={email}")
    if payload.get("es_mipyme") is not None:
        perfil.avisos.append(
            f"dato adicional (sin campo en Supplier): es_mipyme={payload['es_mipyme']}"
        )
    glosa_giro = _texto_sre(payload, "glosa_giro")
    if glosa_giro:
        perfil.avisos.append(f"dato adicional (sin campo en Supplier): glosa_giro={glosa_giro}")

    return perfil
