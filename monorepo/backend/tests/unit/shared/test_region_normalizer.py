import pytest
from app.shared.region_normalizer import (
    normalize_region_name,
    are_regions_matching,
    get_canonical_region_name,
)


def test_normalize_region_name_various_formats() -> None:
    """Verifica que diferentes variantes textuales de una región se normalicen a su ID único (1-16)."""
    # Región Metropolitana (13)
    assert normalize_region_name("Región Metropolitana de Santiago") == 13
    assert normalize_region_name("Metropolitana de Santiago") == 13
    assert normalize_region_name("Metropolitana") == 13
    assert normalize_region_name("RM") == 13
    assert normalize_region_name("Santiago") == 13
    assert normalize_region_name("13") == 13
    assert normalize_region_name("XIII") == 13

    # Región de Los Ríos (14)
    assert normalize_region_name("Región de Los Ríos") == 14
    assert normalize_region_name("Los Ríos") == 14
    assert normalize_region_name("Los Rios") == 14  # Sin tilde
    assert normalize_region_name("XIV") == 14
    assert normalize_region_name("14") == 14

    # Región de Valparaíso (5)
    assert normalize_region_name("Región de Valparaíso") == 5
    assert normalize_region_name("Valparaíso") == 5
    assert normalize_region_name("Valparaiso") == 5
    assert normalize_region_name("V") == 5
    assert normalize_region_name("5") == 5

    # Región del Biobío (8)
    assert normalize_region_name("Región del Biobío") == 8
    assert normalize_region_name("Biobío") == 8
    assert normalize_region_name("Biobio") == 8
    assert normalize_region_name("Bio-Bio") == 8
    assert normalize_region_name("VIII") == 8

    # Entrada inválida o desconocida
    assert normalize_region_name("Desconocida") is None
    assert normalize_region_name("") is None
    assert normalize_region_name(None) is None  # type: ignore


def test_are_regions_matching_strict() -> None:
    """Verifica que la función de coincidencia estricta valide pertenencia geográfica de forma robusta."""
    # Coincidencia con variantes de nombre
    assert are_regions_matching("Los Ríos", ["Región de Los Ríos", "Región de Los Lagos"]) is True
    assert are_regions_matching("Región de Los Ríos", ["Los Rios"]) is True
    assert are_regions_matching("Metropolitana", ["Región Metropolitana de Santiago"]) is True
    assert are_regions_matching("Santiago", ["RM"]) is True

    # No coincidencia
    assert are_regions_matching("Antofagasta", ["Región de Valparaíso", "RM"]) is False
    assert are_regions_matching("Los Ríos", ["Región Metropolitana de Santiago"]) is False

    # Casos borde
    assert are_regions_matching(None, ["Metropolitana"]) is False
    assert are_regions_matching("Metropolitana", []) is True  # Sin filtro de proveedor -> permite todo
    assert are_regions_matching("Metropolitana", None) is True  # type: ignore


def test_get_canonical_region_name() -> None:
    """Verifica la obtención del nombre canónico oficial por ID."""
    assert get_canonical_region_name(13) == "Región Metropolitana de Santiago"
    assert get_canonical_region_name(14) == "Región de Los Ríos"
    assert get_canonical_region_name(5) == "Región de Valparaíso"
    assert get_canonical_region_name(99) == "Región Desconocida"
