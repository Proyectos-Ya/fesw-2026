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
from app.shared.sectors import PRODUCT_SECTORS, SECTOR_GROUPS


class TestListaDeRubros:
    def test_son_los_58_rubros_de_primer_nivel_de_mercado_publico(self):
        assert len(PRODUCT_SECTORS) == 58
        assert len(set(PRODUCT_SECTORS)) == 58

    def test_se_agrupan_por_rangos_de_segmentos_unspsc(self):
        assert [group.title for group in SECTOR_GROUPS] == [
            "Materias primas",
            "Maquinaria y equipamiento industrial",
            "Componentes y suministros",
            "Productos de uso final",
            "Servicios",
            "Obras y consultorías de ChileCompra",
        ]
        assert [len(group.sectors) for group in SECTOR_GROUPS] == [6, 8, 6, 15, 20, 3]

    def test_tecnologias_de_la_informacion_va_en_servicios(self):
        """UNSPSC lo pone en productos (43), pero ChileCompra lo marca como servicio."""
        servicios = next(group for group in SECTOR_GROUPS if group.title == "Servicios")
        assert servicios.sectors[0] == (
            "Tecnologías de la información, telecomunicaciones y radiodifusión"
        )

    def test_la_lista_plana_sigue_el_orden_de_los_grupos(self):
        assert PRODUCT_SECTORS == tuple(s for group in SECTOR_GROUPS for s in group.sectors)


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
            "Servicios de construcción y mantenimiento",
            "Artículos de fabricación y producción",
            "Servicios de cuidado personal y domésticos",
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


class TestDiccionarioPorRubrosDeMayorGasto:
    """Los 53 códigos de los 15 rubros con más gasto público (plan 311, CA 2)."""

    CODIGOS = (
        421000, 422000, 429000, 431100, 431200, 432100, 432200, 432900,
        410010, 410020, 439000,
        861020, 862021, 862022, 862031, 266000, 325009,
        477201, 477202, 210000,
        562100, 562900, 107500, 107100,
        105000, 463019,
        381100, 381200, 382100, 382200, 383009,
        812909, 812901, 960100,
        782000, 783000,
        492120, 492190, 492250, 492290, 492230,
        711002, 711003, 722000, 732000, 691001,
        801003, 802000,
        13000, 21002, 24001, 24003, 773002,
    )  # fmt: skip

    def test_son_53_codigos_distintos(self):
        assert len(self.CODIGOS) == 53
        assert len(set(self.CODIGOS)) == 53

    def test_cada_codigo_tiene_uno_o_dos_rubros_y_de_tres_a_seis_palabras_clave(self):
        for code in self.CODIGOS:
            entry = activity_dictionary.ACTIVITY_DICTIONARY.get(code)
            assert entry is not None, code
            assert 1 <= len(entry.sectors) <= 2, code
            assert 3 <= len(entry.keywords) <= 6, code
            assert len(entry.keywords) == len(set(entry.keywords)), code

    def test_cada_codigo_aporta_palabras_clave(self):
        for code in self.CODIGOS:
            assert activity_dictionary.keywords_for([code]), code


class TestClasificadorDeRubro:
    def test_reconoce_el_rubro_por_la_glosa(self):
        assert sector_classifier.sectors_from_description(
            "CONSTRUCCIÓN DE EDIFICIOS PARA USO RESIDENCIAL"
        ) == ("Servicios de construcción y mantenimiento",)

    def test_reparacion_domestica_va_a_servicios_domesticos(self):
        assert sector_classifier.sectors_from_description(
            "REPARACIÓN DE APARATOS DE USO DOMÉSTICO"
        ) == ("Servicios de cuidado personal y domésticos",)

    def test_reparacion_de_vehiculos_no_es_construccion(self):
        """Apuntada a construcción, la empresa recibiría preguntas MOP/MINVU."""
        assert "Servicios de construcción y mantenimiento" not in (
            sector_classifier.sectors_from_description("REPARACIÓN DE VEHÍCULOS AUTOMOTORES")
        )

    def test_mantencion_de_software_es_ti_y_no_construccion(self):
        sectores = sector_classifier.sectors_from_description(
            "REPARACIÓN Y MANTENCIÓN DE SOFTWARE"
        )
        assert "Tecnologías de la información, telecomunicaciones y radiodifusión" in sectores
        assert "Servicios de construcción y mantenimiento" not in sectores

    def test_restaurante_es_servicio_y_cultivo_es_alimento(self):
        assert sector_classifier.sectors_from_description("ACTIVIDADES DE RESTAURANTES") == (
            "Servicios de Viajes, alimentación, alojamiento y entretenimiento",
        )
        assert sector_classifier.sectors_from_description("CULTIVO DE FRUTAS") == (
            "Alimentos, bebidas y tabaco",
        )

    def test_caza_y_pesca_no_es_alimentacion(self):
        sectores = sector_classifier.sectors_from_description(
            "VENTA AL POR MENOR DE ARTÍCULOS DE CAZA Y PESCA"
        )
        assert "Alimentos, bebidas y tabaco" not in sectores
        assert "Servicios de Viajes, alimentación, alojamiento y entretenimiento" not in sectores

    def test_aparatos_electricos_no_es_energia(self):
        assert "Maquinaria para generación y distribución de energía" not in (
            sector_classifier.sectors_from_description("VENTA AL POR MENOR DE APARATOS ELÉCTRICOS")
        )

    def test_el_comodin_de_comercio_solo_aplica_sin_otra_coincidencia(self):
        assert sector_classifier.sectors_from_description("VENTA AL POR MAYOR DE TELAS") == (
            "Artículos de fabricación y producción",
        )
        assert sector_classifier.sectors_from_description(
            "VENTA DE SERVICIOS DE ASEO"
        ) == ("Servicios de limpieza industrial",)

    def test_glosa_sin_coincidencias_no_fuerza_un_rubro(self):
        assert sector_classifier.sectors_from_description("ACTIVIDADES DE ASOCIACIONES") == ()
