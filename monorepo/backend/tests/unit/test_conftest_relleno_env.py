"""El relleno de variables tiene que cubrir todos los campos obligatorios.

El bug que este test previene: `Settings` se instancia a nivel de módulo, así que
un campo obligatorio nuevo sin valor de relleno hace que pytest falle **en la
recolección**, no en un test. El error resultante parece un defecto del código y
no lo es, y además rompe CI, donde no hay `.env`.

Con este test, agregar un campo obligatorio sin agregarlo al relleno falla como
un test normal y con un mensaje que dice exactamente qué hacer.
"""

from pydantic import ValidationError

from app.config import MIN_JWT_SECRET_BYTES, Settings
from pytest_env_defaults import RELLENO_ENV


def _construir(entorno: dict[str, str]) -> Settings:
    """Construye Settings solo con lo que se le pasa, sin leer el .env."""
    return Settings(_env_file=None, **{k.lower(): v for k, v in entorno.items()})  # type: ignore[arg-type]


def test_el_relleno_alcanza_para_construir_settings():
    """La comprobación se hace construyendo, no comparando contra model_fields.

    Un campo puede no tener default y aun así no ser lo único que hace falta: hay
    validadores que exigen combinaciones —DATABASE_URL *o* POSTGRES_PASSWORD, por
    ejemplo— y esos no se ven mirando los campos uno a uno.
    """
    assert _construir(RELLENO_ENV) is not None


def test_cada_clave_del_relleno_hace_falta():
    """Relleno muerto: una clave que se puede quitar sin que nada falle.

    Se comprueba quitándola de verdad, por la misma razón que el test anterior.
    """
    sobrantes = []
    for clave in RELLENO_ENV:
        sin_ella = {k: v for k, v in RELLENO_ENV.items() if k != clave}
        try:
            _construir(sin_ella)
        except ValidationError:
            continue
        sobrantes.append(clave)

    assert not sobrantes, (
        f"RELLENO_ENV define claves que Settings ya no exige: {sorted(sobrantes)}. "
        "Quítalas de pytest_env_defaults.py."
    )


def test_la_clave_de_pruebas_pasa_la_validacion_de_largo():
    """De nada sirve rellenar JWT_SECRET_KEY con algo que el validador rechaza."""
    clave = RELLENO_ENV["JWT_SECRET_KEY"]
    assert len(clave.encode("utf-8")) >= MIN_JWT_SECRET_BYTES
