"""Diagnóstico de cabezas múltiples de Alembic.

El fallo que cubren estos tests no es que el CI no detecte el problema —eso ya lo
hacía contando líneas de `alembic heads`—, sino que al detectarlo no dijera *cuál*
de las dos soluciones del `docs/guides/alembic-migraciones.md` (Problema A)
corresponde. Elegir mal tiene consecuencias distintas: repuntar el
`down_revision` de una migración que otros ya aplicaron les rompe el historial,
y hacer `merge heads` de una migración que solo existe en tu rama deja el grafo
bifurcado sin necesidad.

El caso que más fácil se hace mal a mano, y por eso tiene su propio test: cuando
tu rama trae **dos** migraciones encadenadas, lo que hay que repuntar es la
primera de la cadena, no la cabeza. Repuntar la cabeza rompe tu propia cadena.
"""

import pytest

from scripts.migraciones import Revision, aplicar_arreglo, diagnosticar


def _rev(revision: str, abajo: str | tuple[str, ...] | None) -> Revision:
    return Revision(revision=revision, abajo=abajo, archivo=f"{revision}_x.py")


# Historia lineal: a <- b
LINEAL = [_rev("a", None), _rev("b", "a")]

# Bifurcación: a <- b (develop) y a <- c (tu rama)
BIFURCADA = [_rev("a", None), _rev("b", "a"), _rev("c", "a")]


def test_una_sola_cabeza_no_es_conflicto():
    d = diagnosticar(LINEAL, nuevas=set())

    assert d.estado == "ok"
    assert d.cabezas == ("b",)


def test_historia_vacia_no_es_conflicto():
    assert diagnosticar([], nuevas=set()).estado == "ok"


def test_dos_cabezas_con_una_nueva_se_repunta():
    """Solución 1 de la guía: la migración sigue solo en la rama."""
    d = diagnosticar(BIFURCADA, nuevas={"c"})

    assert d.estado == "repuntar"
    assert d.archivo == "c_x.py"
    assert d.destino == "b"


def test_se_repunta_la_raiz_de_la_cadena_y_no_la_cabeza():
    """Con dos migraciones propias, repuntar la cabeza rompería la cadena.

    Grafo: a <- b (develop), y a <- c <- d (la rama). La cabeza de la rama es
    `d`, pero la que cuelga del ancestro común es `c`.
    """
    historia = [*BIFURCADA, _rev("d", "c")]

    d = diagnosticar(historia, nuevas={"c", "d"})

    assert d.estado == "repuntar"
    assert d.archivo == "c_x.py"
    assert d.destino == "b"


def test_dos_cabezas_ya_publicadas_piden_merge():
    """Solución 2: si ninguna es nueva, ya viven en develop/main."""
    d = diagnosticar(BIFURCADA, nuevas=set())

    assert d.estado == "merge"
    assert set(d.cabezas) == {"b", "c"}


def test_tres_cabezas_se_resuelven_a_mano():
    historia = [*BIFURCADA, _rev("e", "a")]

    assert diagnosticar(historia, nuevas={"c"}).estado == "manual"


def test_dos_cabezas_ambas_nuevas_se_resuelven_a_mano():
    """Las dos salieron de la rama: el script no adivina cuál va primero."""
    assert diagnosticar(BIFURCADA, nuevas={"b", "c"}).estado == "manual"


def test_una_migracion_de_merge_no_se_repunta():
    """Una revisión con dos padres es un `merge heads` ya hecho.

    Reescribir su `down_revision` desharía la unión en silencio, así que el
    diagnóstico manda resolver a mano aunque sea nueva en la rama.
    """
    historia = [
        _rev("a", None),
        _rev("b", "a"),
        _rev("c", "a"),
        _rev("m", ("b", "c")),
        _rev("d", "a"),
    ]

    assert diagnosticar(historia, nuevas={"m"}).estado == "manual"


def test_arreglar_solo_cambia_la_linea_de_down_revision(tmp_path):
    migracion = tmp_path / "c_x.py"
    migracion.write_text(
        '"""agrega notas\n\n'
        "Revision ID: c\n"
        "Revises: a\n"
        '"""\n\n'
        'revision: str = "c"\n'
        'down_revision: str | Sequence[str] | None = "a"\n'
        "branch_labels: str | Sequence[str] | None = None\n\n"
        "def upgrade() -> None:\n"
        '    op.add_column("quotation", sa.Column("notas"))\n'
    )

    aplicar_arreglo(migracion, destino="b")

    contenido = migracion.read_text()
    assert 'down_revision: str | Sequence[str] | None = "b"' in contenido
    assert 'revision: str = "c"' in contenido
    assert "branch_labels: str | Sequence[str] | None = None" in contenido
    assert 'op.add_column("quotation", sa.Column("notas"))' in contenido
    # El docstring conserva el `Revises:` original: es documentación histórica
    # del archivo, no lo que Alembic lee.
    assert "Revises: a" in contenido


def test_arreglar_acepta_comillas_simples(tmp_path):
    """El autogenerate ha emitido las dos formas; hay 8 archivos con cada una."""
    migracion = tmp_path / "c_x.py"
    migracion.write_text("down_revision: str | Sequence[str] | None = 'a'\n")

    aplicar_arreglo(migracion, destino="b")

    assert (
        migracion.read_text().strip()
        == 'down_revision: str | Sequence[str] | None = "b"'
    )


def test_arreglar_falla_si_no_encuentra_la_linea(tmp_path):
    migracion = tmp_path / "c_x.py"
    migracion.write_text("revision: str = 'c'\n")

    with pytest.raises(ValueError, match="down_revision"):
        aplicar_arreglo(migracion, destino="b")
