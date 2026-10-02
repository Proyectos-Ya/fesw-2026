"""Genera los embeddings de las licitaciones cargadas y las indexa en Qdrant.

Segundo paso del Modo A. Antes hay que correr:

    python tests/matching_evaluation/load_postgres_robust.py

y después:

    python tests/matching_evaluation/load_dataset.py

Lee de Postgres, no del xlsx: así lo indexado es exactamente lo que la aplicación
tiene, sin una segunda interpretación del dataset.

**Usa los mismos servicios que la ingesta real** —`TextBuilder`,
`BgeM3EmbeddingService` y `QdrantTenderRepository`— en vez de reimplementar el
texto, el vector o el payload. Una copia paralela se desincroniza en cuanto
alguien toca el original, y el síntoma sería un matching que empeora sin causa
visible.

**Es reanudable**: lo que ya está en Qdrant se omite (`--reindexar` lo fuerza), así
que cargar un catálogo nuevo sobre uno existente solo calcula lo que falta y una
caída a medias no obliga a empezar de cero.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from qdrant_client import AsyncQdrantClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.application.services.text_builder import TextBuilder  # noqa: E402
from app.config import settings  # noqa: E402
from app.infrastructure.db import engine  # noqa: E402
from app.infrastructure.repositories.qdrant_tender_repository import (  # noqa: E402
    QdrantTenderRepository,
)
from app.infrastructure.services.bge_m3_embedding_service import (  # noqa: E402
    BgeM3EmbeddingService,
)
from app.shared.constants import TENDER_STATUS_CODE_BY_ID  # noqa: E402
from app.shared.datetime_utils import to_utc_epoch  # noqa: E402

# Textos por llamada al modelo. Con lotes más grandes BGE-M3 rellena todo el lote hasta
# el texto más largo —hay partidas de más de 10.000 caracteres— y el proceso muere por
# memoria sin dejar un mensaje. Ordenados de corto a largo, los lotes chicos casi no
# rellenan.
LOTE = 8


@dataclass
class _Simple:
    """Objeto mínimo con los atributos que `TextBuilder` lee."""

    name: str
    description: str | None = None


def seleccionar_pendientes(
    textos: dict[UUID, str], ya_indexadas: set[UUID], reindexar: bool = False
) -> list[UUID]:
    """Ids a indexar, del texto más corto al más largo.

    Se omiten los que ya están en Qdrant, salvo con `reindexar`. El orden por largo
    agrupa textos parecidos en cada lote y deja para el final los que más memoria
    piden, de modo que una caída por memoria se nota cuando ya hay casi todo hecho.
    """
    ids = [i for i in textos if reindexar or i not in ya_indexadas]
    return sorted(ids, key=lambda i: len(textos[i]))


async def _ids_ya_indexados(
    cliente: AsyncQdrantClient, ids: list[UUID], coleccion: str = "tenders"
) -> set[UUID]:
    """Cuáles de estos ids ya tienen punto en la colección (consulta por lotes)."""
    existentes: set[UUID] = set()
    for inicio in range(0, len(ids), 256):
        puntos = await cliente.retrieve(
            collection_name=coleccion,
            ids=[str(i) for i in ids[inicio : inicio + 256]],
            with_payload=False,
            with_vectors=False,
        )
        existentes.update(UUID(str(p.id)) for p in puntos)
    return existentes


async def _leer_licitaciones() -> list[dict]:
    # `comuna_id` es directo en `buyer_institution`; `provincia_id` sale de un
    # salto más a través de `comuna` (no hay FK propia a provincia). LEFT JOIN
    # porque no todos los organismos tienen comuna resuelta.
    consulta = text("""
        SELECT t.id, t.name, t.description, t.status_id, t.closing_at,
               t.published_at, t.available_amount_clp, b.region_id,
               b.comuna_id, c.provincia_id,
               ti.name AS item_name, ti.description AS item_description
        FROM tender t
        LEFT JOIN buyer_institution b ON b.rut = t.buyer_rut
        LEFT JOIN comuna c ON c.id = b.comuna_id
        LEFT JOIN tender_item ti ON ti.tender_id = t.id
        ORDER BY t.id
    """)
    async with engine.connect() as conn:
        filas = (await conn.execute(consulta)).mappings().all()

    # Una fila por partida: se agrupan para no repetir la licitación.
    por_id: dict = {}
    for f in filas:
        actual = por_id.setdefault(
            f["id"],
            {
                "id": f["id"],
                "name": f["name"] or "",
                "description": f["description"],
                "status_id": f["status_id"],
                "closing_at": f["closing_at"],
                "published_at": f["published_at"],
                "available_amount_clp": f["available_amount_clp"],
                "region_id": f["region_id"],
                "comuna_id": f["comuna_id"],
                "provincia_id": f["provincia_id"],
                "items": [],
            },
        )
        if f["item_name"]:
            actual["items"].append(
                _Simple(name=f["item_name"], description=f["item_description"])
            )
    return list(por_id.values())


async def main(reindexar: bool = False) -> None:
    licitaciones = await _leer_licitaciones()
    if not licitaciones:
        raise SystemExit(
            "No hay licitaciones en la base. Corre primero:\n"
            "  python tests/matching_evaluation/load_postgres_robust.py"
        )
    print(f"[DB] {len(licitaciones)} licitaciones en la base", flush=True)

    constructor = TextBuilder()
    embeddings = BgeM3EmbeddingService()
    cliente = AsyncQdrantClient(url=settings.qdrant_url, timeout=60.0)
    repositorio = QdrantTenderRepository(
        client=cliente, vector_size=settings.embedding_vector_size
    )

    # Crea la colección y, sobre todo, los índices de payload que el pre-filtrado
    # del buscador necesita. Sin ellos el filtro por fecha o monto no funciona.
    await repositorio.ensure_collection()

    por_id = {t["id"]: t for t in licitaciones}
    textos = {
        i: constructor.build_from_tender(
            tender=_Simple(name=t["name"], description=t["description"]), items=t["items"]
        )
        for i, t in por_id.items()
    }
    ya = set() if reindexar else await _ids_ya_indexados(cliente, list(textos))
    pendientes = seleccionar_pendientes(textos, ya, reindexar)
    print(
        f"[QDRANT] {len(ya)} ya indexadas (se omiten) | {len(pendientes)} por indexar",
        flush=True,
    )

    indexadas = 0
    for inicio in range(0, len(pendientes), LOTE):
        ids = pendientes[inicio : inicio + LOTE]
        vectores = await embeddings.embed([textos[i] for i in ids])

        for i, vector in zip(ids, vectores, strict=True):
            t = por_id[i]
            await repositorio.upsert(
                tender_id=i,
                embedding=vector,
                payload={
                    # El código semántico, no el numérico: es contra lo que
                    # filtra el matching.
                    "status_code": TENDER_STATUS_CODE_BY_ID.get(t["status_id"]),
                    "region_id": t["region_id"],
                    "provincia_id": t["provincia_id"],
                    "comuna_id": t["comuna_id"],
                    "available_amount_clp": t["available_amount_clp"],
                    # Epoch entero: Qdrant no compara `datetime`.
                    "closing_at": to_utc_epoch(t["closing_at"]),
                    "published_at": to_utc_epoch(t["published_at"]),
                },
            )
            indexadas += 1

        # Una línea nueva cada ~100 y no sobrescribir la misma: en un log o en un
        # pegado la sobrescritura borra el progreso, y cuando el proceso muere no
        # queda rastro de hasta dónde llegó.
        if indexadas % 96 < LOTE or inicio + LOTE >= len(pendientes):
            print(f"  {indexadas}/{len(pendientes)}", flush=True)

    total = await repositorio.count()
    print(f"\n[LISTO] {total} licitaciones indexadas en Qdrant.", flush=True)

    await cliente.close()
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--reindexar",
        action="store_true",
        help="vuelve a calcular también lo que ya está en Qdrant",
    )
    args = parser.parse_args()
    asyncio.run(main(reindexar=args.reindexar))
