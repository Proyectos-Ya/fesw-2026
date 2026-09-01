"""Heurísticas de resolución de comuna desde el nombre del organismo comprador.

Compra Ágil (la API en producción) no entrega comuna en ningún campo. Dos
heurísticas, en cascada (`resolve_comuna`):

1. `resolve_comuna_from_organismo_name` — en Chile cada municipalidad se llama
   literalmente "(I.) Municipalidad de <comuna>", y el nombre ya viene en
   `institucion.organismo_comprador`, sin costo de red. Ver PENDIENTES.md
   6.19: verificado en vivo, 12/12 municipalidades de una muestra real de
   Compra Ágil se resolvieron con este matcher.
2. `resolve_comuna_from_organismo_name_generic` — respaldo cuando la primera
   no matchea: busca el nombre de cualquier comuna en cualquier parte del
   texto ("Hospital de X", "Corporación Municipal de X", etc.), con dos
   resguardos encontrados revisando los nombres reales de la base (ver los
   tests de regresión más abajo).
"""

from app.shared.comunas import (
    resolve_comuna,
    resolve_comuna_from_organismo_name,
    resolve_comuna_from_organismo_name_generic,
)


def test_resuelve_municipalidad_con_prefijo_i():
    assert (
        resolve_comuna_from_organismo_name("I MUNICIPALIDAD DE VITACURA") == "Vitacura"
    )


def test_resuelve_municipalidad_con_prefijo_ilustre():
    assert (
        resolve_comuna_from_organismo_name("Ilustre Municipalidad de Yerbas Buenas")
        == "Yerbas Buenas"
    )


def test_resuelve_sin_tilde_en_el_nombre_de_la_comuna():
    # Mercado Público suele mandar los nombres sin acentuar.
    assert (
        resolve_comuna_from_organismo_name("I MUNICIPALIDAD DE SANTA BARBARA")
        == "Santa Bárbara"
    )
    assert resolve_comuna_from_organismo_name("I MUNICIPALIDAD DE CHAITEN") == "Chaitén"


def test_no_sobrecaptura_cuando_el_nombre_sigue_con_mas_texto():
    # Un regex ingenuo capturaría "CABRERO DEPARTAMENTO DE SALUD" entero.
    assert (
        resolve_comuna_from_organismo_name(
            "I MUNICIPALIDAD DE CABRERO DEPARTAMENTO DE SALUD"
        )
        == "Cabrero"
    )


def test_prefiere_el_nombre_de_comuna_mas_largo_que_calce():
    # "Puerto Montt" no debe perder contra una comuna corta que sea prefijo.
    assert (
        resolve_comuna_from_organismo_name("I MUNICIPALIDAD DE PUERTO MONTT")
        == "Puerto Montt"
    )


def test_nombre_no_municipal_no_resuelve():
    assert resolve_comuna_from_organismo_name("SERVICIO ELECTORAL") is None
    assert resolve_comuna_from_organismo_name("UNIVERSIDAD DE CHILE") is None
    assert resolve_comuna_from_organismo_name("PRESIDENCIA DE LA REPUBLICA") is None


def test_comuna_no_reconocida_no_resuelve():
    assert (
        resolve_comuna_from_organismo_name("I MUNICIPALIDAD DE UN LUGAR INVENTADO")
        is None
    )


def test_entrada_vacia_o_nula_no_resuelve():
    assert resolve_comuna_from_organismo_name(None) is None
    assert resolve_comuna_from_organismo_name("") is None


# ---------------------------------------------------------------------------
# resolve_comuna_from_organismo_name_generic: respaldo, nombre de comuna en
# cualquier parte del texto -- no solo tras "Municipalidad de". Casos y
# resguardos verificados contra los nombres reales de buyer_institution
# (ver PENDIENTES.md 6.19, actualización sobre heurísticas adicionales).
# ---------------------------------------------------------------------------


def test_generica_resuelve_hospital_de_comuna():
    assert (
        resolve_comuna_from_organismo_name_generic(
            "SERVICIO NACIONAL DE SALUD HOSPITAL DE LOTA"
        )
        == "Lota"
    )


def test_generica_resuelve_corporacion_municipal_de_comuna():
    assert (
        resolve_comuna_from_organismo_name_generic(
            "CORP MUNICIPAL DE DESARROLLO SOCIAL DE PUDAHUEL"
        )
        == "Pudahuel"
    )


def test_generica_resuelve_direccion_regional_con_guion():
    assert (
        resolve_comuna_from_organismo_name_generic(
            "Dirección Regional de Gendarmeria - Talca"
        )
        == "Talca"
    )


def test_generica_prefiere_el_match_mas_a_la_derecha_no_el_mas_largo():
    """Regresión real: "O'Higgins" (más largo, comuna de Aysén sin relación)
    perdía contra el "más largo gana" e ignoraba "Rancagua", que es la comuna
    correcta y aparece al final -- el patrón habitual en estos nombres."""
    assert (
        resolve_comuna_from_organismo_name_generic(
            "SERVICIO DE SALUD DEL LIBERTADOR B O'HIGGINS HOSPITAL REG RANCAGUA"
        )
        == "Rancagua"
    )


def test_generica_no_matchea_el_nombre_de_una_region():
    """Regresión real: sin este resguardo, resolvía a "Santiago" porque el
    nombre completo de la región termina en "de Santiago" -- no porque el
    organismo esté en esa comuna."""
    assert (
        resolve_comuna_from_organismo_name_generic(
            "CENTRO DE FORMACION TECNICA DE LA REGION METROPOLITANA DE SANTIAGO"
        )
        is None
    )


def test_generica_si_matchea_regional_con_al_no_es_region():
    """ "Regional" (adjetivo) no es "región": la sede de una entidad *regional*
    sí puede estar en la comuna que nombra."""
    assert (
        resolve_comuna_from_organismo_name_generic(
            "DELEGACIÓN PRESIDENCIAL REGIONAL METROPOLITANA DE SANTIAGO"
        )
        == "Santiago"
    )


def test_generica_sin_ninguna_comuna_en_el_texto_no_resuelve():
    assert resolve_comuna_from_organismo_name_generic("MINISTERIO PUBLICO") is None
    assert resolve_comuna_from_organismo_name_generic("Ejercito de Chile") is None


def test_generica_entrada_vacia_o_nula_no_resuelve():
    assert resolve_comuna_from_organismo_name_generic(None) is None
    assert resolve_comuna_from_organismo_name_generic("") is None


# ---------------------------------------------------------------------------
# resolve_comuna: orquesta las dos en cascada, la específica primero.
# ---------------------------------------------------------------------------


def test_resolve_comuna_prefiere_la_especifica_sobre_la_generica():
    comuna, fuente = resolve_comuna("I MUNICIPALIDAD DE VITACURA")
    assert comuna == "Vitacura"
    assert fuente == "organismo_name"


def test_resolve_comuna_cae_a_la_generica_si_la_especifica_no_matchea():
    comuna, fuente = resolve_comuna("SERVICIO NACIONAL DE SALUD HOSPITAL DE LOTA")
    assert comuna == "Lota"
    assert fuente == "organismo_name_generic"


def test_resolve_comuna_ninguna_resuelve():
    assert resolve_comuna("MINISTERIO PUBLICO") == (None, None)


def test_resolve_comuna_entrada_vacia_o_nula():
    assert resolve_comuna(None) == (None, None)
    assert resolve_comuna("") == (None, None)
