"""Saca de circulación las licitaciones cuyo plazo de cotización ya venció.

El payload de Qdrant se escribía una vez en la ingesta y no se volvía a tocar.
Una licitación que cerró conservaba `status_code: "publicada"`, así que seguía
pasando el pre-filtro de la primera etapa del embudo de matching y **ocupaba uno
de los 50 cupos de candidatas**, para recién ser descartada en la segunda
comparando `closing_at` contra SQL. Cada cerrada le roba el lugar a una
candidata real: con rotación alta pueden estar rerankeándose 20 vigentes en vez
de 50.

Se marcan, **no se borran**. Borrar el punto libera el cupo igual, pero el
buscador manual expone un filtro por estado que acepta `cerrada`, y esa búsqueda
quedaría devolviendo cero para siempre.

No cuesta cuota de Mercado Público: `closing_at` ya está en Postgres y que el
plazo haya vencido es aritmética, no una consulta a la API.
"""

from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.shared.constants import TENDER_STATUSES


class MarkExpiredTendersUseCase:
    def __init__(
        self,
        repository: ITenderRepository,
        tender_vector_repo: ITenderVectorRepository,
    ):
        self.repo = repository
        self.tender_vector_repo = tender_vector_repo

    async def execute(self) -> int:
        """Marca como cerradas las vencidas que aún figuran publicadas.

        Devuelve cuántas se marcaron. Es idempotente: la segunda pasada no
        encuentra nada porque la primera ya las movió de estado.
        """
        vencidas = await self.repo.get_expired_published_ids()
        if not vencidas:
            return 0

        # Qdrant antes que SQL, igual que en la ingesta y por lo mismo: las dos
        # escrituras no comparten transacción. Si SQL falla después, la
        # licitación queda marcada en el índice —que es donde importa, porque es
        # el pre-filtro— y la corrida siguiente vuelve a encontrarla en SQL y se
        # autocorrige. Al revés, quedaría publicada en el índice para siempre.
        for tender_id in vencidas:
            await self.tender_vector_repo.set_payload(
                tender_id, {"status_code": TENDER_STATUSES["CLOSED"]}
            )

        await self.repo.mark_as_closed(vencidas)
        return len(vencidas)
