from app.shared.slug import slugify


def test_quita_tildes_y_signos():
    assert slugify("Obras de Construcción e Infraestructura") == (
        "obras-de-construccion-e-infraestructura"
    )


def test_colapsa_separadores():
    assert slugify("  ISO 9001:2015  ") == "iso-9001-2015"


def test_texto_sin_letras_ni_digitos():
    assert slugify("  --  ") == ""
