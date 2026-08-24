from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.constants import (
    DEFAULT_MERCADOPUBLICO_DETAIL_DELAY,
    DEFAULT_MERCADOPUBLICO_FETCHING_LIMIT,
)

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Largo mínimo de la clave de firma, en bytes. Es lo que exige el RFC 7518 §3.2
# para HS256: una clave más corta que el hash no aporta más seguridad que su
# propio largo y vuelve la fuerza bruta viable.
#
# Va a nivel de módulo y no dentro de Settings porque Pydantic convierte los
# atributos con guion bajo inicial en ModelPrivateAttr, no en el entero.
MIN_JWT_SECRET_BYTES = 32

# La clave de ejemplo que estuvo publicada en el repositorio como valor por
# defecto de `jwt_secret_key`. Se rechaza explícitamente: sin esto, alguien
# podría recuperarla del historial de git, ponerla en su .env y quedar tan
# expuesto como antes, pero ahora en silencio.
_CLAVE_PUBLICADA = "dev-insecure-secret-change-me"

_COMO_GENERAR = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "proyectosya"
    postgres_user: str = "postgres"
    postgres_password: str

    # --- Qdrant ---
    qdrant_host: str = "localhost"
    qdrant_http_port: int = 6333
    qdrant_grpc_port: int = 6334

    # --- Auth / JWT ---
    # Sin valor por defecto a propósito. Antes había uno ("dev-insecure-secret
    # -change-me") que además estaba publicado en el repositorio: como la
    # variable no llegaba por entorno, la aplicación firmaba las sesiones reales
    # con una cadena que cualquiera podía leer. Un default cómodo convierte un
    # fallo de configuración en un agujero silencioso, así que ahora la
    # aplicación no arranca sin clave.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Nombre de la cookie httpOnly donde viaja el token
    auth_cookie_name: str = "access_token"
    # Cookie Secure solo en producción (requiere HTTPS); en local va en False
    auth_cookie_secure: bool = False

    # --- Embeddings ---
    embedding_model: str = "BAAI/bge-m3"
    embedding_vector_size: int = 1024

    # --- Mercado Público ---
    mercado_publico_api_key: str
    mercadopublico_fetching_limit: int = DEFAULT_MERCADOPUBLICO_FETCHING_LIMIT
    mercadopublico_detail_delay: float = DEFAULT_MERCADOPUBLICO_DETAIL_DELAY
    # Ingesta automática al arrancar y región a la que acotarla (None = todas).
    run_auto_ingestion: bool = True
    target_region: str | None = None

    # --- Matching ---
    # Escape para entornos sin RAM suficiente para el reranker ONNX.
    disable_reranker: bool = False
    # Variante ONNX del reranker a descargar y usar. El repositorio publica el
    # mismo modelo en ocho precisiones; bajarlas todas son 8,3 GB.
    #   model_quantized.onnx -> INT8, 571 MB (por defecto; es sobre la que se
    #                           calibraron reranker_temperature y reranker_bias)
    #   model.onnx           -> fp32, 2,3 GB (arrastra model.onnx_data)
    #   model_fp16.onnx      -> fp16, 1,1 GB
    # Cambiar de variante cambia la distribución de los logits, así que la
    # calibración debería re-medirse con tests/matching_evaluation.
    reranker_onnx_variant: str = "model_quantized.onnx"
    reranker_temperature: float = 1.5
    reranker_bias: float = 1.5

    # --- Gemini ---
    gemini_api_key: str
    gemini_model: str

    # Modo desarrollo: reduce el tamaño de página y el número de licitaciones
    # procesadas por ciclo. El valor por defecto es False para que un despliegue
    # sin la variable no arranque en silencio ingestando una fracción de los datos.
    is_dev: bool = False

    @field_validator("jwt_secret_key")
    @classmethod
    def _validar_clave_de_firma(cls, value: str) -> str:
        """Rechaza claves cortas y la que estuvo publicada en el repositorio.

        Se valida acá y no en el borde HTTP porque el momento correcto para
        fallar es el arranque: una clave débil no produce ningún error visible
        en runtime, solo tokens falsificables.
        """
        if value == _CLAVE_PUBLICADA:
            raise ValueError(
                "JWT_SECRET_KEY es la clave de ejemplo que estuvo publicada en el "
                f"repositorio. Genera una propia:\n  {_COMO_GENERAR}"
            )
        largo = len(value.encode("utf-8"))
        if largo < MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET_KEY debe tener al menos {MIN_JWT_SECRET_BYTES} bytes "
                f"para HS256 (RFC 7518 §3.2); tiene {largo}. Genera una con:\n"
                f"  {_COMO_GENERAR}"
            )
        return value

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_http_port}"


settings = Settings()  # type: ignore
