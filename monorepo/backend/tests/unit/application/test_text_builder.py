"""Tests unitarios de TextBuilder — simetría semántica entre proveedor y licitación."""

from dataclasses import dataclass

from app.application.services.text_builder import TextBuilder

# ---------------------------------------------------------------------------
# Helpers: objetos mínimos compatibles por duck typing
# ---------------------------------------------------------------------------


@dataclass
class FakeTender:
    name: str
    description: str | None = None


@dataclass
class FakeItem:
    name: str
    description: str | None = None


# ---------------------------------------------------------------------------
# build_from_tender
# ---------------------------------------------------------------------------


def test_incluye_nombre_licitacion() -> None:
    t = TextBuilder()
    result = t.build_from_tender(FakeTender("Construcción de sede"), [])
    assert "Construcción de sede" in result


def test_incluye_descripcion_si_existe() -> None:
    t = TextBuilder()
    result = t.build_from_tender(
        FakeTender("Título", description="Se requiere obra civil"), []
    )
    assert "Se requiere obra civil" in result


def test_omite_descripcion_si_es_none() -> None:
    t = TextBuilder()
    result = t.build_from_tender(FakeTender("Título", description=None), [])
    assert "None" not in result


def test_incluye_nombre_de_items() -> None:
    t = TextBuilder()
    items = [FakeItem("Mano de obra"), FakeItem("Materiales hormigón")]
    result = t.build_from_tender(FakeTender("Título"), items)
    assert "Mano de obra" in result
    assert "Materiales hormigón" in result


def test_incluye_descripcion_de_item_si_existe() -> None:
    t = TextBuilder()
    items = [FakeItem("Cemento", description="Portland tipo V")]
    result = t.build_from_tender(FakeTender("Título"), items)
    assert "Portland tipo V" in result


def test_omite_descripcion_de_item_si_es_none() -> None:
    t = TextBuilder()
    items = [FakeItem("Cemento", description=None)]
    result = t.build_from_tender(FakeTender("Título"), items)
    assert "None" not in result


def test_sin_items_no_aparece_prefijo_items() -> None:
    t = TextBuilder()
    result = t.build_from_tender(FakeTender("Título"), [])
    assert "Items:" not in result


def test_no_incluye_informacion_del_comprador() -> None:
    """El texto de la licitación no debe incluir datos del organismo comprador."""
    t = TextBuilder()
    result = t.build_from_tender(FakeTender("Título"), [])
    assert "Municipalidad" not in result
    assert "Comprador" not in result
    assert "buyer" not in result.lower()
