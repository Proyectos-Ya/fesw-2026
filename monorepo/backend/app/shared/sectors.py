"""Rubros del producto: el vocabulario cerrado de `Supplier.sectors`.

Son los rubros de primer nivel del catálogo ONU que usa Mercado Público, copiados
tal cual (con sus mayúsculas y tildes) de `Listado_rubros_ONU.xlsx`, de Datos
Abiertos de ChileCompra:
https://transparenciachc.blob.core.windows.net/oc-da/Listado_rubros_ONU.xlsx
Consultado el 2026-10-26 (plan 311, CA 1).

* 58 rubros de la columna `Nivel1`. Se excluyen `x` y `eCommerce`.
* Cada rubro es un segmento UNSPSC (los dos primeros dígitos de `CodigoProducto`).
  Se agrupan por los rangos de segmentos de UNSPSC: materias primas (10-15),
  maquinaria y equipamiento industrial (20-27), componentes y suministros (30-41),
  productos de uso final (42-60) y servicios (70-94). Dentro de cada grupo van en
  orden de segmento.
* Dos excepciones. Tecnologías de la información (segmento 43) va en Servicios,
  porque ChileCompra lo marca como servicio. Obras, Obras MINVU y Consultoria son
  categorías propias de ChileCompra (sus códigos empiezan con 10, pero no son
  materias primas) y van en un grupo aparte.
* El catálogo tiene 362 rubros de segundo nivel. No se usan.

`frontend/src/features/company-profile/data/sectors.ts` repite los mismos grupos,
que son los que el usuario ve en el wizard. `tests/unit/test_sectors_frontend_parity.py`
falla si las dos copias no coinciden.

El diccionario de actividades y el clasificador de rubro
(`app/application/services/company_profiling/`) dependen de esta lista, y un test
exige que todo rubro que sugieran exista acá.
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class SectorGroup:
    title: str
    sectors: tuple[str, ...]


SECTOR_GROUPS: tuple[SectorGroup, ...] = (
    SectorGroup(
        title="Materias primas",
        sectors=(
            "Artículos para plantas y animales",
            "Productos derivados de minerales, plantas y animales",
            "Productos químicos industriales",
            "Resinas, cauchos, espumas y elastómeros",
            "Productos de papel",
            "Combustibles, lubricantes y anticorrosivos",
        ),
    ),
    SectorGroup(
        title="Maquinaria y equipamiento industrial",
        sectors=(
            "Maquinaria para minería y perforación",
            "Maquinaria para agricultura, pesca y silvicultura",
            "Maquinaria para construcción y edificación",
            "Maquinaria para fabricación y transformación industrial",
            "Equipamiento para manejo y estiba de materiales",
            "Vehículos y equipamiento en general",
            "Maquinaria para generación y distribución de energía",
            "Herramientas y maquinaria en general",
        ),
    ),
    SectorGroup(
        title="Componentes y suministros",
        sectors=(
            "Artículos para estructuras, obras y construcciones",
            "Artículos de fabricación y producción",
            "Artículos de electrónica",
            "Artículos eléctricos y de iluminación",
            "Equipamiento para el acondicionamiento, distribución y filtrado de fluidos",
            "Equipamiento para laboratorios",
        ),
    ),
    SectorGroup(
        title="Productos de uso final",
        sectors=(
            "Equipamiento y suministros médicos",
            "Equipos, accesorios y suministros de oficina",
            "Equipos y suministros de imprenta, fotográficos y audiovisuales",
            "Equipos y suministros de defensa, orden público, protección y seguridad",
            "Equipos y suministros de limpieza",
            "Maquinarias, equipos y suministros para la industria de servicios",
            "Equipos, suministros y accesorios deportivos y recreativos",
            "Alimentos, bebidas y tabaco",
            "Medicamentos y productos farmacéuticos",
            "Muebles, accesorios, electrodomésticos y productos electrónicos",
            "Ropa, maletas y productos de aseo personal",
            "Productos para relojería, joyería y gemas",
            "Productos impresos y publicaciones",
            "Muebles y mobiliario",
            "Instrumentos musicales, juegos, juguetes, artesanías y materiales educativos",
        ),
    ),
    SectorGroup(
        title="Servicios",
        sectors=(
            "Tecnologías de la información, telecomunicaciones y radiodifusión",
            "Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",
            "Servicios de perforación de minería, petróleo y gas",
            "Servicios de construcción y mantenimiento",
            "Servicios de producción y fabricación industrial",
            "Servicios de limpieza industrial",
            "Servicios medioambientales",
            "Servicios de transporte, almacenaje y correo",
            "Servicios profesionales, administrativos y consultorías de gestión empresarial",
            "Servicios basados en ingeniería, ciencias sociales y tecnología de la información",
            "Servicios editoriales, de diseño, publicidad, gráficos y artistas",
            "Servicios básicos y de información pública",
            "Servicios financieros, pensiones y seguros",
            "Salud, servicios sanitarios y alimentación",
            "Educación, formación, entrenamiento y capacitación",
            "Servicios de Viajes, alimentación, alojamiento y entretenimiento",
            "Servicios de cuidado personal y domésticos",
            "Servicios de defensa nacional, orden público y seguridad",
            "Organizaciones y consultorías políticas, demográficas, económicas, sociales y de administración pública",
            "Organizaciones sociales, laborales y clubes",
        ),
    ),
    SectorGroup(
        title="Obras y consultorías de ChileCompra",
        sectors=(
            "Consultoria",
            "Obras",
            "Obras MINVU",
        ),
    ),
)

PRODUCT_SECTORS: tuple[str, ...] = tuple(
    sector for group in SECTOR_GROUPS for sector in group.sectors
)

# Palabras que los nombres del catálogo repiten entre rubros ("Servicios de...",
# "Equipos y suministros de...") y que aparecen en casi toda licitación. Si contaran
# para el peso de rubro, casi toda empresa lo sumaría contra casi toda licitación.
# Van en minúsculas y sin tildes, como las devuelve `fold`.
GENERIC_SECTOR_WORDS: frozenset[str] = frozenset(
    {
        "servicios",
        "servicio",
        "equipos",
        "equipamiento",
        "suministros",
        "articulos",
        "accesorios",
        "productos",
        "relacionados",
        "industria",
        "industrial",
        "industriales",
        "general",
        "para",
        "sobre",
        "entre",
        "desde",
        "hasta",
    }
)


def fold(text: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres de rubro con texto libre."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def significant_terms(sector: str) -> list[str]:
    """Palabras del rubro que sirven para reconocerlo en una licitación.

    Sin puntuación ni tildes, de 4 letras o más y fuera de `GENERIC_SECTOR_WORDS`,
    en el orden del nombre y sin repetir.
    """
    terms: list[str] = []
    for word in re.findall(r"\w+", fold(sector)):
        if len(word) >= 4 and word not in GENERIC_SECTOR_WORDS and word not in terms:
            terms.append(word)
    return terms
