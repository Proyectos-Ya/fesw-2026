from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings


def _connect_args() -> dict[str, object]:
    """Ajustes de asyncpg según se hable con Postgres directo o con un pooler.

    Detrás de un pooler en modo transacción (Supavisor de Supabase en el 6543,
    PgBouncer) cada consulta puede caer en una conexión distinta del backend, así
    que una sentencia preparada en otra sesión no existe. asyncpg las usa por
    defecto, y el resultado son errores intermitentes de "prepared statement
    ... does not exist" — no un fallo limpio y reproducible.
    """
    if not settings.db_disable_prepared_statements:
        return {}
    return {
        "statement_cache_size": 0,
        # asyncpg también cachea las descripciones de tipo de cada sentencia;
        # desactivar solo lo primero deja el problema a medias.
        "prepared_statement_cache_size": 0,
    }


engine = create_async_engine(
    settings.database_url,
    # En producción, echo=True escribe cada sentencia SQL con sus parámetros en
    # los logs: volumen enorme y datos en claro.
    echo=settings.is_dev,
    pool_pre_ping=True,
    connect_args=_connect_args(),
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


class EsquemaSinMigrar(RuntimeError):
    """La base no tiene aplicadas las migraciones de Alembic."""


async def verificar_esquema_migrado() -> None:
    """Falla al arrancar si la base no está migrada.

    Sin esto el error aparece más tarde y disfrazado: la primera consulta
    revienta con `relation "..." does not exist`, que parece un bug del código y
    no una base sin preparar.

    Solo comprueba que exista `alembic_version` con una revisión; no compara
    contra `head`. Verificar eso exigiría cargar la configuración de Alembic en
    tiempo de arranque, y el caso que importa —la base vacía o creada con el
    viejo `create_all`— ya queda cubierto.
    """
    async with engine.connect() as conn:
        # `to_regclass` devuelve NULL en vez de lanzar error si la tabla no
        # existe, así que sirve para preguntar sin abortar la transacción.
        existe = await conn.scalar(text("SELECT to_regclass('public.alembic_version')"))
        revision = None
        if existe is not None:
            revision = await conn.scalar(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )

    if revision is None:
        raise EsquemaSinMigrar(
            "La base de datos no tiene las migraciones aplicadas. Ejecuta:\n"
            "  alembic upgrade head\n"
            "Si la base ya tiene el esquema porque se creó con el antiguo "
            "create_all, márcala como migrada con:\n"
            "  alembic stamp head"
        )
