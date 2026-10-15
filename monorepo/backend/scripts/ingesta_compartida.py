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

import json
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.embedding_service import IEmbeddingService
from app.application.services.tender_ingestion_service import (
    ITenderIngestionService,
    ModoCola,
)
from app.config import settings
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.infrastructure.db import crear_engine
from app.infrastructure.repositories.tender_model import TenderMetadataModel
from app.infrastructure.services.tenders.mercado_publico_client import (
    MercadoPublicoClient,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
    condiciones_cola,
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
    from app.infrastructure.repositories.qdrant_lexical_tender_repository import (
        QdrantLexicalTenderRepository,
    )
    from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
        QdrantTenderItemVectorRepository,
    )
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
    print("Colección 'tenders' lista (con sus índices de payload).")

    # La ingesta también guarda un vector por partida; sin esta colección cada
    # licitación fallaría al escribirlo y se daría por perdida tras tres intentos.
    await QdrantTenderItemVectorRepository(
        client=qdrant, vector_size=settings.embedding_vector_size
    ).ensure_collection()
    print("Colección 'tender_items' lista.")

    # Y el vector léxico (BM25) del canal léxico. Sin la colección, la ingesta
    # fallaba en cada licitación con un 404 de Qdrant (plan 305, 2026-10-13).
    await QdrantLexicalTenderRepository(client=qdrant).ensure_collection()
    print("Colección 'tender_lexical' lista.\n")


def imprimir_resumen(cron: str, datos: dict[str, Any]) -> None:
    """Una línea `RESUMEN {json}` por corrida (plan 305).

    Para revisar un día entero de crons basta filtrar los logs de Railway por
    `RESUMEN`: cada línea trae la corrida completa en un JSON de una línea.
    """
    print(
        "RESUMEN "
        + json.dumps({"cron": cron, **datos}, ensure_ascii=False, default=str)
    )


class EmbeddingsContados(IEmbeddingService):
    """Envuelve el servicio de embeddings y cuenta sus llamadas (plan 305).

    Cada corrida de la ingesta guarda cuántas hizo en `ingestion_run`: con los
    vectores por partida, una licitación nueva cuesta dos llamadas y unos
    cuatro textos, y el proveedor cobra por eso.
    """

    def __init__(self, interno: IEmbeddingService) -> None:
        self.interno = interno
        self.llamadas = 0
        self.textos = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.llamadas += 1
        self.textos += len(texts)
        return await self.interno.embed(texts)


class _SinEmbeddings:
    """Para procesos que no calculan vectores, como el cron de estados.

    Con `EMBEDDING_PROVIDER=local`, construir el servicio real carga bge-m3
    (~2 GB) aunque nadie lo use. Si algo lo llamara por error, falla fuerte en
    vez de escribir vectores vacíos.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Este proceso no calcula embeddings.")


def construir_servicio(
    *, con_embeddings: bool = True
) -> tuple[TenderIngestionService, AsyncEngine, AsyncQdrantClient]:
    """Arma el servicio de ingesta con las mismas piezas que usa la aplicación."""
    from app.bootstrap.builders import build_embedding_service

    engine = crear_engine()
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    servicio = TenderIngestionService(
        engine=engine,
        client=MercadoPublicoClient(
            api_keys=settings.mercado_publico_tickets,
            concurrencia_listado=settings.mercadopublico_listing_concurrency,
        ),
        embedding_service=(
            EmbeddingsContados(build_embedding_service())  # type: ignore[arg-type]
            if con_embeddings
            else _SinEmbeddings()  # type: ignore[arg-type]
        ),
        qdrant_client=qdrant,
    )
    return servicio, engine, qdrant


def indices_secundarios(qdrant: AsyncQdrantClient) -> dict[str, Any]:
    """Partidas y léxico, para que el cierre saque la licitación de las tres
    colecciones y no solo de `tenders` (plan 306).

    Se pasan como argumentos con nombre a los casos de uso que borran puntos.
    """
    from app.infrastructure.repositories.qdrant_lexical_tender_repository import (
        QdrantLexicalTenderRepository,
    )
    from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
        QdrantTenderItemVectorRepository,
    )

    return {
        "item_vector_repo": QdrantTenderItemVectorRepository(
            client=qdrant, vector_size=settings.embedding_vector_size
        ),
        "lexical_tender_repo": QdrantLexicalTenderRepository(client=qdrant),
    }


async def marcar_vencidas(engine: AsyncEngine, qdrant: AsyncQdrantClient) -> int:
    """Pasa a `cerrada` lo que venció y sigue figurando publicado.

    En Postgres cambia el estado; en Qdrant se **borra** el punto, porque el
    índice guarda solo activas y el buscador resuelve las cerradas en Postgres.
    Además barre por payload cualquier punto que no esté activo.
    """
    from app.application.use_cases.mark_expired_tenders import (
        MarkExpiredTendersUseCase,
    )
    from app.infrastructure.repositories.qdrant_tender_repository import (
        QdrantTenderRepository,
    )
    from app.infrastructure.repositories.tender_repository import TenderRepository

    async with AsyncSession(engine) as session:
        caso = MarkExpiredTendersUseCase(
            repository=TenderRepository(session),
            tender_vector_repo=QdrantTenderRepository(
                client=qdrant, vector_size=settings.embedding_vector_size
            ),
            **indices_secundarios(qdrant),
        )
        return await caso.execute()


async def borrar_cerradas_sin_uso(
    engine: AsyncEngine, qdrant: AsyncQdrantClient, dias: int | None
) -> int:
    """Borra de Postgres y de las tres colecciones las licitaciones no activas
    que cerraron hace más de `dias` y que nadie usó (plan 306)."""
    from app.application.use_cases.purgar_licitaciones_cerradas import (
        PurgarLicitacionesCerradasUseCase,
    )
    from app.infrastructure.repositories.qdrant_tender_repository import (
        QdrantTenderRepository,
    )
    from app.infrastructure.repositories.sql_tender_retention_repository import (
        SqlTenderRetentionRepository,
    )

    caso = PurgarLicitacionesCerradasUseCase(
        repository=SqlTenderRetentionRepository(engine),
        tender_vector_repo=QdrantTenderRepository(
            client=qdrant, vector_size=settings.embedding_vector_size
        ),
        retencion_dias=dias,
        **indices_secundarios(qdrant),
    )
    return await caso.execute()


async def aplicar_documentos_oficiales(
    engine: AsyncEngine, listas_por_codigo: Mapping[str, Sequence[DocumentoOficialDTO]]
) -> int:
    """Refresca la lista oficial de anexos de las licitaciones que ya tenemos.

    La comparten los dos crons: los dos listan, y el listado ya trae
    `documentos`, así que no cuesta peticiones a la API.
    """
    from app.application.use_cases.tender_attachments.sync_official_attachments import (
        SyncOfficialAttachmentsUseCase,
    )
    from app.infrastructure.repositories.sql_tender_attachment_repository import (
        SqlTenderAttachmentRepository,
    )

    async with AsyncSession(engine) as session:
        caso = SyncOfficialAttachmentsUseCase(SqlTenderAttachmentRepository(session))
        return await caso.execute(listas_por_codigo)


async def contar_pendientes(
    engine: AsyncEngine,
    modo: ModoCola = ModoCola.TODAS,
    antes_de: datetime | None = None,
) -> int:
    """Cuántas licitaciones quedan en la parte de la cola que toma `modo`.

    Filtra igual que el SELECT de la pasada (`condiciones_cola`): si contara
    también las terminales o las que esperan la noche, la cola nunca se vería
    vacía.
    """
    async with AsyncSession(engine) as s:
        stmt = (
            select(func.count())
            .select_from(TenderMetadataModel)
            .where(*condiciones_cola(modo, antes_de))
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
    # El cortacircuito saltó: la API devolvió errores transitorios seguidos.
    api_caida: bool = False

    @property
    def completo(self) -> bool:
        """La cola quedó vacía, sin cortes."""
        return (
            self.pendientes == 0
            and not self.cuota_agotada
            and not self.sin_avance
            and not self.api_caida
        )


async def vaciar_cola(
    servicio: ITenderIngestionService,
    contar_pendientes: Callable[[], Awaitable[int]],
    *,
    modo: ModoCola = ModoCola.TODAS,
    antes_de: datetime | None = None,
    verboso: bool = True,
    en: ResultadoRondas | None = None,
) -> ResultadoRondas:
    """Insiste hasta vaciar la cola, o hasta que insistir deje de servir.

    Dos cortes, con motivos distintos:

    * **Cuota agotada.** Seguir gasta los cuatro reintentos del cliente contra
      una cuota que ya no existe. Se para y se retoma en la corrida siguiente:
      lo que está encolado no se pierde.
    * **API caída.** El cortacircuito del servicio saltó con errores
      transitorios seguidos. La ronda siguiente se los volvería a cobrar.
    * **Varias rondas sin avance.** Alguna licitación está fallando de forma
      reproducible, o la API está caída. Insistir para siempre bloquearía la
      cola. Una ronda que procesa menos de `EXITO_MINIMO_POR_PASADA` de lo que
      intentó también cuenta como sin avance, aunque lo que sí entró se suma.
    """
    inicio = time.perf_counter()
    # `en` deja que el llamador lea el avance aunque la corrida se cancele a
    # mitad: sin él, una corrida que vencía el tope registraba 0 procesadas.
    resultado = en if en is not None else ResultadoRondas()
    pendientes = await contar_pendientes()
    resultado.pendientes = pendientes
    if not pendientes:
        return resultado

    sin_avance = 0
    while pendientes:
        resultado.rondas += 1
        pasada = await servicio.process_unprocessed_tenders(
            modo=modo, antes_de=antes_de
        )
        restantes = await contar_pendientes()

        if pasada.cuota_agotada or pasada.api_caida:
            resultado.cuota_agotada = pasada.cuota_agotada
            resultado.api_caida = pasada.api_caida
            resultado.procesadas += pasada.procesadas
            resultado.pendientes = restantes
            break

        # Lo que esta pasada procesó, no la resta de la cola: el cron de estados
        # encola en paralelo, y una ronda que avanzó podía verse sin avance.
        hechas = pasada.procesadas
        resultado.procesadas += hechas
        pendientes = restantes
        resultado.pendientes = restantes

        intentadas = pasada.procesadas + pasada.fallidas
        goteo = (
            intentadas > 0 and pasada.procesadas < intentadas * EXITO_MINIMO_POR_PASADA
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
