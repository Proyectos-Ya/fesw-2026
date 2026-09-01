"""Catálogo de provincias/comunas de Chile, para poblar selects en el frontend.

No hay tabla de "estado" que mostrar: se sirve directo desde las constantes de
`app/shared/comunas.py`, que ya son la fuente de verdad usada para sembrar la
base y para la heurística de resolución de comuna.
"""

from pydantic import BaseModel


class ProvinceOption(BaseModel):
    id: int
    name: str
    region_name: str


class CommuneOption(BaseModel):
    id: int
    name: str
    province_name: str


class LocationCatalogResponse(BaseModel):
    provinces: list[ProvinceOption]
    communes: list[CommuneOption]
