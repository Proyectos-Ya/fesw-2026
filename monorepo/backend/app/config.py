from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.constants import (
    DEFAULT_MERCADOPUBLICO_DETAIL_CONCURRENCY,
    DEFAULT_MERCADOPUBLICO_DETAIL_DELAY,
    DEFAULT_MERCADOPUBLICO_FETCHING_LIMIT,
)

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Host oficial de cada proveedor de embeddings. "local" no llama a ninguno, pero
# tiene entrada para que `embedding_api_url` no falle si alguien la consulta.
_URL_POR_PROVEEDOR = {
    "local": "",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "huggingface": "https://router.huggingface.co",
}


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
    # Opcional a propósito: con DATABASE_URL puesta, estos POSTGRES_* no se usan
    # para nada. Exigirla igual obligaba a inventar un valor en las variables del
    # despliegue, y quien las configura sin conocer el código no tiene cómo saber
    # que da lo mismo —lo razonable es suponer lo contrario—. El validador de más
    # abajo se encarga de que no falten las dos a la vez.
    postgres_password: str | None = None

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

    # --- Supabase Auth ---
    # Las sesiones las emite Supabase, no esta API: acá solo se verifican. Para
    # eso hacen falta la URL donde vive el JWKS, el emisor que se acepta y la
    # audiencia. Sin valor por defecto a propósito: uno apuntando a localhost
    # dejaría arrancar un despliegue mal configurado que rechaza todas las
    # sesiones, y eso es más difícil de diagnosticar que no arrancar.
    supabase_url: str
    # Normalmente se deriva de `supabase_url`. Se declara aparte para el caso en
    # que el host que alcanza a Supabase no sea el que firma: dentro de Docker
    # el contenedor llega por `host.docker.internal`, pero GoTrue emite
    # `iss: http://127.0.0.1:54321/auth/v1`. Con una sola variable, o falla la
    # descarga del JWKS o falla la validación del emisor.
    supabase_jwt_issuer: str | None = None
    # El claim `aud` que Supabase pone en el token de un usuario conectado.
    supabase_jwt_audience: str = "authenticated"
    # Cuánto se conservan las claves públicas antes de volver a pedirlas.
    supabase_jwks_cache_seconds: int = 600

    # --- CORS ---
    # Orígenes autorizados, separados por coma. Estaba hardcodeado en
    # middleware.py, así que no había forma de desplegar a otro dominio sin
    # tocar código.
    cors_origins: str = "http://localhost:3000"

    # --- Embeddings ---
    embedding_model: str = "BAAI/bge-m3"
    embedding_vector_size: int = 1024

    # De dónde sale el modelo: "local" lo carga en el proceso (sentence-transformers,
    # ~938 MB de RAM) y el resto lo delega a un proveedor externo, que tiene que servir
    # el MISMO modelo: cambiarlo invalida todo lo ya indexado en Qdrant, porque los
    # vectores de dos modelos distintos no son comparables entre sí.
    #
    # Se nombra al proveedor en vez de un genérico "api" porque no hablan el mismo
    # protocolo: DeepInfra expone el dialecto OpenAI (`data[].embedding`) y Hugging
    # Face devuelve un array de arrays plano por su endpoint de feature-extraction.
    embedding_provider: Literal["local", "deepinfra", "huggingface"] = "local"
    embedding_api_key: str | None = None
    # Solo para apuntar a otro host (un proxy, una instancia dedicada). Vacío usa el
    # oficial del proveedor elegido.
    embedding_api_base_url: str | None = None

    # Mismo esquema para el reranker, que en local es ONNX (~1,3 GB de RAM).
    reranker_provider: Literal["local", "pinecone"] = "local"
    pinecone_api_key: str | None = None
    pinecone_base_url: str = "https://api.pinecone.io"
    pinecone_rerank_model: str = "bge-reranker-v2-m3"
    # La API de Pinecone versiona por header y rechaza las peticiones sin él.
    pinecone_api_version: str = "2025-04"

    # --- Mercado Público ---
    mercado_publico_api_key: str
    mercadopublico_fetching_limit: int = DEFAULT_MERCADOPUBLICO_FETCHING_LIMIT
    mercadopublico_detail_delay: float = DEFAULT_MERCADOPUBLICO_DETAIL_DELAY
    mercadopublico_detail_concurrency: int = (
        DEFAULT_MERCADOPUBLICO_DETAIL_CONCURRENCY
    )
    # Ingesta automática al arrancar y región a la que acotarla (None = todas).
    run_auto_ingestion: bool = True
    target_region: str | None = None
    # Heurística de respaldo para resolver comuna del comprador
    # (`resolve_comuna_from_organismo_name_generic`, ver app/shared/comunas.py):
    # busca el nombre de cualquier comuna en cualquier parte del texto, no solo
    # tras "Municipalidad de". Más cobertura, algo más de riesgo de falso
    # positivo -- apagada por defecto hasta decidir si vale la pena el riesgo.
    enable_comuna_generic_heuristic: bool = True

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

    @model_validator(mode="after")
    def _exigir_https_en_supabase(self) -> "Settings":
        """Fuera de desarrollo, el JWKS tiene que viajar por TLS.

        Sobre HTTP cualquiera en la red puede responder con su propia clave
        pública, y a partir de ahí firmar sesiones de cualquier usuario sin que
        nada falle. Es el mismo agujero silencioso que una clave de firma
        publicada, así que se cierra igual: al arrancar.
        """
        if not self.is_dev and not self.supabase_url.startswith("https://"):
            raise ValueError(
                "SUPABASE_URL debe usar https fuera de desarrollo; llegó "
                f"'{self.supabase_url}'. Por esa conexión se descargan las "
                "claves con que se valida cada sesión."
            )
        return self

    @property
    def jwt_issuer(self) -> str:
        """Emisor que se acepta en el claim `iss` de los tokens.

        El `rstrip` importa: una barra final en la variable produciría
        `.../auth//v1`, que no coincide con lo que emite Supabase, y el síntoma
        sería un 401 en todo sin ninguna pista de por qué.
        """
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        """Dónde publica Supabase las claves públicas de firma.

        Se arma desde `supabase_url` y no desde `jwt_issuer`, porque son
        justamente las dos cosas que pueden no coincidir dentro de Docker.
        """
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

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

    @field_validator("embedding_api_key", "pinecone_api_key", "postgres_password", mode="after")
    @classmethod
    def _credencial_vacia_es_ausente(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return valor.strip() or None

    @model_validator(mode="after")
    def _exigir_una_forma_de_conectar_a_postgres(self) -> "Settings":
        """Hay dos formas válidas de configurar la base, y hace falta una.

        Falla al construir Settings y no en la primera consulta: un error de
        configuración tiene que impedir el arranque, no aparecer más tarde
        disfrazado de fallo de conexión.
        """
        if not self.database_url_override and not self.postgres_password:
            raise ValueError(
                "Falta la configuración de la base de datos. Usa DATABASE_URL con "
                "la cadena completa (lo habitual con Supabase, Neon o RDS), o bien "
                "POSTGRES_PASSWORD junto a los demás POSTGRES_* (lo que hace el "
                "compose local)."
            )
        return self

    @model_validator(mode="after")
    def _exigir_credencial_del_proveedor(self) -> "Settings":
        """En modo API, sin credencial la aplicación no arranca.

        Dejarlo pasar convierte un error de configuración en un fallo en la
        primera petición del primer usuario. Para el embedding es peor todavía:
        la ingesta escribiría vectores fallidos en Qdrant, y eso no se arregla
        corrigiendo la variable —hay que reindexar.
        """
        faltantes = []
        if self.embedding_provider != "local" and not self.embedding_api_key:
            faltantes.append(
                f"EMBEDDING_API_KEY (EMBEDDING_PROVIDER={self.embedding_provider})"
            )
        if self.reranker_provider != "local" and not self.pinecone_api_key:
            faltantes.append(
                f"PINECONE_API_KEY (RERANKER_PROVIDER={self.reranker_provider})"
            )
        if faltantes:
            raise ValueError("Falta configurar: " + ", ".join(faltantes))
        return self

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
    def embedding_api_url(self) -> str:
        """Host del proveedor de embeddings, con el override por delante."""
        if self.embedding_api_base_url:
            return self.embedding_api_base_url.rstrip("/")
        return _URL_POR_PROVEEDOR[self.embedding_provider]

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
