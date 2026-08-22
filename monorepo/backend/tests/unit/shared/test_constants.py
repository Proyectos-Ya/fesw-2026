"""La numeración de regiones tiene que ser una sola en todo el sistema.

El bug que estos tests previenen: `seeder.py` numeraba las regiones de norte a
sur y la ingesta usaba la numeración administrativa. No coincidían en **ninguna**
región, así que una licitación de la Metropolitana (id 13) quedaba etiquetada
como "Los Ríos", que es el 13 en la otra numeración.

Los ids son los que entrega Mercado Público en `institucion.region`, verificados
contra la API el 21 de agosto de 2026 sobre las 16 regiones.
"""

from app.shared.constants import (
    CHILE_REGIONS,
    UNKNOWN_REGION_ID,
    region_id_by_name,
)


class TestChileRegions:
    def test_estan_las_dieciseis_regiones(self):
        assert len(CHILE_REGIONS) == 16

    def test_los_ids_van_del_1_al_16(self):
        assert sorted(CHILE_REGIONS) == list(range(1, 17))

    def test_los_ids_clave_coinciden_con_la_api(self):
        # Las cuatro que difieren más entre ambas numeraciones: si alguien
        # reintroduce el orden geográfico, estas son las primeras en romperse.
        assert CHILE_REGIONS[13] == "Metropolitana de Santiago"
        assert CHILE_REGIONS[15] == "Arica y Parinacota"
        assert CHILE_REGIONS[16] == "Ñuble"
        assert CHILE_REGIONS[1] == "Tarapacá"

    def test_los_nombres_son_unicos(self):
        assert len(set(CHILE_REGIONS.values())) == len(CHILE_REGIONS)

    def test_los_nombres_vienen_limpios(self):
        # La API los entrega con espacios sobrantes ("Región de Tarapacá  ").
        for nombre in CHILE_REGIONS.values():
            assert nombre, "ningún nombre puede ser vacío"
            assert nombre == nombre.strip(), f"{nombre!r} tiene espacios sobrantes"

    def test_el_id_de_region_desconocida_no_pisa_una_real(self):
        assert UNKNOWN_REGION_ID not in CHILE_REGIONS


class TestRegionIdByName:
    """El frontend filtra por nombre de región; el criterio de búsqueda usa ids.

    La traducción ocurre en el borde HTTP. Es tolerante a mayúsculas y espacios
    porque los nombres viajan en una query string escrita por otro equipo.
    """

    def test_resuelve_un_nombre_exacto(self):
        assert region_id_by_name("Metropolitana de Santiago") == 13

    def test_ignora_mayusculas_y_espacios(self):
        assert region_id_by_name("  metropolitana DE santiago ") == 13

    def test_devuelve_none_si_no_existe(self):
        assert region_id_by_name("Región Inventada") is None

    def test_devuelve_none_con_texto_vacio(self):
        assert region_id_by_name("   ") is None

    def test_resuelve_todas_las_regiones_de_la_constante(self):
        for r_id, nombre in CHILE_REGIONS.items():
            assert region_id_by_name(nombre) == r_id
