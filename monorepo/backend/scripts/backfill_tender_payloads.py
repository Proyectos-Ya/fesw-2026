"""Backfill: reescribe el payload de los puntos de Qdrant desde Postgres.

Contexto
--------
El pre-filtrado del buscador manual (HdU 07) se apoya en el payload de Qdrant: es
ahí donde se aplican región, estado, monto y rango de fechas **durante** la
búsqueda vectorial. Post-filtrar después del top-K no sirve — con un filtro que
deja pasar el 4% del corpus, un top-50 devuelve ~2 resultados habiendo cientos
que califican.

Los puntos indexados antes de este cambio traen solo `status_code`, `region_id` y
`available_amount_clp`. Sin `closing_at` ni `published_at` no pasan ningún filtro
de fecha, así que quedarían invisibles para cualquier búsqueda que acote por
plazo. Lo mismo pasa con `provincia_id`/`comuna_id`: las licitaciones ingeridas
antes de agregar el filtro de provincia/comuna no tienen esos campos en el
payload, así que no calzan con ningún filtro por esas dos condiciones aunque su
`buyer_institution.comuna_id` sí esté resuelto en Postgres.

No recalcula embeddings: `set_payload` actualiza solo los metadatos, de modo que
la corrida es barata y repetible. Postgres es la fuente de verdad; Qdrant se
alinea a él.

Uso
---
    python -m scripts.backfill_tender_payloads --dry-run   # muestra sin escribir
    python -m scripts.backfill_tender_payloads             # aplica

Los puntos sin fila en SQL se reportan pero no se tocan: de esos se encarga la
limpieza de huérfanos de `rank_tenders` (ver check_tender_vector_orphans.py).
"""

import argparse
import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.shared.constants import TENDER_STATUS_CODE_BY_ID
from app.shared.datetime_utils import to_utc_epoch

_COLLECTION = "tenders"

# Qdrant limita el tamaño de cada retrieve; 500 mantiene bajo el número de viajes
# sin construir respuestas enormes.
_BATCH_SIZE = 500

# `region_id` vive en la institución compradora, no en la licitación.
# `comuna_id` es directo en `buyer_institution`; `provincia_id` sale de un
# salto más a través de `comuna` (`buyer_institution` no tiene FK propia a
# provincia). Ambos LEFT JOIN porque `comuna_id` puede ser NULL: no todos los
# organismos se resuelven (ver app/shared/comunas.py).
_SELECT_TENDERS = text("""
    SELECT t.id,
           t.code,
           t.status_id,
           t.closing_at,
           t.published_at,
           t.available_amount_clp,
           b.region_id,
           b.comuna_id,
           c.provincia_id
    FROM tender t
    JOIN buyer_institution b ON b.rut = t.buyer_rut
    LEFT JOIN comuna c ON c.id = b.comuna_id
""")


@dataclass
class Stats:
    en_sql: int = 0
    actualizados: int = 0
    sin_punto: list[str] = field(default_factory=list)
    fallidos: list[str] = field(default_factory=list)


def _build_payload(row) -> dict:
    """Construye el mismo payload que escribe la ingesta.

    Mantener ambos en sintonía es responsabilidad de quien toque uno de los dos;
    si divergen, el corpus queda con puntos filtrables de forma distinta según
    cuándo se indexaron.
    """
    return {
        "status_code": TENDER_STATUS_CODE_BY_ID.get(row.status_id),
        "region_id": row.region_id,
        "provincia_id": row.provincia_id,
        "comuna_id": row.comuna_id,
        "available_amount_clp": row.available_amount_clp,
        "closing_at": to_utc_epoch(row.closing_at),
        "published_at": to_utc_epoch(row.published_at),
    }


async def _existing_point_ids(client: AsyncQdrantClient, ids: list[UUID]) -> set[str]:
    """IDs que efectivamente están en Qdrant, consultados por lotes."""
    encontrados: set[str] = set()
    for i in range(0, len(ids), _BATCH_SIZE):
        lote = [str(u) for u in ids[i : i + _BATCH_SIZE]]
        puntos = await client.retrieve(
            collection_name=_COLLECTION,
            ids=lote,  # type: ignore[arg-type]
            with_payload=False,
            with_vectors=False,
        )
        encontrados.update(str(p.id) for p in puntos)
    return encontrados


async def run(dry_run: bool) -> Stats:
    stats = Stats()
    engine = create_async_engine(settings.database_url)
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    try:
        async with engine.connect() as conn:
            filas = (await conn.execute(_SELECT_TENDERS)).all()

        stats.en_sql = len(filas)
        if not filas:
            return stats

        # Los índices de payload son condición para que el filtrado rinda; si el
        # entorno nunca arrancó la app con este cambio, no existen todavía.
        if not dry_run:
            await QdrantTenderRepository(
                client=client, vector_size=settings.embedding_vector_size
            ).ensure_collection()

        presentes = await _existing_point_ids(client, [f.id for f in filas])

        for fila in filas:
            punto_id = str(fila.id)
            if punto_id not in presentes:
                stats.sin_punto.append(fila.code)
                continue

            payload = _build_payload(fila)
            if dry_run:
                stats.actualizados += 1
                print(f"  [dry-run] {fila.code}: {payload}")
                continue

            try:
                await client.set_payload(
                    collection_name=_COLLECTION,
                    payload=payload,
                    points=[punto_id],  # type: ignore[arg-type]
                    wait=True,
                )
                stats.actualizados += 1
            except Exception as exc:
                stats.fallidos.append(f"{fila.code}: {type(exc).__name__}: {exc}")
    finally:
        await client.close()
        await engine.dispose()

    return stats


def _report(stats: Stats, dry_run: bool) -> None:
    modo = "DRY-RUN (no se escribió nada)" if dry_run else "APLICADO"
    print(f"\n=== Backfill de payloads — {modo} ===")
    print(f"  licitaciones en Postgres : {stats.en_sql}")
    print(f"  payloads actualizados    : {stats.actualizados}")
    print(f"  sin punto en Qdrant      : {len(stats.sin_punto)}")

    if stats.sin_punto:
        muestra = ", ".join(stats.sin_punto[:10])
        resto = "" if len(stats.sin_punto) <= 10 else f" (+{len(stats.sin_punto) - 10})"
        print(f"    {muestra}{resto}")
        print("    → son licitaciones sin vector; ver check_tender_vector_orphans")

    if stats.fallidos:
        print(f"  fallidos                 : {len(stats.fallidos)}")
        for f in stats.fallidos[:10]:
            print(f"    {f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los payloads que se escribirían, sin tocar Qdrant.",
    )
    args = parser.parse_args()

    stats = asyncio.run(run(dry_run=args.dry_run))
    _report(stats, dry_run=args.dry_run)
    return 1 if stats.fallidos else 0


if __name__ == "__main__":
    raise SystemExit(main())
