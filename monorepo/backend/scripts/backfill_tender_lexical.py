"""Vectores dispersos (sparse BM25) para las licitaciones en Qdrant (plan 256).

Indexa las licitaciones en la colección `tender_lexical` de Qdrant utilizando
`LexicalTokenizer` (sparse vectors BM25 con modifier=IDF) para habilitar el canal
léxico complementario del motor de matching.

Payload para pre-filtros
------------------------
Cada punto de `tender_lexical` lleva el mismo payload que el de la licitación en
`tenders` (estado, región, provincia, comuna, monto, fechas epoch): permite pre-filtrar
directamente dentro de la búsqueda sparse de Qdrant.

El script copia el payload desde `tenders` si existe; si no existe allá, lo construye
a partir de los campos de SQL (`TenderModel`).

Idempotencia
------------
Por defecto omite las licitaciones que ya tienen punto en `tender_lexical`. Con `--forzar`
recalcula y sobreescribe los vectores dispersos.

Uso
---
    # Diagnóstico: cuántas faltan por indexar en tender_lexical
    python -m scripts.backfill_tender_lexical --solo-contar

    # Prueba con 20 licitaciones
    python -m scripts.backfill_tender_lexical --limite 20

    # Corrida completa para licitaciones activas
    python -m scripts.backfill_tender_lexical

    # Forzar re-indexación de todas
    python -m scripts.backfill_tender_lexical --forzar
"""

import argparse
import asyncio
import sys
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.services.lexical_tokenizer import LexicalTokenizer
from app.application.services.text_builder import TextBuilder
from app.config import settings
from app.infrastructure.repositories.qdrant_lexical_tender_repository import (
    QdrantLexicalTenderRepository,
)
from app.infrastructure.repositories.qdrant_tender_filters import PAYLOAD_INDEXES
from app.infrastructure.repositories.tender_model import TenderModel
from app.shared.constants import PUBLICADA_STATUS_ID, TENDER_STATUS_CODE_BY_ID
from app.shared.datetime_utils import to_utc_epoch, utc_now_naive

HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "db"}
LICITACIONES_POR_GRUPO = 100
COLECCION_LICITACIONES = "tenders"
COLECCION_LEXICAL = "tender_lexical"


@dataclass
class Resumen:
    revisadas: int = 0
    ya_indexadas: int = 0
    pendientes: int = 0
    indexadas: int = 0
    payloads_copiados: int = 0
    payloads_generados_sql: int = 0


def _es_local(url: str) -> bool:
    return (urlsplit(url).hostname or "") in HOSTS_LOCALES


def _destinos_no_locales(database_url: str, qdrant_url: str) -> list[str]:
    destinos = []
    if not _es_local(database_url):
        destinos.append(f"la base de datos ({urlsplit(database_url).hostname})")
    if not _es_local(qdrant_url):
        destinos.append(f"Qdrant ({urlsplit(qdrant_url).hostname})")
    return destinos


def _conectar() -> tuple[AsyncEngine, AsyncQdrantClient]:
    engine = create_async_engine(settings.database_url, echo=False)
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return engine, qdrant


async def _leer_payloads_tenders(
    qdrant: AsyncQdrantClient, ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    """Recupera los payloads ya existentes en la colección 'tenders'."""
    str_ids = [str(i) for i in ids]
    try:
        puntos = await qdrant.retrieve(
            collection_name=COLECCION_LICITACIONES,
            ids=str_ids,
            with_payload=True,
            with_vectors=False,
        )
    except Exception:
        return {}

    resultado: dict[uuid.UUID, dict] = {}
    for p in puntos:
        if p.payload:
            filtrado = {k: p.payload[k] for k in PAYLOAD_INDEXES if k in p.payload}
            resultado[uuid.UUID(str(p.id))] = filtrado
    return resultado


async def _consultar_existentes_lexical(
    qdrant: AsyncQdrantClient, ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Detecta qué licitaciones ya tienen punto en 'tender_lexical'."""
    str_ids = [str(i) for i in ids]
    try:
        puntos = await qdrant.retrieve(
            collection_name=COLECCION_LEXICAL,
            ids=str_ids,
            with_payload=False,
            with_vectors=False,
        )
        return {uuid.UUID(str(p.id)) for p in puntos}
    except Exception:
        return set()


def _payload_desde_sql(tender: TenderModel) -> dict:
    """Fallback si la licitación no tenía punto previo en 'tenders'."""
    status_code = TENDER_STATUS_CODE_BY_ID.get(tender.status_id, "desconocido")
    return {
        "status_code": status_code,
        "region_id": None,
        "provincia_id": None,
        "comuna_id": None,
        "available_amount_clp": tender.available_amount_clp,
        "closing_at": to_utc_epoch(tender.closing_at),
        "published_at": to_utc_epoch(tender.published_at),
    }


async def procesar_backfill(
    engine: AsyncEngine,
    qdrant: AsyncQdrantClient,
    repo: QdrantLexicalTenderRepository,
    tokenizer: LexicalTokenizer,
    text_builder: TextBuilder,
    *,
    incluir_cerradas: bool = False,
    forzar: bool = False,
    limite: int | None = None,
    solo_contar: bool = False,
) -> Resumen:
    resumen = Resumen()
    despues_de: uuid.UUID | None = None
    procesadas_total = 0

    while True:
        stmt = (
            select(TenderModel)
            .options(selectinload(TenderModel.items))  # type: ignore[arg-type]
            .order_by(col(TenderModel.id))
            .limit(LICITACIONES_POR_GRUPO)
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

        if not licitaciones:
            break

        resumen.revisadas += len(licitaciones)
        ids_grupo = [t.id for t in licitaciones]

        # Verificar qué IDs ya existen en Qdrant lexical
        existentes = (
            set() if forzar else await _consultar_existentes_lexical(qdrant, ids_grupo)
        )
        resumen.ya_indexadas += len(existentes)

        pendientes = [t for t in licitaciones if t.id not in existentes]
        resumen.pendientes += len(pendientes)

        if not solo_contar and pendientes:
            # Obtener payloads desde tenders
            payloads = await _leer_payloads_tenders(
                qdrant, [t.id for t in pendientes]
            )

            for tender in pendientes:
                if limite is not None and procesadas_total >= limite:
                    break

                text = text_builder.build_from_tender(tender, tender.items or [])
                sparse_vec = tokenizer.encode_sparse(text)

                if tender.id in payloads:
                    payload = payloads[tender.id]
                    resumen.payloads_copiados += 1
                else:
                    payload = _payload_desde_sql(tender)
                    resumen.payloads_generados_sql += 1

                await repo.upsert(tender.id, sparse_vec, payload)
                resumen.indexadas += 1
                procesadas_total += 1

                if limite is not None and procesadas_total >= limite:
                    return resumen

        despues_de = licitaciones[-1].id
        if len(licitaciones) < LICITACIONES_POR_GRUPO:
            break

    return resumen


def _imprimir_resumen(resumen: Resumen, solo_contar: bool = False) -> None:
    print(f"  licitaciones revisadas    : {resumen.revisadas}")
    print(f"  ya indexadas en léxico    : {resumen.ya_indexadas}")
    print(f"  por indexar               : {resumen.pendientes}")
    if not solo_contar:
        print(f"  indexadas ahora           : {resumen.indexadas}")
        print(f"  payloads desde tenders    : {resumen.payloads_copiados}")
        print(f"  payloads generados SQL    : {resumen.payloads_generados_sql}")


async def ejecutar(args: argparse.Namespace) -> None:
    engine, qdrant = _conectar()
    try:
        repo = QdrantLexicalTenderRepository(client=qdrant)
        if not args.solo_contar:
            await repo.ensure_collection()

        tokenizer = LexicalTokenizer()
        text_builder = TextBuilder()

        t0 = time.perf_counter()
        resumen = await procesar_backfill(
            engine,
            qdrant,
            repo,
            tokenizer,
            text_builder,
            incluir_cerradas=args.incluir_cerradas,
            forzar=args.forzar,
            limite=args.limite,
            solo_contar=args.solo_contar,
        )
        t_total = time.perf_counter() - t0

        if args.solo_contar:
            print("\nDiagnóstico de backfill léxico (no se escribió nada):")
            _imprimir_resumen(resumen, solo_contar=True)
        else:
            print(f"\nBackfill léxico finalizado en {t_total:.2f} s.")
            _imprimir_resumen(resumen, solo_contar=False)
    finally:
        await engine.dispose()
        await qdrant.close()


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--solo-contar",
        action="store_true",
        help="diagnóstico: cuántas faltan por indexar en tender_lexical",
    )
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        help="tope de licitaciones a indexar en esta corrida",
    )
    p.add_argument(
        "--incluir-cerradas",
        action="store_true",
        help="recorrer también las licitaciones cerradas (por defecto solo activas)",
    )
    p.add_argument(
        "--forzar",
        action="store_true",
        help="re-indexar incluso si la licitación ya existe en tender_lexical",
    )
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base o Qdrant no son locales",
    )
    args = p.parse_args()

    print(f"Base de datos : {urlsplit(settings.database_url).hostname}")
    print(f"Qdrant        : {urlsplit(settings.qdrant_url).hostname}")
    print(f"Colección     : {COLECCION_LEXICAL}\n")

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

    asyncio.run(ejecutar(args))


if __name__ == "__main__":
    main()
