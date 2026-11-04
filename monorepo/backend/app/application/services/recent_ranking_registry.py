"""Reuso del `ranking_id` cuando se sirve la misma lista (plan 233, decisión 8).

El dashboard pide `/tenders/recommended` dos veces al montarse, otra cada 3 minutos
y desde Inicio y Matches, y todas esas respuestas salen de la misma caché de
`matching_result`. Sin este registro cada una sería un ranking distinto con las
mismas posiciones, y el NDCG contaría varias veces lo mismo.
"""

from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID, uuid4

RANKING_REUSE_WINDOW = timedelta(minutes=30)


class RecentRankingRegistry:
    """Reusa el ranking_id si la misma lista se le sirvió hace poco al mismo usuario y empresa.

    En memoria y por proceso: la API corre con un solo worker (ver
    `NotificationScheduler`). Con más, solo se degrada (más rankings), no se
    corrompe nada.
    """

    def __init__(
        self,
        reuse_window: timedelta = RANKING_REUSE_WINDOW,
        max_entries: int = 10_000,
    ) -> None:
        self.reuse_window = reuse_window
        self.max_entries = max_entries
        # (usuario, empresa) -> (firma de la lista, ranking_id, última vez servido)
        self._entries: OrderedDict[
            tuple[UUID, UUID], tuple[tuple[str, tuple[UUID, ...]], UUID, datetime]
        ] = OrderedDict()

    def resolve(
        self,
        *,
        user_id: UUID,
        supplier_id: UUID,
        model_version: str,
        tender_ids: Sequence[UUID],
        now: datetime,
    ) -> tuple[UUID, bool]:
        """`(ranking_id, es_nuevo)`. Solo un `ranking_id` nuevo hay que registrarlo."""
        key = (user_id, supplier_id)
        signature = (model_version, tuple(tender_ids))

        entry = self._entries.get(key)
        if (
            entry is not None
            and entry[0] == signature
            and now - entry[2] <= self.reuse_window
        ):
            # Ventana deslizante: cada vez que se sirve de nuevo, vuelve a contar.
            self._entries[key] = (signature, entry[1], now)
            self._entries.move_to_end(key)
            return entry[1], False

        ranking_id = uuid4()
        self._entries[key] = (signature, ranking_id, now)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return ranking_id, True
