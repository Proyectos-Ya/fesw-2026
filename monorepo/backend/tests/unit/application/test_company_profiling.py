"""Diccionario de actividades, clasificador de rubro y catálogo del SII.

Portados del spike 1. Los casos salen de lo que el spike encontró con datos
reales: la empresa de RUT 76.668.304-5 (433000 + 479100 + 952200) y los dos
falsos positivos que se corrigieron comparando contra el catálogo completo.
"""

from app.application.services.company_profiling import (
    activity_catalog,
    activity_dictionary,
    sector_classifier,
)
from app.shared.sectors import PRODUCT_SECTORS


class TestVocabularioCerrado:
    def test_todo_sector_del_diccionario_existe_en_el_producto(self):
        """Un rubro mal escrito no falla: queda sin marcar en el wizard."""
        for code, entry in activity_dictionary.ACTIVITY_DICTIONARY.items():
            for sector in entry.sectors:
                assert sector in PRODUCT_SECTORS, (code, sector)

    def test_todo_sector_del_clasificador_existe_en_el_producto(self):
        for sector in sector_classifier.all_sectors():
            assert sector in PRODUCT_SECTORS, sector


class TestCatalogoSii:
    def test_trae_los_674_codigos_del_catalogo_oficial(self):
        assert activity_catalog.catalog_size() == 674

    def test_devuelve_la_glosa_oficial_de_un_codigo(self):
        assert (
            activity_catalog.official_description(433000)
            == "TERMINACIÓN Y ACABADO DE EDIFICIOS"
        )

    def test_codigo_inexistente_devuelve_cadena_vacia(self):
        assert activity_catalog.official_description(999999) == ""


class TestDiccionario:
    CODIGOS_EMPRESA_REAL = [433000, 479100, 952200]

    def test_une_los_rubros_de_todas_las_actividades(self):
        assert activity_dictionary.curated_sectors(self.CODIGOS_EMPRESA_REAL) == [
            "Obras de Construcción e Infraestructura",
            "Equipos e Insumos Industriales",
            "Mantención y Reparación",
        ]

    def test_une_las_palabras_clave_sin_repetir(self):
        keywords = activity_dictionary.keywords_for(self.CODIGOS_EMPRESA_REAL)
        assert keywords[:2] == ["pintura", "revestimiento"]
        assert "servicio técnico" in keywords
        assert len(keywords) == len(set(keywords))

    def test_codigo_no_curado_no_aporta_palabras_clave(self):
        """Decisión del spike: la glosa es lenguaje tributario, no de compra."""
        assert activity_dictionary.keywords_for([11101]) == []

    def test_actividad_fuera_de_alcance_no_aporta_rubro(self):
        assert activity_dictionary.is_out_of_scope(970000)
        assert activity_dictionary.curated_sectors([970000]) == []


class TestClasificadorDeRubro:
    def test_reconoce_el_rubro_por_la_glosa(self):
        assert sector_classifier.sectors_from_description(
            "REPARACIÓN DE APARATOS DE USO DOMÉSTICO"
        ) == ("Mantención y Reparación",)

    def test_acumula_varios_rubros(self):
        sectores = sector_classifier.sectors_from_description(
            "REPARACIÓN Y MANTENCIÓN DE SOFTWARE"
        )
        assert "Mantención y Reparación" in sectores
        assert "Desarrollo de Software" in sectores

    def test_caza_y_pesca_no_es_alimentacion(self):
        assert "Alimentación y Gastronomía" not in sector_classifier.sectors_from_description(
            "VENTA AL POR MENOR DE ARTÍCULOS DE CAZA Y PESCA"
        )

    def test_aparatos_electricos_no_es_energia(self):
        assert "Energía y Electricidad" not in sector_classifier.sectors_from_description(
            "VENTA AL POR MENOR DE APARATOS ELÉCTRICOS"
        )

    def test_el_comodin_de_comercio_solo_aplica_sin_otra_coincidencia(self):
        assert sector_classifier.sectors_from_description("VENTA AL POR MAYOR DE TELAS") == (
            "Equipos e Insumos Industriales",
        )
        assert sector_classifier.sectors_from_description(
            "VENTA DE SERVICIOS DE ASEO"
        ) == ("Limpieza y Aseo Industrial",)

    def test_glosa_sin_coincidencias_no_fuerza_un_rubro(self):
        assert sector_classifier.sectors_from_description("ACTIVIDADES DE ASOCIACIONES") == ()
