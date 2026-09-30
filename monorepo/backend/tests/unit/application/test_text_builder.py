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


# ---------------------------------------------------------------------------
# build_item_texts
# ---------------------------------------------------------------------------


def test_build_item_texts_vacio() -> None:
    """Lista vacía devuelve lista vacía."""
    t = TextBuilder()
    result = t.build_item_texts([])
    assert result == []


def test_build_item_texts_solo_nombre() -> None:
    """Item sin descripción: solo nombre."""
    t = TextBuilder()
    items = [FakeItem("Cemento")]
    result = t.build_item_texts(items)
    assert result == ["Cemento"]


def test_build_item_texts_nombre_y_descripcion() -> None:
    """Item con descripción: 'nombre: descripción[:200]'."""
    t = TextBuilder()
    items = [FakeItem("Cemento", description="Portland tipo V")]
    result = t.build_item_texts(items)
    assert result == ["Cemento: Portland tipo V"]


def test_build_item_texts_trunca_descripcion_en_200_caracteres() -> None:
    """Descripción se trunca a 200 caracteres."""
    t = TextBuilder()
    long_desc = "x" * 250
    items = [FakeItem("Item", description=long_desc)]
    result = t.build_item_texts(items)
    assert result[0] == f"Item: {'x' * 200}"


def test_build_item_texts_strip_descripcion() -> None:
    """Descripción se stripea antes de truncar."""
    t = TextBuilder()
    items = [FakeItem("Item", description="  desc  ")]
    result = t.build_item_texts(items)
    assert result == ["Item: desc"]


def test_build_item_texts_omite_nombre_vacio() -> None:
    """Partidas con nombre vacío se omiten."""
    t = TextBuilder()
    items = [FakeItem(""), FakeItem("Válido"), FakeItem("")]
    result = t.build_item_texts(items)
    assert result == ["Válido"]


def test_build_item_texts_deduplica() -> None:
    """Textos duplicados se deduplicamos conservando orden."""
    t = TextBuilder()
    items = [
        FakeItem("A", description="desc1"),
        FakeItem("B"),
        FakeItem("A", description="desc1"),
    ]
    result = t.build_item_texts(items)
    assert result == ["A: desc1", "B"]


# ---------------------------------------------------------------------------
# build_reranker_query
# ---------------------------------------------------------------------------


def test_build_reranker_query_con_sectores_y_keywords() -> None:
    """Formato exacto: 'Rubro: <sectores>. Productos: <keywords>.'"""
    from app.domain.entities.supplier import Supplier

    t = TextBuilder()
    supplier = Supplier(
        rut="11111111-1",
        legal_name="Empresa Test",
        sectors=["Construcción", "Ingeniería"],
        keywords=["Excavación", "Hormigón"],
    )
    result = t.build_reranker_query(supplier)
    assert result == "Rubro: Construcción, Ingeniería. Productos: Excavación, Hormigón."


def test_build_reranker_query_sin_sectores_usa_legal_name() -> None:
    """Sin sectores, usa legal_name en lugar de la lista."""
    from app.domain.entities.supplier import Supplier

    t = TextBuilder()
    supplier = Supplier(
        rut="11111111-1",
        legal_name="Mi Empresa",
        sectors=None,
        keywords=["Excavación"],
    )
    result = t.build_reranker_query(supplier)
    assert result == "Rubro: Mi Empresa. Productos: Excavación."


def test_build_reranker_query_sin_keywords_usa_descripcion() -> None:
    """Sin keywords, usa description después de 'Productos: '."""
    from app.domain.entities.supplier import Supplier

    t = TextBuilder()
    supplier = Supplier(
        rut="11111111-1",
        legal_name="Empresa",
        sectors=["Construcción"],
        description="Somos especialistas",
        keywords=None,
    )
    result = t.build_reranker_query(supplier)
    assert result == "Rubro: Construcción. Productos: Somos especialistas."


def test_build_reranker_query_sin_keywords_ni_descripcion_usa_legal_name() -> None:
    """Sin keywords y sin descripción, usa legal_name."""
    from app.domain.entities.supplier import Supplier

    t = TextBuilder()
    supplier = Supplier(
        rut="11111111-1",
        legal_name="Mi Empresa",
        sectors=["Construcción"],
        keywords=None,
        description=None,
    )
    result = t.build_reranker_query(supplier)
    assert result == "Rubro: Construcción. Productos: Mi Empresa."


# ---------------------------------------------------------------------------
# build_keyword_texts
# ---------------------------------------------------------------------------


def _proveedor(**campos):
    from app.domain.entities.supplier import Supplier

    return Supplier(rut="11111111-1", legal_name="Mi Empresa", **campos)


def test_build_keyword_texts_devuelve_las_keywords_en_orden() -> None:
    supplier = _proveedor(keywords=["cemento", "fierro", "hormigón"])

    assert TextBuilder().build_keyword_texts(supplier) == [
        "cemento",
        "fierro",
        "hormigón",
    ]


def test_build_keyword_texts_quita_espacios_y_omite_las_vacias() -> None:
    supplier = _proveedor(keywords=["  cemento ", "", "   ", "fierro"])

    assert TextBuilder().build_keyword_texts(supplier) == ["cemento", "fierro"]


def test_build_keyword_texts_sin_keywords_usa_la_descripcion() -> None:
    supplier = _proveedor(keywords=[], description="  Venta de materiales  ")

    assert TextBuilder().build_keyword_texts(supplier) == ["Venta de materiales"]


def test_build_keyword_texts_con_keywords_en_blanco_usa_la_descripcion() -> None:
    supplier = _proveedor(keywords=["", "  "], description="Venta de materiales")

    assert TextBuilder().build_keyword_texts(supplier) == ["Venta de materiales"]


def test_build_keyword_texts_sin_keywords_ni_descripcion_usa_la_razon_social() -> None:
    supplier = _proveedor(keywords=None, description=None)

    assert TextBuilder().build_keyword_texts(supplier) == ["Mi Empresa"]


def test_build_keyword_texts_con_descripcion_en_blanco_usa_la_razon_social() -> None:
    supplier = _proveedor(keywords=None, description="   ")

    assert TextBuilder().build_keyword_texts(supplier) == ["Mi Empresa"]
