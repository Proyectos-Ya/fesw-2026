"""Rubros del producto: el vocabulario cerrado de `Supplier.sectors`.

Son los rubros de primer nivel del catálogo ONU que usa Mercado Público, copiados
tal cual (con sus mayúsculas y tildes) de `Listado_rubros_ONU.xlsx`, de Datos
Abiertos de ChileCompra:
https://transparenciachc.blob.core.windows.net/oc-da/Listado_rubros_ONU.xlsx
Consultado el 2026-10-26 (plan 311, CA 1).

* 58 rubros de la columna `Nivel1`, agrupados por la columna `Tipo`: 19 de
  Servicios, 35 de Bienes y 4 de tipo `SinInfo`, que acá se llaman "Obras y otros".
  Se excluyen `x` y `eCommerce`, que también vienen como `SinInfo`.
* El catálogo tiene 362 rubros de segundo nivel. No se usan.

`frontend/src/features/company-profile/data/sectors.ts` repite los mismos grupos,
que son los que el usuario ve en el wizard. `tests/unit/test_sectors_frontend_parity.py`
falla si las dos copias no coinciden.

El diccionario de actividades y el clasificador de rubro
(`app/application/services/company_profiling/`) dependen de esta lista, y un test
exige que todo rubro que sugieran exista acá.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SectorGroup:
    title: str
    sectors: tuple[str, ...]


SECTOR_GROUPS: tuple[SectorGroup, ...] = (
    SectorGroup(
        title="Servicios",
        sectors=(
            "Consultoria",
            "Educación, formación, entrenamiento y capacitación",
            "Organizaciones sociales, laborales y clubes",
            "Salud, servicios sanitarios y alimentación",
            "Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",
            "Servicios basados en ingeniería, ciencias sociales y tecnología de la información",
            "Servicios básicos y de información pública",
            "Servicios de Viajes, alimentación, alojamiento y entretenimiento",
            "Servicios de cuidado personal y domésticos",
            "Servicios de defensa nacional, orden público y seguridad",
            "Servicios de limpieza industrial",
            "Servicios de perforación de minería, petróleo y gas",
            "Servicios de producción y fabricación industrial",
            "Servicios de transporte, almacenaje y correo",
            "Servicios editoriales, de diseño, publicidad, gráficos y artistas",
            "Servicios financieros, pensiones y seguros",
            "Servicios medioambientales",
            "Servicios profesionales, administrativos y consultorías de gestión empresarial",
            "Tecnologías de la información, telecomunicaciones y radiodifusión",
        ),
    ),
    SectorGroup(
        title="Bienes",
        sectors=(
            "Alimentos, bebidas y tabaco",
            "Artículos de electrónica",
            "Artículos de fabricación y producción",
            "Artículos eléctricos y de iluminación",
            "Artículos para estructuras, obras y construcciones",
            "Artículos para plantas y animales",
            "Combustibles, lubricantes y anticorrosivos",
            "Equipamiento para el acondicionamiento, distribución y filtrado de fluidos",
            "Equipamiento para laboratorios",
            "Equipamiento para manejo y estiba de materiales",
            "Equipamiento y suministros médicos",
            "Equipos y suministros de defensa, orden público, protección y seguridad",
            "Equipos y suministros de imprenta, fotográficos y audiovisuales",
            "Equipos y suministros de limpieza",
            "Equipos, accesorios y suministros de oficina",
            "Equipos, suministros y accesorios deportivos y recreativos",
            "Herramientas y maquinaria en general",
            "Instrumentos musicales, juegos, juguetes, artesanías y materiales educativos",
            "Maquinaria para agricultura, pesca y silvicultura",
            "Maquinaria para construcción y edificación",
            "Maquinaria para fabricación y transformación industrial",
            "Maquinaria para generación y distribución de energía",
            "Maquinaria para minería y perforación",
            "Maquinarias, equipos y suministros para la industria de servicios",
            "Medicamentos y productos farmacéuticos",
            "Muebles y mobiliario",
            "Muebles, accesorios, electrodomésticos y productos electrónicos",
            "Productos de papel",
            "Productos derivados de minerales, plantas y animales",
            "Productos impresos y publicaciones",
            "Productos para relojería, joyería y gemas",
            "Productos químicos industriales",
            "Resinas, cauchos, espumas y elastómeros",
            "Ropa, maletas y productos de aseo personal",
            "Vehículos y equipamiento en general",
        ),
    ),
    SectorGroup(
        title="Obras y otros",
        sectors=(
            "Obras",
            "Obras MINVU",
            "Organizaciones y consultorías políticas, demográficas, económicas, sociales y de administración pública",
            "Servicios de construcción y mantenimiento",
        ),
    ),
)

PRODUCT_SECTORS: tuple[str, ...] = tuple(
    sector for group in SECTOR_GROUPS for sector in group.sectors
)
