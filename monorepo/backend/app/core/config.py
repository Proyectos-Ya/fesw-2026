from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "proyectosya"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    mercado_publico_ticket: str = ""

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "licitaciones"

    embedding_model: str = "BAAI/bge-m3"
    embedding_vector_size: int = 1024

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

settings = Settings()