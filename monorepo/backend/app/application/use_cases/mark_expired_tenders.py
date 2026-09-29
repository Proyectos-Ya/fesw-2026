"""Saca del índice vectorial las licitaciones cuyo plazo de cotización venció.

El índice guarda **solo licitaciones activas**. Una cerrada no tiene nada que
hacer ahí: el matching descarta lo no publicado y el buscador resuelve en
Postgres toda búsqueda que incluya estados no activos (`SearchTendersUseCase`).
Conservar sus puntos solo hacía crecer el índice —~11 GB al año contra ~87 MB
de lo vigente, medido en el spike 2.1— y cada cerrada con el payload todavía en
`publicada` le robaba un cupo de candidata al pre-filtro del matching.

Antes se marcaban en el payload en vez de borrarse, porque el buscador filtraba
cerradas contra Qdrant. Desde que esa búsqueda va a Postgres, ese motivo ya no
existe.

No cuesta cuota de Mercado Público: `closing_at` ya está en Postgres y que el
plazo haya vencido es aritmética, no una consulta a la API.
"""

from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES


class MarkExpiredTendersUseCase:
    def __init__(
        self,
        repository: ITenderRepository,
        tender_vector_repo: ITenderVectorRepository,
    ):
        self.repo = repository
        self.tender_vector_repo = tender_vector_repo

    async def execute(self) -> int:
        """Cierra en SQL las vencidas que aún figuran publicadas y borra su punto.

        Devuelve cuántas se cerraron. Es idempotente: la segunda pasada no
        encuentra nada porque la primera ya las movió de estado.
        """
        vencidas = await self.repo.get_expired_published_ids()
        if vencidas:
            # Qdrant antes que SQL, igual que en la ingesta y por lo mismo: las
            # dos escrituras no comparten transacción. Si SQL falla después, la
            # corrida siguiente vuelve a encontrarlas en SQL y borrar un punto
            # que ya no existe no es un error. Al revés, quedaría en el índice
            # un punto que SQL ya no volvería a señalar.
            await self.tender_vector_repo.delete_many(vencidas)
            await self.repo.mark_as_closed(vencidas)

        # Barrido por payload: corrige lo que quedó de antes de esta regla o de
        # una escritura a medias. Lo resuelve Qdrant en el servidor, así que
        # correrlo todos los días no cuesta nada.
        await self.tender_vector_repo.delete_by_status_not_in(ACTIVE_TENDER_STATUSES)
        return len(vencidas)


class PurgeInactiveTenderVectorsUseCase:
    """Purga única: deja en el índice solo lo que Postgres dice que está activo.

    El barrido por payload no alcanza a los puntos cuyo payload quedó diciendo
    `publicada` cuando SQL ya no (6.24: desiertas leídas como publicadas por un
    mapa de estados equivocado). Para esos manda Postgres, que es la fuente de
    verdad del estado.
    """

    def __init__(
        self,
        repository: ITenderRepository,
        tender_vector_repo: ITenderVectorRepository,
    ):
        self.repo = repository
        self.tender_vector_repo = tender_vector_repo

    async def execute(self) -> int:
        """Devuelve cuántas licitaciones inactivas había en SQL."""
        inactivas = await self.repo.get_inactive_ids()
        await self.tender_vector_repo.delete_many(inactivas)
        await self.tender_vector_repo.delete_by_status_not_in(ACTIVE_TENDER_STATUSES)
        return len(inactivas)
