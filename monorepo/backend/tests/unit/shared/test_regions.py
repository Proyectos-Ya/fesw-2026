from app.shared.regions import (
    are_regions_matching,
    canonical_region_name,
    normalize_region_name,
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
    assert (
        are_regions_matching("Los Ríos", ["Región de Los Ríos", "Región de Los Lagos"])
        is True
    )
    assert are_regions_matching("Región de Los Ríos", ["Los Rios"]) is True
    assert (
        are_regions_matching("Metropolitana", ["Región Metropolitana de Santiago"])
        is True
    )
    assert are_regions_matching("Santiago", ["RM"]) is True

    # No coincidencia
    assert are_regions_matching("Antofagasta", ["Región de Valparaíso", "RM"]) is False
    assert (
        are_regions_matching("Los Ríos", ["Región Metropolitana de Santiago"]) is False
    )

    # Casos borde
    assert are_regions_matching(None, ["Metropolitana"]) is False
    assert (
        are_regions_matching("Metropolitana", []) is True
    )  # Sin filtro de proveedor -> permite todo
    assert are_regions_matching("Metropolitana", None) is True  # type: ignore


def test_canonical_region_name() -> None:
    """El nombre canónico es el que se siembra en la tabla `region`.

    Va sin el prefijo "Región" porque así están las filas ya sembradas; el
    prefijo se reconoce a la entrada (ver `normalize_region_name`) pero no se
    escribe.
    """
    assert canonical_region_name(13) == "Metropolitana de Santiago"
    assert canonical_region_name(14) == "Los Ríos"
    assert canonical_region_name(5) == "Valparaíso"
    assert canonical_region_name(99) == "Desconocida"
