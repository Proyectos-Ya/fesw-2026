from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        # Necesario porque database_url_override declara alias DATABASE_URL y aun
        # así debe poder construirse por nombre en los tests.
        populate_by_name=True,
    )

    # --- PostgreSQL ---
    # Cadena de conexión completa. Tiene prioridad sobre los POSTGRES_* de abajo,
    # que siguen sirviendo para el compose local. Los proveedores gestionados
    # (Supabase, Neon, RDS) entregan la URL armada, y con el pooler el usuario
    # viene en formato `postgres.<project-ref>`: descomponerla en piezas para
    # volver a componerla es una fuente de errores gratuita.
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    # Desactiva el caché de sentencias preparadas de asyncpg. Obligatorio detrás
    # de un pooler en modo transacción (Supavisor de Supabase en el puerto 6543,
    # PgBouncer): ahí cada consulta puede caer en una conexión distinta, y una
    # sentencia preparada en otra sesión no existe. El síntoma son errores
    # intermitentes de "prepared statement does not exist", no un fallo limpio.
    db_disable_prepared_statements: bool = False

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "proyectosya"
    postgres_user: str = "postgres"
    postgres_password: str

    # --- Qdrant ---
    # URL completa del servicio. Tiene prioridad sobre qdrant_host/qdrant_http_port,
    # que siguen sirviendo para el compose local. Un servicio gestionado (Qdrant
    # Cloud) entrega un endpoint https con un puerto propio, y armarlo a mano
    # desde las piezas obliga a asumir el esquema http.
    qdrant_url_override: str | None = Field(default=None, alias="QDRANT_URL")
    # Solo la exigen los servicios gestionados; el Qdrant del compose local no
    # pide autenticación, así que por defecto no se manda nada.
    qdrant_api_key: str | None = None

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
    # Atributo Secure de la cookie de sesión: el navegador solo la manda por
    # HTTPS. El valor por defecto se deriva de `is_dev` (ver el validador de más
    # abajo) en vez de ser un `False` fijo, porque ese `False` viajaba tal cual a
    # cualquier despliegue y dejaba la cookie de sesión expuesta a interceptación.
    auth_cookie_secure: bool | None = None
    # SameSite de la cookie. "lax" sirve mientras frontend y backend compartan
    # sitio; si quedan en dominios distintos hace falta "none", que el navegador
    # solo acepta junto con Secure.
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # --- CORS ---
    # Orígenes autorizados, separados por coma. Estaba hardcodeado en
    # middleware.py, así que no había forma de desplegar a otro dominio sin
    # tocar código.
    cors_origins: str = "http://localhost:3000"

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

    # --- Alertas de licitaciones (HdU 08) ---
    # SMTP plano: es el denominador común de Mailpit en local y de Brevo o
    # SendGrid en producción, así que cambiar de entorno es cambiar estas
    # variables y nada de código. Los defaults apuntan al Mailpit que levanta
    # `supabase start` (hay que descomentar `smtp_port` en supabase/config.toml).
    smtp_host: str = "host.docker.internal"
    smtp_port: int = 54325
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "alertas@proyectosya.local"
    # STARTTLS sobre el 587. Mailpit escucha en claro, por eso el default apagado.
    smtp_use_tls: bool = False
    # Base de los enlaces del correo. Debe ser la URL pública del frontend: es
    # lo que el usuario abre desde su bandeja.
    app_base_url: str = "http://localhost:3000"
    # Igual que run_auto_ingestion, permite apagar los bucles sin tocar código.
    run_notification_scan: bool = True
    notification_scan_interval_seconds: int = 300
    notification_digest_hour: int = 8

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

    @model_validator(mode="after")
    def _derivar_cookie_secure(self) -> "Settings":
        """Si no se declaró, Secure sigue a `is_dev`: apagado en local, encendido fuera.

        Se deriva en vez de tener un valor por defecto fijo para que el caso
        peligroso —desplegar sin declarar la variable— caiga del lado seguro.
        """
        if self.auth_cookie_secure is None:
            self.auth_cookie_secure = not self.is_dev
        # El navegador descarta SameSite=None sin Secure, así que la sesión
        # dejaría de viajar y el síntoma sería "no puedo entrar", sin pista.
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError(
                "AUTH_COOKIE_SAMESITE=none exige AUTH_COOKIE_SECURE=true: los "
                "navegadores rechazan esa combinación y la sesión no se envía."
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Orígenes de CORS como lista, desde la cadena separada por comas."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        """URL de conexión, con el driver asyncpg garantizado.

        Los proveedores entregan la URL con esquema `postgresql://` o
        `postgres://`, que SQLAlchemy resuelve al driver **síncrono**. Pegarla
        tal cual en el `.env` produce un error confuso sobre greenlets en la
        primera consulta, así que se normaliza acá.
        """
        if self.database_url_override:
            url = self.database_url_override
            for prefijo in ("postgresql+asyncpg://", "postgres+asyncpg://"):
                if url.startswith(prefijo):
                    return url
            for viejo, nuevo in (
                ("postgresql://", "postgresql+asyncpg://"),
                ("postgres://", "postgresql+asyncpg://"),
            ):
                if url.startswith(viejo):
                    return nuevo + url[len(viejo) :]
            return url

        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @field_validator("qdrant_url_override", "qdrant_api_key", mode="after")
    @classmethod
    def _vacio_es_ausente(cls, valor: str | None) -> str | None:
        """Una variable declarada pero vacía es ausencia, no un valor.

        Es el caso habitual de una plantilla de `.env` con `QDRANT_API_KEY=` sin
        rellenar: sin esto, el cliente mandaría una key vacía y el servidor
        respondería 401 en vez de dejar pasar la conexión anónima.
        """
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None

    @property
    def qdrant_url(self) -> str:
        """URL del servicio, con el override por delante del host y el puerto."""
        if self.qdrant_url_override:
            # Una barra final concatenada con la ruta del cliente da "//". Los
            # paneles la entregan de las dos formas y copiarla tal cual no
            # debería cambiar el comportamiento.
            return self.qdrant_url_override.rstrip("/")

        return f"http://{self.qdrant_host}:{self.qdrant_http_port}"


settings = Settings()  # type: ignore
