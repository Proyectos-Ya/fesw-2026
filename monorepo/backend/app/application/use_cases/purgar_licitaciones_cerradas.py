"""Borra las licitaciones cerradas que nadie usó (plan 306).

Entran unas 3.000 licitaciones por día y casi ninguna cerrada se vuelve a usar.
Medido el 2026-10-13: 18.776 de 41.500 (el 45%) cerraron hace más de 7 días sin
uso, y la base crecía unos 130 MB al mes.

Lo corre la ingesta nocturna. Cada lote borra primero en Qdrant y después en
SQL, igual que el resto de la ingesta: si SQL falla, la licitación sigue siendo
borrable y la noche siguiente se repite. Al revés, quedaría en Qdrant un punto
que SQL ya no volvería a señalar.

Si una licitación borrada reabre (segundo llamado), sync-estados no la conoce,
la ve activa con cierre futuro y la deja como `nueva`, y la ingesta la vuelve a
bajar entera.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from app.application.repositories.lexical_tender_repository import (
    ILexicalTenderRepository,
)
from app.application.repositories.tender_item_vector_repository import (
    ITenderItemVectorRepository,
)
from app.application.repositories.tender_retention_repository import (
    ITenderRetentionRepository,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.indices_de_licitaciones import borrar_de_los_indices
from app.shared.datetime_utils import utc_now_naive

# Licitaciones por transacción. El lote bloquea sus filas de `tender` mientras
# borra: chico para que el bloqueo dure poco, grande para no hacer miles de
# viajes en la primera corrida (~18.800).
LOTE = 1_000


class PurgarLicitacionesCerradasUseCase:
    def __init__(
        self,
        repository: ITenderRetentionRepository,
        tender_vector_repo: ITenderVectorRepository,
        retencion_dias: int | None,
        item_vector_repo: ITenderItemVectorRepository | None = None,
        lexical_tender_repo: ILexicalTenderRepository | None = None,
        lote: int = LOTE,
        reloj: Callable[[], datetime] = utc_now_naive,
    ) -> None:
        self.repo = repository
        self.tender_vector_repo = tender_vector_repo
        self.retencion_dias = retencion_dias
        self.item_vector_repo = item_vector_repo
        self.lexical_tender_repo = lexical_tender_repo
        self.lote = lote
        self.reloj = reloj

    async def execute(self) -> int:
        """Devuelve cuántas licitaciones borró. `None` en los días no borra nada."""
        if self.retencion_dias is None:
            return 0
        corte = self.reloj() - timedelta(days=self.retencion_dias)
        total = 0
        while ids := await self.repo.ids_borrables(corte, self.lote):
            await borrar_de_los_indices(
                ids,
                self.tender_vector_repo,
                self.item_vector_repo,
                self.lexical_tender_repo,
            )
            borradas = await self.repo.borrar(ids, corte)
            total += borradas
            # Si el lote entero se conservó, la próxima vuelta traería los
            # mismos ids y el bucle no terminaría.
            if borradas == 0:
                break
        return total
