"""
Tests para TextBuilder — simetría de formato entre licitacion y proveedor.

Invariante central: build_from_licitacion y build_from_proveedor deben producir
texto con la misma estructura de secciones. Si el formato diverge, la similitud
coseno entre vectores de licitacion y proveedor pierde significado semántico.

Estructura esperada (ambos lados):
  {concepto_principal}. {descripcion_libre}. {Etiqueta_A}: {lista_A}. {Etiqueta_B}: {lista_B}.
"""

from datetime import datetime, timezone

import pytest

from app.application.services.text_builder import TextBuilder
from app.domain.entities.licitacion import ItemLicitacion, Licitacion
from app.domain.entities.supplier import Supplier

FECHA_CIERRE = datetime(2026, 7, 1, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def builder() -> TextBuilder:
    return TextBuilder()


@pytest.fixture
def licitacion_completa() -> Licitacion:
    return Licitacion(
        codigo_externo="1234-5-LQ24",
        nombre="Adquisición de equipos computacionales",
        descripcion="Compra de notebooks y monitores para colegios de la región",
        organismo_nombre="Ministerio de Educación",
        fecha_cierre=FECHA_CIERRE,
        region="Metropolitana",
        estado="activa",
        categorias=["Tecnología", "Computación"],
        items=[
            ItemLicitacion(nombre="Notebook", descripcion="Intel i7 16GB RAM"),
            ItemLicitacion(nombre="Monitor", descripcion="27 pulgadas Full HD"),
        ],
    )


@pytest.fixture
def licitacion_minima() -> Licitacion:
    return Licitacion(
        codigo_externo="9999-1-LE24",
        nombre="Servicio de mantención de jardines",
        organismo_nombre="Municipalidad de Santiago",
        fecha_cierre=FECHA_CIERRE,
        region="Metropolitana",
        estado="activa",
    )


@pytest.fixture
def proveedor_completo() -> Supplier:
    return Supplier(
        rut="12345678-5",
        legal_name="TechSolutions SpA",
        sectors=["Tecnología de la Información", "Consultoría"],
        description="Empresa especializada en soluciones TI para el sector público",
        keywords=["redes", "servidores", "soporte técnico"],
        certifications=["ISO 9001", "Microsoft Partner"],
    )


@pytest.fixture
def proveedor_minimo() -> Supplier:
    return Supplier(
        rut="12.345.678-5",
        legal_name="Servicios Generales Ltda",
    )


# ---------------------------------------------------------------------------
# Tests de build_from_licitacion
# ---------------------------------------------------------------------------


class TestBuildFromLicitacion:
    def test_contiene_nombre(
        self, builder: TextBuilder, licitacion_completa: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_completa)
        assert "Adquisición de equipos computacionales" in texto

    def test_contiene_descripcion_cuando_existe(
        self, builder: TextBuilder, licitacion_completa: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_completa)
        assert "Compra de notebooks y monitores" in texto

    def test_contiene_categorias_cuando_existen(
        self, builder: TextBuilder, licitacion_completa: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_completa)
        assert "Tecnología" in texto
        assert "Computación" in texto

    def test_contiene_items_cuando_existen(
        self, builder: TextBuilder, licitacion_completa: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_completa)
        assert "Notebook" in texto
        assert "Monitor" in texto

    def test_no_produce_segmentos_vacios(
        self, builder: TextBuilder, licitacion_completa: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_completa)
        assert ". ." not in texto
        assert not texto.startswith(". ")

    def test_licitacion_minima_no_es_vacia(
        self, builder: TextBuilder, licitacion_minima: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_minima)
        assert len(texto.strip()) > 0

    def test_omite_descripcion_cuando_es_none(
        self, builder: TextBuilder, licitacion_minima: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_minima)
        assert "None" not in texto

    def test_omite_categorias_cuando_lista_vacia(
        self, builder: TextBuilder, licitacion_minima: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_minima)
        assert "Categorías:" not in texto

    def test_omite_items_cuando_lista_vacia(
        self, builder: TextBuilder, licitacion_minima: Licitacion
    ) -> None:
        texto = builder.build_from_licitacion(licitacion_minima)
        assert "Items:" not in texto

    def test_item_sin_descripcion_incluye_solo_nombre(
        self, builder: TextBuilder
    ) -> None:
        licitacion = Licitacion(
            codigo_externo="0001-1-LQ24",
            nombre="Servicio de limpieza",
            organismo_nombre="Hospital Base",
            fecha_cierre=FECHA_CIERRE,
            region="Los Lagos",
            estado="activa",
            items=[ItemLicitacion(nombre="Servicio mensual")],
        )
        texto = builder.build_from_licitacion(licitacion)
        assert "Servicio mensual" in texto
        assert "None" not in texto


# ---------------------------------------------------------------------------
# Tests de build_from_proveedor
# ---------------------------------------------------------------------------


class TestBuildFromProveedor:
    def test_contiene_rubros_cuando_existen(
        self, builder: TextBuilder, proveedor_completo: Supplier
    ) -> None:
        texto = builder.build_from_supplier(proveedor_completo)
        assert "Tecnología de la Información" in texto

    def test_contiene_descripcion_libre_cuando_existe(
        self, builder: TextBuilder, proveedor_completo: Supplier
    ) -> None:
        texto = builder.build_from_supplier(proveedor_completo)
        assert "soluciones TI para el sector público" in texto

    def test_contiene_palabras_clave_cuando_existen(
        self, builder: TextBuilder, proveedor_completo: Supplier
    ) -> None:
        texto = builder.build_from_supplier(proveedor_completo)
        assert "redes" in texto
        assert "servidores" in texto

    def test_contiene_certificaciones_cuando_existen(
        self, builder: TextBuilder, proveedor_completo: Supplier
    ) -> None:
        texto = builder.build_from_supplier(proveedor_completo)
        assert "ISO 9001" in texto

    def test_no_produce_segmentos_vacios(
        self, builder: TextBuilder, proveedor_completo: Supplier
    ) -> None:
        texto = builder.build_from_supplier(proveedor_completo)
        assert ". ." not in texto
        assert not texto.startswith(". ")

    def test_proveedor_minimo_no_es_vacio(
        self, builder: TextBuilder, proveedor_minimo: Supplier
    ) -> None:
        texto = builder.build_from_supplier(proveedor_minimo)
        assert len(texto.strip()) > 0

    def test_omite_campos_none(
        self, builder: TextBuilder, proveedor_minimo: Supplier
    ) -> None:
        texto = builder.build_from_supplier(proveedor_minimo)
        assert "None" not in texto
        assert "Capacidades:" not in texto
        assert "Certificaciones:" not in texto


# ---------------------------------------------------------------------------
# Tests de simetría — el más importante
# ---------------------------------------------------------------------------


class TestSimetriaFormato:
    def test_ambos_terminan_con_punto(
        self,
        builder: TextBuilder,
        licitacion_completa: Licitacion,
        proveedor_completo: Supplier,
    ) -> None:
        assert builder.build_from_licitacion(licitacion_completa).endswith(".")
        assert builder.build_from_supplier(proveedor_completo).endswith(".")

    def test_ambos_usan_punto_espacio_como_separador(
        self,
        builder: TextBuilder,
        licitacion_completa: Licitacion,
        proveedor_completo: Supplier,
    ) -> None:
        texto_lic = builder.build_from_licitacion(licitacion_completa)
        texto_prov = builder.build_from_supplier(proveedor_completo)
        # Ambos deben tener al menos un separador ". " cuando hay múltiples secciones
        assert ". " in texto_lic
        assert ". " in texto_prov

    def test_ambos_producen_misma_cantidad_de_secciones_con_datos_completos(
        self,
        builder: TextBuilder,
        licitacion_completa: Licitacion,
        proveedor_completo: Supplier,
    ) -> None:
        """
        Con datos completos, ambos lados deben tener 4 secciones:
        [concepto_principal, descripcion, etiqueta_A, etiqueta_B]
        """
        texto_lic = builder.build_from_licitacion(licitacion_completa)
        texto_prov = builder.build_from_supplier(proveedor_completo)

        secciones_lic = [s for s in texto_lic.rstrip(".").split(". ") if s]
        secciones_prov = [s for s in texto_prov.rstrip(".").split(". ") if s]

        assert len(secciones_lic) == len(secciones_prov) == 4

    def test_mismo_numero_secciones_con_datos_minimos(
        self,
        builder: TextBuilder,
        licitacion_minima: Licitacion,
        proveedor_minimo: Supplier,
    ) -> None:
        """Con datos mínimos, ambos lados producen exactamente 1 sección."""
        texto_lic = builder.build_from_licitacion(licitacion_minima)
        texto_prov = builder.build_from_supplier(proveedor_minimo)

        secciones_lic = [s for s in texto_lic.rstrip(".").split(". ") if s]
        secciones_prov = [s for s in texto_prov.rstrip(".").split(". ") if s]

        assert len(secciones_lic) == len(secciones_prov) == 1
