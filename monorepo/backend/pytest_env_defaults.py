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
    # Host inexistente a propósito: ningún test debe llegar a la red para
    # verificar un token. Los que ejercitan la verificación inyectan el JWKS.
    # Va en https porque `is_dev` es False por defecto y la configuración exige
    # TLS fuera de desarrollo: el relleno tiene que ser válido sin ayuda.
    "SUPABASE_URL": "https://supabase-de-pruebas.local",
}
