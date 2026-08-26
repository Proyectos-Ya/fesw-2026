"""Del payload de **SRE** (`sre.cl/api/company_info`) a un borrador de perfil.

**No hace red.** Recibe el JSON ya obtenido y lo interpreta.

Esquema real (POST, respuesta confirmada en vivo el 26-08-2026)
------------------------------------------------------------------

    {
      "razon_social": "Planeta Libre Soluciones Sustentables Limitada",
      "rut": "76668304-5",
      "dte_email": "cl.empresas@defontanadte.com",
      "fecha_resol": "22-08-2014", "numero_resol": 80,
      "actecos": ["433000", "479100", "952200"],
      "url": "", "actualizado": "2026-08-25",
      "glosa_giro": null, "es_mipyme": false,
      "consultas_restantes": 48
    }

Es la fuente **más pobre de las tres** para el perfil, y la más rica para otra
cosa que ninguna de las otras dos tiene.

Lo que NO entrega, y que sí entregan Web Empresario o ruts.info
------------------------------------------------------------------

1. **Ninguna glosa por actividad.** `actecos` es una lista de códigos pelados
   (`"433000"`, como texto). Sin esto, no hay cómo derivar `keywords` por la vía
   de respaldo (glosa normalizada) ni decidir si una actividad es genérica —
   ambas rutinas necesitan texto, no un número. Se resuelve con el catálogo del
   SII ya cargado en este mismo PoC (`catalogo_glosas.py`, construido desde el
   xlsx que se procesó para 1.4): la glosa no se inventa ni se pide a otra API,
   se recupera de una fuente que ya se tiene y ya se verificó.

2. **Cero datos de domicilio.** Ni región, ni comuna, ni dirección. **SRE no
   puede aportar nada a `Supplier.regions`.**

3. **Ninguna señal de vigencia.** No hay equivalente a `FECHA_TG_VIG` (Web
   Empresario) ni a `valid_until_date` (ruts.info). La pregunta que more
   1.1-onboarding.md dejó abierta sigue sin responder por esta vía.

4. **Ninguna actividad marcada como principal**, igual que las otras dos.

Lo que SÍ entrega y las otras dos no
--------------------------------------

- **`dte_email`**: correo de facturación electrónica. No hay campo en
  `Supplier` para esto hoy, pero es un dato de contacto real y verificado —
  vale la pena anotarlo como candidato a futuro, no descartarlo solo porque no
  calza con el esquema actual.
- **`es_mipyme`**: booleano oficial de clasificación MIPYME. Tampoco tiene
  campo en `Supplier`, pero podría ser un criterio de segmentación o de
  beneficios (hay licitaciones con criterios preferentes para MIPYME).
- **`glosa_giro`**: giro declarado en texto libre, cuando existe (acá viene
  `null`). Con una muestra de uno no se puede saber qué tan seguido viene
  poblado.
- **`consultas_restantes`**: la API expone su propia cuota restante en cada
  respuesta. Dato operacional, no de negocio, pero útil para decidir si esta
  fuente aguanta el volumen de un onboarding masivo sin pedirlo aparte.

Sobre `fecha_resol`/`numero_resol`: **no está claro qué acto administrativo
es**. Podría ser la fecha de inicio de actividades o la resolución de un
trámite del SII no relacionado con la vigencia. Se guarda como dato auxiliar
(`fecha_inicio`) sin afirmar más de lo que se sabe — confirmarlo requiere
comparar contra más muestras o preguntarle a la documentación de la API.
"""

from __future__ import annotations

from typing import Any

from .catalogo_glosas import glosa_oficial
from .ciiu import Actividad
from .perfil import PerfilSugerido, construir_perfil

FUENTE = "sre"

# Claves que identifican esta respuesta como la de SRE y no otra cosa. Sirve
# para fallar rápido y claro si alguien pasa el payload equivocado.
_CLAVES_ESPERADAS = ("razon_social", "rut", "actecos")


def _texto(payload: dict[str, Any], clave: str) -> str:
    valor = payload.get(clave)
    return str(valor).strip() if valor else ""


def _leer_actividades(crudos: Any, avisos: list[str]) -> list[Actividad]:
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
    if not isinstance(payload, dict) or not all(c in payload for c in _CLAVES_ESPERADAS):
        raise ValueError(
            "la respuesta no tiene el esquema esperado de SRE "
            f"(faltan una o más de: {', '.join(_CLAVES_ESPERADAS)})"
        )

    avisos: list[str] = [
        "SRE no entrega domicilio: la región queda sin dato desde esta fuente",
        "SRE no entrega término de giro ni vigencia: queda sin determinar",
    ]

    rut = str(payload.get("rut", "")).strip()
    actividades = _leer_actividades(payload.get("actecos"), avisos)

    perfil = construir_perfil(
        fuente=FUENTE,
        rut=rut,
        legal_name=_texto(payload, "razon_social"),
        vigente=None,
        fecha_inicio=_texto(payload, "fecha_resol"),
        actividades=actividades,
        regiones_brutas=[],
        comunas=[],
        avisos=avisos,
    )

    # Datos que SRE sí trae y ninguna otra fuente entrega, sin campo propio en
    # `PerfilSugerido` todavía. Se dejan en avisos para que no se pierdan del
    # informe, sin inventarles un campo del dominio que no existe.
    email = _texto(payload, "dte_email")
    if email:
        perfil.avisos.append(f"dato adicional (sin campo en Supplier): dte_email={email}")
    if payload.get("es_mipyme") is not None:
        perfil.avisos.append(
            f"dato adicional (sin campo en Supplier): es_mipyme={payload['es_mipyme']}"
        )
    glosa_giro = _texto(payload, "glosa_giro")
    if glosa_giro:
        perfil.avisos.append(f"dato adicional (sin campo en Supplier): glosa_giro={glosa_giro}")

    return perfil
