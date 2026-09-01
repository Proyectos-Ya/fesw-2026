"""El dataset de comunas tiene que ser consistente consigo mismo y con `regions.py`.

Ninguna de las tres APIs de Mercado Público entrega comuna ni provincia
directamente (ver PENDIENTES.md 6.16/6.19); `CHILE_PROVINCIAS`/`CHILE_COMUNAS`
son la única fuente de verdad, cargada a mano desde un dataset público
verificado (16 regiones / 56 provincias / 346 comunas, sin cambios desde la
creación de la Región de Ñuble en 2018).
"""

from app.shared.comunas import CHILE_COMUNAS, CHILE_PROVINCIAS
from app.shared.regions import CHILE_REGIONS


class TestChileProvincias:
    def test_estan_las_56_provincias(self):
        assert len(CHILE_PROVINCIAS) == 56

    def test_los_nombres_de_provincia_son_unicos(self):
        nombres = [name for name, _region in CHILE_PROVINCIAS.values()]
        assert len(set(nombres)) == len(nombres)

    def test_toda_provincia_referencia_una_region_canonica(self):
        regiones_canonicas = set(CHILE_REGIONS.values())
        for provincia_id, (nombre, region_name) in CHILE_PROVINCIAS.items():
            assert region_name in regiones_canonicas, (
                f"provincia {provincia_id} ({nombre!r}) referencia una región "
                f"que no existe en CHILE_REGIONS: {region_name!r}"
            )

    def test_los_nombres_vienen_limpios(self):
        for nombre, region_name in CHILE_PROVINCIAS.values():
            assert nombre == nombre.strip() and nombre
            assert region_name == region_name.strip() and region_name


class TestChileComunas:
    def test_estan_las_346_comunas(self):
        assert len(CHILE_COMUNAS) == 346

    def test_los_nombres_de_comuna_son_unicos(self):
        nombres = [name for name, _prov in CHILE_COMUNAS.values()]
        assert len(set(nombres)) == len(nombres)

    def test_toda_comuna_referencia_una_provincia_existente(self):
        provincias_existentes = {name for name, _region in CHILE_PROVINCIAS.values()}
        for comuna_id, (nombre, provincia_name) in CHILE_COMUNAS.items():
            assert provincia_name in provincias_existentes, (
                f"comuna {comuna_id} ({nombre!r}) referencia una provincia que "
                f"no existe en CHILE_PROVINCIAS: {provincia_name!r}"
            )

    def test_los_nombres_vienen_limpios(self):
        for nombre, provincia_name in CHILE_COMUNAS.values():
            assert nombre == nombre.strip() and nombre
            assert provincia_name == provincia_name.strip() and provincia_name

    def test_cada_region_tiene_al_menos_una_comuna(self):
        provincia_a_region = {
            name: region for name, region in CHILE_PROVINCIAS.values()
        }
        regiones_con_comuna = {
            provincia_a_region[prov_name]
            for _nombre, prov_name in CHILE_COMUNAS.values()
        }
        assert regiones_con_comuna == set(CHILE_REGIONS.values())
