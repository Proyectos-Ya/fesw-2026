"""Del payload de **ruts.info** a un borrador de perfil de proveedor.

**No hace red.** Recibe el JSON ya obtenido y lo interpreta.

Esquema, y en qué se diferencia de Web Empresario
--------------------------------------------------
Nombres de campo en inglés y estructura plana, sin el envoltorio
`{"success", "data"}` de Web Empresario:

    {
      "code": 77073851, "verification_digit": "2",
      "business_name": "STARLINK CHILE SPA",
      "valid_from_date": "26-09-2019", "valid_until_date": null,
      "activities": [{"activity_code": "619090", "activity_description": "...",
                       "iva_affects": true, "tax_category": "1"}],
      "addresses": [{"region": "XIII REGION METROPOLITANA",
                      "district": "LAS CONDES", "city": "SANTIAGO"}]
    }

Tres diferencias concretas con Web Empresario, encontradas al escribir este
adaptador:

1. **La vigencia se expresa al revés.** Web Empresario tiene término de giro
   como string vacío cuando la empresa está vigente (`FECHA_TG_VIG: ""`).
   ruts.info usa **`null`** para lo mismo (`valid_until_date: null`). Confundir
   los dos formatos —tratar `null` como "dato ausente" en vez de "vigente sin
   fecha de término"— dejaría vigente a toda empresa indeterminada, que es el
   error opuesto al que hay que evitar.

2. **`activity_code` es texto, no entero.** Web Empresario lo manda como
   `433000` (int); acá llega `"619090"` (string). Ambos se normalizan al mismo
   `Actividad.codigo: int`, así que el resto del pipeline —diccionario,
   secciones CIIU— no nota la diferencia.

3. **`iva_affects` ya es booleano**, no `"S"`/`"N"` como en Web Empresario. Un
   detalle menor, pero es el tipo de cosa que revienta en silencio si se
   reutiliza código pensado para la otra fuente sin adaptarlo.

Y una duda que queda abierta, no resuelta a favor de ninguna opción: `district`
en el ejemplo (`"LAS CONDES"`) tiene forma de comuna, no de "distrito" en el
sentido administrativo chileno. Se trata como comuna acá porque es lo que
calza con `Supplier`, pero conviene confirmarlo con más muestras — un solo
ejemplo no alcanza para estar seguro de que `district` sea siempre eso.
"""

from __future__ import annotations

from typing import Any

from .ciiu import Actividad
from .perfil import PerfilSugerido, construir_perfil

FUENTE = "ruts-info"


def _texto(datos: dict[str, Any], clave: str) -> str:
    valor = datos.get(clave)
    return str(valor).strip() if valor else ""


def _leer_actividades(crudas: Any, avisos: list[str]) -> list[Actividad]:
    if not isinstance(crudas, list):
        return []

    actividades: list[Actividad] = []
    for cruda in crudas:
        if not isinstance(cruda, dict):
            continue
        codigo = cruda.get("activity_code")
        glosa = _texto(cruda, "activity_description")
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
                desde=_texto(cruda, "activity_date"),
            )
        )

    return actividades


def _leer_domicilios(crudos: Any) -> tuple[list[str], list[str]]:
    """Regiones (sin normalizar todavía) y comunas de `addresses[]`."""
    if not isinstance(crudos, list):
        return [], []

    regiones: list[str] = []
    comunas: list[str] = []
    for crudo in crudos:
        if not isinstance(crudo, dict):
            continue
        region = _texto(crudo, "region")
        if region and region not in regiones:
            regiones.append(region)
        # `district` tiene forma de comuna en el único ejemplo visto ("LAS
        # CONDES"). Ver advertencia en el docstring del módulo.
        comuna = _texto(crudo, "district")
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
    # ausencia de la clave es lo indeterminado. Ver punto 1 del docstring.
    if "valid_until_date" not in payload:
        vigente = None
        avisos.append(
            "la respuesta no trae `valid_until_date`: la vigencia queda sin determinar"
        )
    else:
        vigente = payload.get("valid_until_date") is None

    actividades = _leer_actividades(payload.get("activities"), avisos)
    regiones_brutas, comunas = _leer_domicilios(payload.get("addresses"))

    return construir_perfil(
        fuente=FUENTE,
        rut=rut,
        legal_name=_texto(payload, "business_name"),
        vigente=vigente,
        fecha_inicio=_texto(payload, "valid_from_date"),
        fecha_termino_giro=_texto(payload, "valid_until_date"),
        actividades=actividades,
        regiones_brutas=regiones_brutas,
        comunas=comunas,
        avisos=avisos,
    )
