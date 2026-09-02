"""Catálogo de provincias/comunas para poblar selects en el frontend.

No toca la base de datos: arma la respuesta directo desde `CHILE_PROVINCIAS`/
`CHILE_COMUNAS` (`app/shared/comunas.py`), la misma fuente de verdad que ya usa
el seed. Sirve para que el buscador manual (HdU 07) pueda ofrecer las opciones
de provincia/comuna sin depender de qué llegó en la página actual de
resultados (ver PENDIENTES.md, sección de filtro de provincia/comuna).
"""

from app.infrastructure.routers.catalog import build_location_catalog
from app.shared.comunas import CHILE_COMUNAS, CHILE_PROVINCIAS


class TestBuildLocationCatalog:
    def test_trae_las_56_provincias(self):
        catalog = build_location_catalog()
        assert len(catalog.provinces) == 56

    def test_trae_las_346_comunas(self):
        catalog = build_location_catalog()
        assert len(catalog.communes) == 346

    def test_cada_provincia_tiene_id_nombre_y_region(self):
        catalog = build_location_catalog()
        by_id = {
            (name, region): pid for pid, (name, region) in CHILE_PROVINCIAS.items()
        }
        for provincia in catalog.provinces:
            assert by_id[(provincia.name, provincia.region_name)] == provincia.id

    def test_cada_comuna_tiene_id_nombre_y_provincia(self):
        catalog = build_location_catalog()
        by_id = {(name, prov): cid for cid, (name, prov) in CHILE_COMUNAS.items()}
        for comuna in catalog.communes:
            assert by_id[(comuna.name, comuna.province_name)] == comuna.id

    def test_toda_comuna_referencia_una_provincia_que_esta_en_el_catalogo(self):
        catalog = build_location_catalog()
        nombres_provincia = {p.name for p in catalog.provinces}
        for comuna in catalog.communes:
            assert comuna.province_name in nombres_provincia
