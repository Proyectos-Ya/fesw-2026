"""Heurística de resolución de comuna desde el nombre del organismo comprador.

Compra Ágil (la API en producción) no entrega comuna en ningún campo, pero en
Chile cada municipalidad se llama literalmente "(I.) Municipalidad de <comuna>"
— el nombre ya viene en `institucion.organismo_comprador`, sin costo de red.
Ver PENDIENTES.md 6.19: verificado en vivo, 12/12 municipalidades de una
muestra real de Compra Ágil se resolvieron con este matcher.
"""

from app.shared.comunas import resolve_comuna_from_organismo_name


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
