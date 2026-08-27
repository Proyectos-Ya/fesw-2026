"""El relleno de variables tiene que cubrir todos los campos obligatorios.

El bug que este test previene: `Settings` se instancia a nivel de módulo, así que
un campo obligatorio nuevo sin valor de relleno hace que pytest falle **en la
recolección**, no en un test. El error resultante parece un defecto del código y
no lo es, y además rompe CI, donde no hay `.env`.

Con este test, agregar un campo obligatorio sin agregarlo al relleno falla como
un test normal y con un mensaje que dice exactamente qué hacer.
"""

from pydantic_core import PydanticUndefined

from app.config import MIN_JWT_SECRET_BYTES, Settings
from pytest_env_defaults import RELLENO_ENV


def _campos_obligatorios() -> set[str]:
    """Campos de Settings sin valor por defecto: hay que suministrarlos sí o sí."""
    return {
        nombre
        for nombre, campo in Settings.model_fields.items()
        if campo.default is PydanticUndefined and campo.default_factory is None
    }


def test_el_relleno_cubre_todos_los_campos_obligatorios():
    faltantes = _campos_obligatorios() - {c.lower() for c in RELLENO_ENV}
    assert not faltantes, (
        f"Campos obligatorios de Settings sin valor de relleno: {sorted(faltantes)}. "
        "Agrégalos a RELLENO_ENV en backend/conftest.py o pytest fallará en la "
        "recolección al no haber .env (por ejemplo, en CI)."
    )


def test_el_relleno_no_trae_claves_de_mas():
    """Una clave que ya no es obligatoria en Settings es relleno muerto."""
    sobrantes = {c.lower() for c in RELLENO_ENV} - _campos_obligatorios()
    assert not sobrantes, (
        f"RELLENO_ENV define claves que Settings ya no exige: {sorted(sobrantes)}."
    )


def test_la_clave_de_pruebas_pasa_la_validacion_de_largo():
    """De nada sirve rellenar JWT_SECRET_KEY con algo que el validador rechaza."""
    clave = RELLENO_ENV["JWT_SECRET_KEY"]
    assert len(clave.encode("utf-8")) >= MIN_JWT_SECRET_BYTES
