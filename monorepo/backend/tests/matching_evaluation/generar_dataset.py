"""Trae compras ágiles frescas desde Mercado Público para armar un dataset.

Primer paso para **regenerar** el dataset de prueba. El ciclo completo:

    # 1. Una persona, una vez (consume cuota del ticket):
    python tests/matching_evaluation/generar_dataset.py --limite 300
    python tests/matching_evaluation/export_dataset.py

    # 2. El resto del equipo (cuota: cero):
    python tests/matching_evaluation/load_postgres_robust.py
    python tests/matching_evaluation/load_dataset.py

Por qué hace falta regenerarlo: el dataset se llena de licitaciones **cerradas**.
El matching descarta todo lo que tenga `closing_at` en el pasado, así que un
volcado de hace unas semanas deja el dashboard vacío aunque la base tenga miles
de filas. Conviene rehacerlo cuando eso pase.

Usa los mismos servicios que la ingesta de producción —no una copia paralela—,
así que lo que queda en la base es exactamente lo que la aplicación habría
guardado.
"""

import argparse
import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from qdrant_client import AsyncQdrantClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.infrastructure.db import engine  # noqa: E402
from app.infrastructure.repositories.qdrant_tender_repository import (  # noqa: E402
    QdrantTenderRepository,
)
from app.infrastructure.services.bge_m3_embedding_service import (  # noqa: E402
    BgeM3EmbeddingService,
)
from app.infrastructure.services.tenders.mercado_publico_client import (  # noqa: E402
    MercadoPublicoClient,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (  # noqa: E402
    TenderIngestionService,
)


async def _contar(consulta: str) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(text(consulta))).scalar_one()


async def main(limite: int, retardo: float) -> None:
    # El servicio lee estos dos de la configuración global; se sobrescriben acá
    # para no obligar a editar el .env solo para generar el dataset.
    settings.mercadopublico_fetching_limit = limite
    settings.mercadopublico_detail_delay = retardo

    estimado = limite * retardo / 60
    print(
        f"[PLAN] Hasta {limite} compras ágiles, {retardo}s entre detalles.\n"
        f"       Costo aproximado: {limite + limite // 50} peticiones de las "
        f"10.000 diarias del ticket, ~{estimado:.0f} min.",
        flush=True,
    )

    qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    repositorio = QdrantTenderRepository(
        client=qdrant, vector_size=settings.embedding_vector_size
    )
    await repositorio.ensure_collection()

    servicio = TenderIngestionService(
        engine=engine,
        client=MercadoPublicoClient(api_key=settings.mercado_publico_api_key),
        embedding_service=BgeM3EmbeddingService(),
        qdrant_client=qdrant,
        tender_vector_repo=repositorio,
    )

    print("\n[FASE 1] Encolando licitaciones recientes...", flush=True)
    await servicio.fetch_tenders_metadata()
    pendientes = await _contar(
        "SELECT count(*) FROM tender_metadata WHERE is_processed IS false"
    )
    print(f"[FASE 1] {pendientes} pendientes de procesar.", flush=True)

    if pendientes:
        print("\n[FASE 2] Descargando detalles e indexando...", flush=True)
        await servicio.process_unprocessed_tenders()

    total = await _contar("SELECT count(*) FROM tender")
    vigentes = await _contar("SELECT count(*) FROM tender WHERE closing_at > now()")
    print(
        f"\n[LISTO] {total} licitaciones en la base, {vigentes} vigentes.",
        flush=True,
    )
    if not vigentes:
        print(
            "[AVISO] Ninguna vigente: el matching no va a mostrar resultados.",
            flush=True,
        )
    print("Siguiente paso: export_dataset.py")

    await qdrant.close()
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limite",
        type=int,
        default=300,
        help="Máximo de compras ágiles a traer (por defecto 300).",
    )
    parser.add_argument(
        "--retardo",
        type=float,
        default=0.5,
        help=(
            "Segundos entre descargas de detalle (por defecto 0.5). Bajarlo "
            "acerca el error 429 de la API."
        ),
    )
    args = parser.parse_args()
    asyncio.run(main(args.limite, args.retardo))
