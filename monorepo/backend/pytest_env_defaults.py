"""Valores de relleno para las variables de entorno obligatorias en los tests.

Vive en su propio módulo y no dentro de `conftest.py` porque pytest registra
todos los `conftest.py` en `sys.modules` bajo el mismo nombre `conftest`: un
`from conftest import ...` resuelve a cualquiera de ellos, no necesariamente al
de la raíz. El nombre `pytest_env_defaults` no calza con `python_files`, así que
pytest no intenta recolectarlo como test.

Ver `conftest.py` (raíz del backend) para el porqué del mecanismo.
"""

# Deliberadamente reconocibles como de prueba. Ninguno sirve para hablar con un
# servicio real: los tests que necesitan uno de verdad o bien lo mockean, o
# están marcados como `integration` y se saltan solos.
RELLENO_ENV = {
    "POSTGRES_PASSWORD": "postgres",
    "MERCADO_PUBLICO_API_KEY": "test-mercado-publico-key",
    "GEMINI_API_KEY": "test-gemini-key",
    "GEMINI_MODEL": "gemini-test",
    # Tiene que superar el mínimo de config.MIN_JWT_SECRET_BYTES (32 bytes).
    # Es una clave de pruebas y se nota; firmar con ella fuera de los tests no
    # protege nada.
    "JWT_SECRET_KEY": "clave-de-pruebas-no-usar-en-produccion",
}
