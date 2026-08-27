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
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

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

LOTE = 32


@dataclass
class _Simple:
    """Objeto mínimo con los atributos que `TextBuilder` lee."""

    name: str
    description: str | None = None


async def _leer_licitaciones() -> list[dict]:
    consulta = text("""
        SELECT t.id, t.name, t.description, t.status_id, t.closing_at,
               t.published_at, t.available_amount_clp, b.region_id,
               ti.name AS item_name, ti.description AS item_description
        FROM tender t
        LEFT JOIN buyer_institution b ON b.rut = t.buyer_rut
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
                "items": [],
            },
        )
        if f["item_name"]:
            actual["items"].append(
                _Simple(name=f["item_name"], description=f["item_description"])
            )
    return list(por_id.values())


async def main() -> None:
    licitaciones = await _leer_licitaciones()
    if not licitaciones:
        raise SystemExit(
            "No hay licitaciones en la base. Corre primero:\n"
            "  python tests/matching_evaluation/load_postgres_robust.py"
        )
    print(f"[DB] {len(licitaciones)} licitaciones por indexar", flush=True)

    constructor = TextBuilder()
    embeddings = BgeM3EmbeddingService()
    cliente = AsyncQdrantClient(url=settings.qdrant_url)
    repositorio = QdrantTenderRepository(
        client=cliente, vector_size=settings.embedding_vector_size
    )

    # Crea la colección y, sobre todo, los índices de payload que el pre-filtrado
    # del buscador necesita. Sin ellos el filtro por fecha o monto no funciona.
    await repositorio.ensure_collection()

    indexadas = 0
    for inicio in range(0, len(licitaciones), LOTE):
        lote = licitaciones[inicio : inicio + LOTE]
        textos = [
            constructor.build_from_tender(
                tender=_Simple(name=t["name"], description=t["description"]),
                items=t["items"],
            )
            for t in lote
        ]
        vectores = await embeddings.embed(textos)

        for t, vector in zip(lote, vectores, strict=True):
            await repositorio.upsert(
                tender_id=t["id"],
                embedding=vector,
                payload={
                    # El código semántico, no el numérico: es contra lo que
                    # filtra el matching.
                    "status_code": TENDER_STATUS_CODE_BY_ID.get(t["status_id"]),
                    "region_id": t["region_id"],
                    "available_amount_clp": t["available_amount_clp"],
                    # Epoch entero: Qdrant no compara `datetime`.
                    "closing_at": to_utc_epoch(t["closing_at"]),
                    "published_at": to_utc_epoch(t["published_at"]),
                },
            )
            indexadas += 1

        print(f"  {indexadas}/{len(licitaciones)}", end="\r", flush=True)

    total = await repositorio.count()
    print(f"\n[LISTO] {total} licitaciones indexadas en Qdrant.", flush=True)

    await cliente.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
