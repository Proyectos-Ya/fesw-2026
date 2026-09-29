"""Purga única: deja en Qdrant solo las licitaciones activas.

Contexto
--------
El índice vectorial pasó a guardar solo licitaciones activas: el buscador
resuelve en Postgres toda búsqueda que incluya cerradas, y el matching descarta
lo no publicado. Desde ese cambio, la ingesta y el barrido diario de
`sync_diaria` ya no dejan entrar ni quedarse puntos inactivos, pero el corpus
indexado antes los conserva. Este script los saca una sola vez.

Borra dos grupos:

- los ids que Postgres tiene con un estado no activo, que es la fuente de verdad
  (incluye los puntos cuyo payload quedó diciendo `publicada` por el mapa de
  estados equivocado de 6.24), y
- todo punto cuyo payload no diga un estado activo.

**Correrlo solo después de desplegar la búsqueda por estado**
(`SearchTendersUseCase`): con la versión anterior, la búsqueda de cerradas sin
texto sale de Qdrant y quedaría devolviendo cero. Es idempotente: repetirlo no
borra nada nuevo.

Uso
---
    python -m scripts.purgar_vectores_inactivos --dry-run              # solo cuenta
    python -m scripts.purgar_vectores_inactivos                        # local
    python -m scripts.purgar_vectores_inactivos --confirmar-produccion
"""

import argparse
import asyncio
import sys

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchAny
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.use_cases.mark_expired_tenders import (
    PurgeInactiveTenderVectorsUseCase,
)
from app.config import settings
from app.infrastructure.db import crear_engine
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.shared.constants import ACTIVE_TENDER_STATUSES
from scripts.sync_diaria import verificar_destino

_COLLECTION = "tenders"


async def _contar_puntos(client: AsyncQdrantClient, *, inactivos: bool) -> int:
    """Puntos del índice; con `inactivos`, solo los de payload no activo."""
    filtro = (
        Filter(
            must_not=[
                FieldCondition(
                    key="status_code",
                    match=MatchAny(any=sorted(ACTIVE_TENDER_STATUSES)),
                )
            ]
        )
        if inactivos
        else None
    )
    respuesta = await client.count(
        collection_name=_COLLECTION, count_filter=filtro, exact=True
    )
    return respuesta.count


async def run(dry_run: bool) -> None:
    engine = crear_engine()
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        antes = await _contar_puntos(qdrant, inactivos=False)
        por_payload = await _contar_puntos(qdrant, inactivos=True)
        print(f"Puntos en el índice                : {antes}")
        print(f"Con payload no activo              : {por_payload}")

        async with AsyncSession(engine) as session:
            repo = TenderRepository(session)
            if dry_run:
                inactivas = await repo.get_inactive_ids()
                print(f"Inactivas en Postgres (a borrar)   : {len(inactivas)}")
                print("\n[dry-run] no se borró nada.")
                return

            caso = PurgeInactiveTenderVectorsUseCase(
                repository=repo,
                tender_vector_repo=QdrantTenderRepository(
                    client=qdrant, vector_size=settings.embedding_vector_size
                ),
            )
            inactivas = await caso.execute()

        despues = await _contar_puntos(qdrant, inactivos=False)
        print(f"Inactivas en Postgres              : {inactivas}")
        print(
            f"Puntos en el índice tras la purga  : {despues} ({antes - despues} borrados)"
        )
    finally:
        await engine.dispose()
        await qdrant.close()


def main() -> None:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument("--dry-run", action="store_true", help="solo contar, sin borrar")
    p.add_argument(
        "--confirmar-produccion",
        action="store_true",
        help="requerido si la base no es local",
    )
    args = p.parse_args()

    print(f"Base de datos : {settings.database_url.split('@')[-1]}")
    print(f"Qdrant        : {settings.qdrant_url}\n")

    if not args.dry_run:
        mensaje = verificar_destino(
            settings.database_url, confirmar_produccion=args.confirmar_produccion
        )
        if mensaje:
            print(mensaje, file=sys.stderr)
            sys.exit(2)

    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
