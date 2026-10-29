"""El cortacircuito de la cola corta por proporción de fallas, no por racha.

El 2026-10-19 en hora punta el detalle daba 504 o 500 entre el 30 y el 67% de
las veces y aun así entraban licitaciones. Con 10 detalles pedidos a la vez, 10
errores seguidos salían solos: la corrida de las 16:02 se cortó a los 2,8 min
con 938 pendientes y procesando 17. Ahora corta cuando fallan
`FALLAS_CORTACIRCUITO` de los últimos `VENTANA_CORTACIRCUITO` resultados, que
es lo que se ve con la API caída de verdad.
"""

from app.infrastructure.services.tenders.tender_ingestion_service import (
    FALLAS_CORTACIRCUITO,
    VENTANA_CORTACIRCUITO,
    _Cortacircuito,
)


def _alimentar(cortacircuito: _Cortacircuito, patron: str, veces: int) -> None:
    """`patron` es una secuencia de `x` (falla) y `o` (éxito)."""
    for _ in range(veces):
        for marca in patron:
            if marca == "x":
                cortacircuito.fallo()
            else:
                cortacircuito.exito()


def test_los_valores_son_27_de_30():
    assert (FALLAS_CORTACIRCUITO, VENTANA_CORTACIRCUITO) == (27, 30)


def test_todo_falla_corta_al_llegar_al_umbral():
    c = _Cortacircuito()
    _alimentar(c, "x", FALLAS_CORTACIRCUITO - 1)
    assert not c.abierto.is_set()
    c.fallo()
    assert c.abierto.is_set()


def test_hora_punta_con_30_por_ciento_de_fallas_no_corta():
    c = _Cortacircuito()
    _alimentar(c, "xxxooooooo", 20)
    assert not c.abierto.is_set()


def test_dos_de_cada_tres_fallando_no_corta():
    """Como la corrida del 10-19 a las 16:02: 35 de 52 fallaron."""
    c = _Cortacircuito()
    _alimentar(c, "xxo", 30)
    assert not c.abierto.is_set()


def test_una_racha_de_diez_ya_no_corta():
    c = _Cortacircuito()
    _alimentar(c, "oooooooooo", 2)
    _alimentar(c, "x", 10)
    assert not c.abierto.is_set()


def test_un_exito_suelto_no_lo_salva_si_casi_todo_falla():
    c = _Cortacircuito()
    _alimentar(c, "xxxxxxxxxxxxxxo", 3)
    assert c.abierto.is_set()


def test_lo_viejo_sale_de_la_ventana():
    c = _Cortacircuito()
    _alimentar(c, "x", FALLAS_CORTACIRCUITO - 1)
    _alimentar(c, "o", VENTANA_CORTACIRCUITO)
    _alimentar(c, "x", FALLAS_CORTACIRCUITO - 1)
    assert not c.abierto.is_set()
