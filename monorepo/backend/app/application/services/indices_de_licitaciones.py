"""Borrado de una licitación en las tres colecciones de Qdrant (plan 306).

Cada licitación tiene un punto en `tenders` (vector del texto), otro en
`tender_items` (vectores de partidas) y otro en `tender_lexical` (BM25). Hasta
el plan 306, el cierre solo borraba el de `tenders`. Los otros dos se quedaban
con el payload en `publicada`, pasaban el filtro de estado del matching y
ocupaban cupos de candidata hasta que SQL los descartaba.

Partidas y léxico son opcionales porque no todos los entornos los tienen
configurados, igual que en `RankTendersUseCase`.
"""

from uuid import UUID

from app.application.repositories.lexical_tender_repository import (
    ILexicalTenderRepository,
)
from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)


async def borrar_de_los_indices(
    tender_ids: list[UUID],
    tender_vector_repo: ITenderVectorRepository,
    item_vector_repo: ITenderItemVectorRepository | None = None,
    lexical_tender_repo: ILexicalTenderRepository | None = None,
) -> None:
    """Borra los puntos de esas licitaciones en todas las colecciones dadas.

    Borrar un punto que no existe no es un error, así que repetirlo es seguro.
    """
    if not tender_ids:
        return
    await tender_vector_repo.delete_many(tender_ids)
    if item_vector_repo is not None:
        await item_vector_repo.delete_many(tender_ids)
    if lexical_tender_repo is not None:
        await lexical_tender_repo.delete_many(tender_ids)
