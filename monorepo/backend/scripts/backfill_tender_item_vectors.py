"""Vectores de partidas para las licitaciones que ya estaban en la base.

El puntaje de compatibilidad (`CompatibilityScorer`) compara las keywords del
proveedor contra **cada partida** de la licitación, no contra el texto agregado.
Los vectores por partida los guarda la ingesta al crear o cambiar una licitación
(colección `tender_items` de Qdrant), pero las licitaciones ingestadas antes de
este cambio no los tienen. Sin ellos el scorer los embebe al vuelo en cada
petición, que funciona pero paga inferencia en un camino de lectura.

Este script los calcula una sola vez para las que faltan.

Payload para el pre-filtro
--------------------------
Cada punto de `tender_items` lleva el mismo payload que el de la licitación en
`tenders` (estado, región, provincia, comuna, monto, cierre y publicación): es lo
que permite buscar licitaciones por sus partidas filtrando por esos campos DENTRO
de la búsqueda, sin filtrar después del top-K. El script lo **copia desde el
punto de `tenders`** (no lo recalcula desde Postgres): así queda idéntico al que
usa el canal de la licitación completa.

- Las licitaciones que ya tienen vectores reciben su payload con `set_payload`,
  sin re-embeber nada.
- Las nuevas se suben con ese mismo payload.
- Una licitación sin punto (o sin payload) en `tenders` se cuenta como
  "sin payload": se indexa igual, pero no pasará filtros hasta que se corrija
  (ver `scripts.backfill_tender_payloads`).

Qué recorre
-----------
Por defecto, las licitaciones **abiertas** (publicadas y con cierre futuro): son
las únicas que el ranking o el cálculo a pedido llegan a puntuar. `--incluir-cerradas`
recorre también el resto.

Una licitación sin partidas no se indexa: no hay nada que embeber, y el scorer ya
la cubre con su nombre y descripción.

Cómo lo hace
------------
- Lee de a `LICITACIONES_POR_GRUPO` licitaciones con sus partidas, pagina por id.
- Omite las que ya tienen vectores (`get_many`), así que es **reanudable**: se
  puede interrumpir y volver a correr sin repetir el trabajo.
- Embebe los textos de cada grupo en **lotes de 8**, ordenados por largo. Con el
  tamaño por defecto de sentence-transformers (32) BGE-M3 se queda sin memoria
  cuando las partidas son largas; ordenar por largo evita que un texto corto
  pague el relleno de uno largo.
- Guarda con un `upsert` por licitación apenas termina su grupo.

Uso
---
    # Diagnóstico: cuántas faltan y cuántos textos hay que embeber. No carga el
    # modelo ni escribe nada. Empieza siempre por aquí.
    python -m scripts.backfill_tender_item_vectors --solo-contar

    # Prueba con unas pocas antes de la corrida completa
    python -m scripts.backfill_tender_item_vectors --limite 20

    # Corrida completa (reanudable): indexa lo que falta y completa el payload de
    # todo lo indexado
    python -m scripts.backfill_tender_item_vectors

    # Solo copiar los payloads a lo ya indexado. No carga el modelo de embeddings
    # ni indexa las que faltan: es el paso para las colecciones ya cargadas.
    python -m scripts.backfill_tender_item_vectors --solo-payload

Advertencias
------------
- Apuntar a una base o a un Qdrant que no sean locales exige
  `--confirmar-produccion`: es una operación deliberada, no algo que deba pasar
  por olvidar una variable de entorno.
- Aborta si el servicio de embeddings cayó al `MockEmbeddingService`: escribiría
  vectores de puros ceros, que no se arreglan corrigiendo la configuración.
- Reanudar recorre otra vez las páginas ya hechas (lee sus vectores para saber que
  están). Es lectura, no inferencia, pero no es gratis en un corpus grande.
"""

import argparse
import asyncio
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.text_builder import TextBuilder
from app.config import settings
from app.infrastructure.repositories.qdrant_tender_filters import PAYLOAD_INDEXES
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.infrastructure.repositories.tender_model import TenderModel
from app.shared.constants import PUBLICADA_STATUS_ID
from app.shared.datetime_utils import utc_now_naive

HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "db"}

# Textos por llamada al modelo. Deliberadamente chico: ver el docstring del módulo.
TAMANO_LOTE_EMBEDDING = 8

# Licitaciones que se leen, embeben y guardan juntas. Acota la memoria (los
# vectores de un grupo viven en RAM hasta guardarse) y lo que se pierde si el
# proceso se interrumpe a mitad de un grupo.
LICITACIONES_POR_GRUPO = 50

# Colección de la que se copia el payload: la de las licitaciones completas.
COLECCION_LICITACIONES = "tenders"

# Puntos por `retrieve` al leer payloads. Acota el largo de la petición y de la
# respuesta, igual que el lote de `QdrantTenderItemVectorRepository.get_many`.
LOTE_LECTURA_PAYLOADS = 256

# Una licitación y las partidas que hay que embeber para ella.
LicitacionConTextos = tuple[uuid.UUID, list[str]]

# `leer_pagina(despues_de, tamano)`: hasta `tamano` licitaciones con id mayor a
# `despues_de`, ordenadas por id. Se inyecta para poder probar el recorrido sin
# una base de datos.
LectorDePaginas = Callable[
    [uuid.UUID | None, int], Awaitable[list[LicitacionConTextos]]
]

# `leer_payloads(ids)`: el payload de cada licitación que lo tenga en "tenders".
# Las que no tienen punto o payload simplemente no aparecen en el resultado.
LectorDePayloads = Callable[[list[uuid.UUID]], Awaitable[dict[uuid.UUID, dict]]]

# `ya_indexadas(ids)`: se le entrega, página a página, quiénes ya tienen vectores.
AlEncontrarIndexadas = Callable[[list[uuid.UUID]], Awaitable[None]]


@dataclass
class Resumen:
    """Qué encontró y qué hizo una pasada. Lo imprime `--solo-contar` y la carga."""

    revisadas: int = 0
    sin_partidas: int = 0
    ya_indexadas: int = 0
    pendientes: int = 0
    textos: int = 0
    indexadas: int = 0
    # Licitaciones (nuevas o ya indexadas) a las que se les escribió el payload
    # copiado de "tenders", y las que no lo tenían allá.
    payloads_copiados: int = 0
    sin_payload: int = 0


def _es_local(url: str) -> bool:
    return (urlsplit(url).hostname or "") in HOSTS_LOCALES


def _destinos_no_locales(database_url: str, qdrant_url: str) -> list[str]:
    """Los destinos de escritura que no son locales, nombrados para el mensaje.

    Se mira también Qdrant y no solo la base: el script escribe ahí, y una base
    local con un Qdrant en la nube es igual de deliberado que lo contrario.
    """
    destinos = []
    if not _es_local(database_url):
        destinos.append(f"la base de datos ({urlsplit(database_url).hostname})")
    if not _es_local(qdrant_url):
        destinos.append(f"Qdrant ({urlsplit(qdrant_url).hostname})")
    return destinos


def _exigir_embedding_real(embedding: IEmbeddingService) -> None:
    """Aborta si el servicio de embeddings es el de mentira.

    `build_embedding_service` cae a `MockEmbeddingService` en desarrollo cuando el
    modelo no carga. Acá eso significaría persistir vectores de puros ceros.
    """
    from app.bootstrap import MockEmbeddingService

    if isinstance(embedding, MockEmbeddingService):
        sys.exit(
            "El modelo de embeddings no cargó (se obtuvo MockEmbeddingService).\n"
            "Escribiría vectores de puros ceros; revisa el log de arranque del "
            "modelo y la configuración EMBEDDING_PROVIDER."
        )


def _lector_payloads(qdrant: AsyncQdrantClient) -> LectorDePayloads:
    """Lee de la colección "tenders" el payload de las licitaciones pedidas.

    Copia solo los campos por los que se filtra (`PAYLOAD_INDEXES`): son los que el
    punto de partidas necesita, y así nada más viaja de una colección a otra.
    """

    async def leer(ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
        payloads: dict[uuid.UUID, dict] = {}
        for inicio in range(0, len(ids), LOTE_LECTURA_PAYLOADS):
            lote = [str(i) for i in ids[inicio : inicio + LOTE_LECTURA_PAYLOADS]]
            puntos = await qdrant.retrieve(
                collection_name=COLECCION_LICITACIONES,
                ids=lote,  # type: ignore[arg-type]
                with_payload=True,
                with_vectors=False,
            )
            for punto in puntos:
                payload = {
                    campo: valor
                    for campo, valor in (punto.payload or {}).items()
                    if campo in PAYLOAD_INDEXES
                }
                if payload:
                    payloads[uuid.UUID(str(punto.id))] = payload
        return payloads

    return leer


def _lotes_por_largo(textos: Iterable[str], tamano: int) -> list[list[str]]:
    """Textos distintos, ordenados de menor a mayor largo y cortados en lotes.

    Un lote se rellena hasta el largo de su texto más largo, así que agrupar
    largos parecidos evita que un texto corto pague el costo de uno largo.
    """
    unicos = sorted(dict.fromkeys(textos), key=len)
    return [unicos[i : i + tamano] for i in range(0, len(unicos), tamano)]


async def _embeber_por_lotes(
    embedding: IEmbeddingService, textos: Iterable[str], tamano_lote: int
) -> dict[str, list[float]]:
    """Un vector por texto distinto, llamando al modelo de a `tamano_lote`."""
    vectores: dict[str, list[float]] = {}
    for lote in _lotes_por_largo(textos, tamano_lote):
        for texto, vector in zip(lote, await embedding.embed(lote), strict=True):
            vectores[texto] = vector
    return vectores


def _clasificar(
    licitaciones: list[LicitacionConTextos],
    con_vectores: set[uuid.UUID],
    resumen: Resumen,
) -> list[LicitacionConTextos]:
    """Deja solo las que hay que indexar y anota el resto en el resumen."""
    pendientes = []
    for tender_id, textos in licitaciones:
        resumen.revisadas += 1
        if not textos:
            resumen.sin_partidas += 1
        elif tender_id in con_vectores:
            resumen.ya_indexadas += 1
        else:
            resumen.pendientes += 1
            resumen.textos += len(textos)
            pendientes.append((tender_id, textos))
    return pendientes


def _repartir(
    grupo: list[LicitacionConTextos], vectores: dict[str, list[float]]
) -> list[tuple[uuid.UUID, list[list[float]]]]:
    """Arma los vectores de cada licitación, en el orden de sus partidas."""
    return [
        (tender_id, [vectores[texto] for texto in textos])
        for tender_id, textos in grupo
    ]


async def _indexar_grupo(
    embedding: IEmbeddingService,
    item_repo: ITenderItemVectorRepository,
    grupo: list[LicitacionConTextos],
    tamano_lote: int,
    payloads: dict[uuid.UUID, dict] | None = None,
) -> int:
    """Embebe los textos del grupo y guarda un upsert por licitación.

    Cada upsert lleva el payload copiado de "tenders", si lo hay: el upsert
    reemplaza el punto entero, así que subirlo sin payload lo dejaría sin filtros.
    """
    vectores = await _embeber_por_lotes(
        embedding, (texto for _, textos in grupo for texto in textos), tamano_lote
    )
    for tender_id, vectores_de_partidas in _repartir(grupo, vectores):
        await item_repo.upsert(
            tender_id, vectores_de_partidas, (payloads or {}).get(tender_id)
        )
    return len(grupo)


async def _copiar_payloads(
    ids: list[uuid.UUID],
    item_repo: ITenderItemVectorRepository,
    leer_payloads: LectorDePayloads,
    resumen: Resumen,
) -> None:
    """Aplica a las licitaciones ya indexadas el payload copiado de "tenders".

    `set_payload` y no `upsert`: los vectores ya están guardados y no se tocan.
    """
    if not ids:
        return
    payloads = await leer_payloads(ids)
    for tender_id in ids:
        payload = payloads.get(tender_id)
        if not payload:
            resumen.sin_payload += 1
            continue
        await item_repo.set_payload(tender_id, payload)
        resumen.payloads_copiados += 1


async def _grupos_pendientes(
    leer_pagina: LectorDePaginas,
    item_repo: ITenderItemVectorRepository,
    tamano_grupo: int,
    limite: int | None,
    resumen: Resumen,
    ya_indexadas: AlEncontrarIndexadas | None = None,
) -> AsyncIterator[list[LicitacionConTextos]]:
    """Recorre el corpus y entrega, grupo a grupo, lo que falta por indexar.

    Por sí mismo solo lee: no escribe en ningún lado, así que lo comparten la
    carga y `--solo-contar`. Una página entera ya hecha no es señal de fin
    (reanudar pasa por muchas): el recorrido termina cuando el lector devuelve una
    página corta. `limite` acota cuántas licitaciones se entregan en la corrida.

    `ya_indexadas`, si se entrega, recibe por cada página los ids que ya tienen
    vectores: es por donde la carga les completa el payload sin que este recorrido
    tenga que saber de escrituras.
    """
    despues_de: uuid.UUID | None = None
    entregadas = 0
    while True:
        pagina = await leer_pagina(despues_de, tamano_grupo)
        if not pagina:
            return

        existentes = set(await item_repo.get_many([tender_id for tender_id, _ in pagina]))
        pendientes = _clasificar(pagina, existentes, resumen)
        if ya_indexadas is not None:
            await ya_indexadas(
                [tender_id for tender_id, _ in pagina if tender_id in existentes]
            )

        if limite is not None:
            pendientes = pendientes[: limite - entregadas]
        if pendientes:
            entregadas += len(pendientes)
            yield pendientes
        if limite is not None and entregadas >= limite:
            return
        if len(pagina) < tamano_grupo:
            return
        despues_de = pagina[-1][0]


async def procesar(
    leer_pagina: LectorDePaginas,
    embedding: IEmbeddingService | None,
    item_repo: ITenderItemVectorRepository,
    tamano_grupo: int,
    tamano_lote: int,
    limite: int | None,
    *,
    leer_payloads: LectorDePayloads | None = None,
    solo_payload: bool = False,
    en_progreso: Callable[[Resumen], None] | None = None,
) -> Resumen:
    """Indexa lo que falte, completa los payloads y devuelve qué hizo.

    Con `leer_payloads`, además de indexar copia el payload de "tenders" a las que
    ya tenían vectores y sube las nuevas con el suyo. Sin él no toca payloads.

    Con `solo_payload` solo copia payloads: no embebe (por eso `embedding` puede
    ser `None`, y el modelo ni siquiera se carga) ni indexa las que faltan, que se
    cuentan como pendientes. `limite` no aplica en ese modo: acota lo que se indexa.
    """
    if not solo_payload and embedding is None:
        raise ValueError("Falta el servicio de embeddings (embedding) para indexar.")
    if solo_payload and leer_payloads is None:
        raise ValueError("--solo-payload necesita un lector de payloads (leer_payloads).")

    resumen = Resumen()

    async def completar_payload(ids: list[uuid.UUID]) -> None:
        if leer_payloads is not None:
            await _copiar_payloads(ids, item_repo, leer_payloads, resumen)
        # En modo solo-payload no hay grupos que indexar, así que esta es la única
        # señal de avance de la corrida.
        if solo_payload and en_progreso is not None:
            en_progreso(resumen)

    async for grupo in _grupos_pendientes(
        leer_pagina,
        item_repo,
        tamano_grupo,
        None if solo_payload else limite,
        resumen,
        ya_indexadas=completar_payload,
    ):
        if solo_payload:
            continue
        assert embedding is not None  # garantizado por la guarda del inicio

        payloads: dict[uuid.UUID, dict] = {}
        if leer_payloads is not None:
            ids = [tender_id for tender_id, _ in grupo]
            payloads = await leer_payloads(ids)
            resumen.sin_payload += sum(1 for i in ids if i not in payloads)

        resumen.indexadas += await _indexar_grupo(
            embedding, item_repo, grupo, tamano_lote, payloads
        )
        if en_progreso is not None:
            en_progreso(resumen)
    return resumen


def _lector_sql(engine: AsyncEngine, incluir_cerradas: bool) -> LectorDePaginas:
    """Lee de Postgres las licitaciones con los textos de sus partidas.

    Los textos salen de `TextBuilder.build_item_texts`, el mismo que usan la
    ingesta y el scorer: si difirieran, el vector guardado no coincidiría con el
    que se calcularía al vuelo para la misma licitación.
    """
    text_builder = TextBuilder()

    async def leer_pagina(
        despues_de: uuid.UUID | None, tamano: int
    ) -> list[LicitacionConTextos]:
        stmt = (
            select(TenderModel)
            .options(selectinload(TenderModel.items))  # type: ignore[arg-type]
            .order_by(col(TenderModel.id))
            .limit(tamano)
        )
        if despues_de is not None:
            stmt = stmt.where(col(TenderModel.id) > despues_de)
        if not incluir_cerradas:
            stmt = stmt.where(
                col(TenderModel.status_id) == PUBLICADA_STATUS_ID,
                col(TenderModel.closing_at) > utc_now_naive(),
            )

        async with AsyncSession(engine) as session:
            licitaciones = (await session.exec(stmt)).all()
            return [
                (t.id, text_builder.build_item_texts(t.items or []))
                for t in licitaciones
            ]

    return leer_pagina


def _conectar() -> tuple[AsyncEngine, AsyncQdrantClient]:
    engine = create_async_engine(settings.database_url, echo=False)
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return engine, qdrant


def _imprimir_resumen(resumen: Resumen, *, con_payloads: bool = True) -> None:
    print(f"  licitaciones revisadas   : {resumen.revisadas}")
    print(f"  ya tenían vectores       : {resumen.ya_indexadas}")
    print(f"  sin partidas (se omiten) : {resumen.sin_partidas}")
    print(f"  por indexar              : {resumen.pendientes}")
    print(f"  textos a embeber         : {resumen.textos}")
    if con_payloads:
        print(f"  payloads copiados        : {resumen.payloads_copiados}")
        print(f"  sin payload en tenders   : {resumen.sin_payload}")


async def contar(args: argparse.Namespace) -> None:
    """Cuántas faltan y cuántos textos hay que embeber. No escribe ni carga el modelo."""
    engine, qdrant = _conectar()
    try:
        repo = QdrantTenderItemVectorRepository(
            client=qdrant, vector_size=settings.embedding_vector_size
        )
        resumen = Resumen()
        async for _ in _grupos_pendientes(
            _lector_sql(engine, args.incluir_cerradas),
            repo,
            LICITACIONES_POR_GRUPO,
            args.limite,
            resumen,
        ):
            pass
        print("Diagnóstico (no se escribió nada):")
        _imprimir_resumen(resumen, con_payloads=False)
    finally:
        await engine.dispose()
        await qdrant.close()


async def cargar(args: argparse.Namespace) -> None:
    # Con --solo-payload no se necesita el modelo: ni se importa ni se construye,
    # que es lo que hace barata esa corrida.
    embedding: IEmbeddingService | None = None
    if not args.solo_payload:
        from app.bootstrap import build_embedding_service

        embedding = build_embedding_service()
        _exigir_embedding_real(embedding)

    engine, qdrant = _conectar()
    try:
        repo = QdrantTenderItemVectorRepository(
            client=qdrant, vector_size=settings.embedding_vector_size
        )
        # Idempotente. Normalmente lo hace el arranque de la aplicación, pero este
        # script puede correr contra un Qdrant donde todavía no ha arrancado.
        await repo.ensure_collection()

        t0 = time.perf_counter()

        def en_progreso(resumen: Resumen) -> None:
            print(
                f"  {resumen.indexadas} licitaciones indexadas, "
                f"{resumen.payloads_copiados} payloads copiados "
                f"({time.perf_counter() - t0:.0f} s)"
            )

        resumen = await procesar(
            _lector_sql(engine, args.incluir_cerradas),
            embedding,
            repo,
            tamano_grupo=LICITACIONES_POR_GRUPO,
            tamano_lote=args.tamano_lote,
            limite=args.limite,
            leer_payloads=_lector_payloads(qdrant),
            solo_payload=args.solo_payload,
            en_progreso=en_progreso,
        )
        print(f"\nListo en {(time.perf_counter() - t0) / 60:.1f} min.")
        _imprimir_resumen(resumen)
        print(f"  indexadas ahora          : {resumen.indexadas}")
        if args.solo_payload and resumen.pendientes:
            print(
                f"  ({resumen.pendientes} sin vectores siguen pendientes: "
                "--solo-payload no las indexa)"
            )
    finally:
        await engine.dispose()
        await qdrant.close()


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--solo-contar",
        action="store_true",
        help="diagnóstico: cuántas faltan; no carga el modelo ni escribe",
    )
    p.add_argument(
        "--solo-payload",
        action="store_true",
        help="solo copia el payload de tenders a las partidas ya indexadas; no "
        "carga el modelo ni indexa las que faltan",
    )
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        help="tope de licitaciones a indexar en esta corrida (para probar)",
    )
    p.add_argument(
        "--tamano-lote",
        type=int,
        default=TAMANO_LOTE_EMBEDDING,
        help=f"textos por llamada al modelo ({TAMANO_LOTE_EMBEDDING}); subirlo "
        "arriesga quedarse sin memoria con partidas largas",
    )
    p.add_argument(
        "--incluir-cerradas",
        action="store_true",
        help="recorrer también las licitaciones cerradas (por defecto solo abiertas)",
    )
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base o Qdrant no son locales",
    )
    args = p.parse_args()

    if args.tamano_lote < 1:
        sys.exit("--tamano-lote tiene que ser al menos 1.")
    if args.solo_payload and args.solo_contar:
        sys.exit("--solo-payload y --solo-contar son excluyentes: el primero escribe.")
    if args.solo_payload and args.limite is not None:
        sys.exit(
            "--limite no aplica con --solo-payload: acota lo que se indexa, y ese "
            "modo no indexa nada."
        )

    print(f"Base de datos : {urlsplit(settings.database_url).hostname}")
    print(f"Qdrant        : {urlsplit(settings.qdrant_url).hostname}")
    print(f"Embeddings    : {settings.embedding_provider}\n")

    if not args.solo_contar:
        destinos = _destinos_no_locales(settings.database_url, settings.qdrant_url)
        if destinos:
            if not args.confirmar_produccion:
                sys.exit(
                    f"Se escribiría contra {' y '.join(destinos)}, que no es local, "
                    "y falta --confirmar-produccion.\n"
                    "Hacerlo contra producción es deliberado, no algo que deba pasar "
                    "por olvidar una variable de entorno."
                )
            print("!! Escribiendo contra un destino NO local !!\n")

    asyncio.run(contar(args) if args.solo_contar else cargar(args))


if __name__ == "__main__":
    main()
