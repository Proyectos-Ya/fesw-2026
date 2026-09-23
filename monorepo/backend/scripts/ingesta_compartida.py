"""Lo que comparten la carga inicial y la sincronización diaria.

`process_unprocessed_tenders` procesa **un lote acotado** y vuelve, en vez de
vaciar la cola entera: así la sesión de lectura dura lo que tarda un SELECT y el
llamador decide si sigue. Alguien tiene que insistir, y ese bucle es idéntico en
la carga inicial y en la sincronización diaria.

Todo esto vivía dentro de `bootstrap_corpus.py`. Copiarlo al cron habría sido la
forma de que uno de los dos arreglara un caso raro y el otro no: las condiciones
de corte del bucle —cuota agotada, rondas sin avance— salieron de corridas reales
contra la API y no son obvias.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.config import settings
from app.infrastructure.db import crear_engine
from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)

# Hosts que se consideran "esta máquina". Todo lo demás es una base compartida
# —producción o `dev test`— y escribir ahí tiene que pedirse explícitamente.
HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "db"}


def es_local(url: str) -> bool:
    """Si la URL apunta a una base de esta máquina."""
    return (urlsplit(url).hostname or "") in HOSTS_LOCALES


async def preparar_destino(engine: AsyncEngine, qdrant: AsyncQdrantClient) -> None:
    """Deja la base y el índice listos para recibir datos.

    Normalmente lo hace el arranque de la API (`main.py`), pero ni la carga inicial
    ni el cron pueden depender de que la API haya corrido alguna vez contra esta
    base: la tabla `region` estaría vacía y los FK de `tender` fallarían, y la
    colección `tenders` no existiría. Ambas operaciones son idempotentes, así que
    repetirlas en cada corrida no cuesta nada.
    """
    from app.infrastructure.repositories.qdrant_tender_repository import (
        QdrantTenderRepository,
    )
    from app.infrastructure.seeder import seed_database_metadata

    async with AsyncSession(engine) as s:
        await seed_database_metadata(s)
    print("Regiones y estados sembrados.")

    await QdrantTenderRepository(
        client=qdrant, vector_size=settings.embedding_vector_size
    ).ensure_collection()
    print("Colección 'tenders' lista (con sus índices de payload).\n")


def construir_servicio() -> tuple[
    TenderIngestionService, AsyncEngine, AsyncQdrantClient
]:
    """Arma el servicio de ingesta con las mismas piezas que usa la aplicación."""
    from app.bootstrap import build_embedding_service

    engine = crear_engine()
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    servicio = TenderIngestionService(
        engine=engine,
        client=MercadoPublicoClient(api_keys=settings.mercado_publico_tickets),
        embedding_service=build_embedding_service(),
        qdrant_client=qdrant,
    )
    return servicio, engine, qdrant


async def contar_pendientes(engine: AsyncEngine) -> int:
    """Cuántas licitaciones quedan en la cola sin procesar."""
    async with AsyncSession(engine) as s:
        stmt = (
            select(func.count())
            .select_from(TenderMetadataModel)
            .where(col(TenderMetadataModel.is_processed).is_(False))
        )
        return (await s.exec(stmt)).one()  # type: ignore[arg-type]


# Rondas seguidas sin procesar nada antes de rendirse. Antes bastaba una, y tenía
# sentido cuando cada pasada vaciaba la cola entera. Ahora cada pasada toma un
# lote acotado y las licitaciones que fallan se van al final del orden, así que
# la ronda siguiente trabaja sobre otras: una sola ronda en blanco ya no
# significa que no se pueda avanzar.
RONDAS_SIN_AVANCE_MAX = 3

# Éxito mínimo de una pasada, sobre lo que intentó, para contarla como avance.
# Con Mercado Público caído entra alguna licitación de vez en cuando, y si
# cualquier avance reiniciara el contador el vaciado no se rendiría nunca: la
# segunda corrida en `dev test` (17-sep-2026) insistió ~45 minutos con 19
# licitaciones en 504. Se mide sobre el lote y no sobre la cola, para no cortar
# una cola grande que avanza 200 de 5.000 por ronda.
EXITO_MINIMO_POR_PASADA = 0.10


@dataclass
class ResultadoRondas:
    """Cómo terminó el vaciado, para que el llamador decida qué reportar."""

    procesadas: int = 0
    pendientes: int = 0
    rondas: int = 0
    segundos: float = 0.0
    cuota_agotada: bool = False
    sin_avance: bool = False

    @property
    def completo(self) -> bool:
        """La cola quedó vacía, sin cortes."""
        return self.pendientes == 0 and not self.cuota_agotada and not self.sin_avance


async def vaciar_cola(
    servicio: ITenderIngestionService,
    contar_pendientes: Callable[[], Awaitable[int]],
    *,
    verboso: bool = True,
) -> ResultadoRondas:
    """Insiste hasta vaciar la cola, o hasta que insistir deje de servir.

    Dos cortes, con motivos distintos:

    * **Cuota agotada.** Seguir gasta los cuatro reintentos del cliente contra
      una cuota que ya no existe. Se para y se retoma en la corrida siguiente:
      lo que está encolado no se pierde.
    * **Varias rondas sin avance.** Alguna licitación está fallando de forma
      reproducible, o la API está caída. Insistir para siempre bloquearía la
      cola. Una ronda que procesa menos de `EXITO_MINIMO_POR_PASADA` de lo que
      intentó también cuenta como sin avance, aunque lo que sí entró se suma.
    """
    inicio = time.perf_counter()
    resultado = ResultadoRondas()
    pendientes = await contar_pendientes()
    resultado.pendientes = pendientes
    if not pendientes:
        return resultado

    sin_avance = 0
    while pendientes:
        resultado.rondas += 1
        pasada = await servicio.process_unprocessed_tenders()
        restantes = await contar_pendientes()

        if pasada.cuota_agotada:
            resultado.cuota_agotada = True
            resultado.pendientes = restantes
            break

        hechas = pendientes - restantes
        resultado.procesadas += hechas
        pendientes = restantes
        resultado.pendientes = restantes

        intentadas = pasada.procesadas + pasada.fallidas
        goteo = (
            intentadas > 0
            and pasada.procesadas < intentadas * EXITO_MINIMO_POR_PASADA
        )
        if hechas <= 0 or goteo:
            sin_avance += 1
            if verboso:
                print(
                    f"  ronda {resultado.rondas}: sin avance ({hechas} procesadas, "
                    f"{restantes} pendientes), intento "
                    f"{sin_avance}/{RONDAS_SIN_AVANCE_MAX}"
                )
            if sin_avance >= RONDAS_SIN_AVANCE_MAX:
                resultado.sin_avance = True
                break
            continue

        sin_avance = 0
        if verboso:
            print(
                f"  ronda {resultado.rondas}: {hechas} procesadas, quedan {restantes}"
            )

    resultado.segundos = time.perf_counter() - inicio
    return resultado
