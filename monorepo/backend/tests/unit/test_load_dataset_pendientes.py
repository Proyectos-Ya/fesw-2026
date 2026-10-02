"""`load_dataset.py` tiene que poder reanudarse sin recalcular lo ya indexado.

Antes indexaba todo lo que hubiera en Postgres en lotes de 32, con relleno hasta el
texto más largo del lote: con partidas de más de 10.000 caracteres el proceso moría
por memoria sin un mensaje, a medio camino, y volver a correrlo repetía el trabajo.
"""

from uuid import uuid4

from tests.matching_evaluation.load_dataset import seleccionar_pendientes


def test_omite_las_licitaciones_ya_indexadas() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()

    pendientes = seleccionar_pendientes({a: "uno", b: "dos", c: "tres"}, ya_indexadas={b})

    assert set(pendientes) == {a, c}


def test_ordena_de_texto_corto_a_largo() -> None:
    corto, medio, largo = uuid4(), uuid4(), uuid4()

    pendientes = seleccionar_pendientes(
        {largo: "x" * 500, corto: "x", medio: "x" * 50}, ya_indexadas=set()
    )

    assert pendientes == [corto, medio, largo]


def test_con_todo_indexado_no_queda_nada_pendiente() -> None:
    a = uuid4()

    assert seleccionar_pendientes({a: "texto"}, ya_indexadas={a}) == []


def test_reindexar_las_incluye_aunque_ya_esten() -> None:
    a = uuid4()

    assert seleccionar_pendientes({a: "texto"}, ya_indexadas={a}, reindexar=True) == [a]
