"""El índice vectorial guarda solo licitaciones activas.

Qdrant sostiene un único uso que las cerradas no necesitan: ordenar por
afinidad con la empresa lo que todavía admite postulación. El buscador ya
resuelve en Postgres cualquier búsqueda que incluya estados no activos, así que
conservar sus puntos solo hacía crecer el índice (~11 GB al año contra ~87 MB
de lo vigente, spike 2.1).

Estos tests cubren los dos casos de uso que sacan puntos del índice: el barrido
diario de vencidas y la purga única del corpus que se indexó antes del cambio.
"""

from uuid import UUID, uuid4

import pytest

from app.application.use_cases.mark_expired_tenders import (
    MarkExpiredTendersUseCase,
    PurgeInactiveTenderVectorsUseCase,
)
from app.shared.constants import ACTIVE_TENDER_STATUSES

from .fakes import FakeTenderVectorRepository, InMemoryTenderRepository

pytestmark = pytest.mark.asyncio


class RepoConVencidas(InMemoryTenderRepository):
    def __init__(
        self, vencidas: list[UUID], inactivas: list[UUID] | None = None
    ) -> None:
        super().__init__()
        self.vencidas = list(vencidas)
        self.inactivas = list(inactivas or [])

    async def get_expired_published_ids(self) -> list[UUID]:
        return [i for i in self.vencidas if i not in self.cerradas]

    async def get_inactive_ids(self) -> list[UUID]:
        return list(self.inactivas)


class TestMarcarVencidas:
    async def test_borra_del_indice_las_vencidas_y_las_cierra_en_sql(self):
        ids = [uuid4(), uuid4()]
        repo, vec = RepoConVencidas(ids), FakeTenderVectorRepository()

        marcadas = await MarkExpiredTendersUseCase(repo, vec).execute()

        assert marcadas == 2
        assert vec.deleted == ids
        assert repo.cerradas == ids
        assert vec.payloads == {}, "ya no se marca el payload: se borra el punto"

    async def test_borra_en_qdrant_antes_de_cerrar_en_sql(self):
        """Si SQL falla después, la corrida siguiente las vuelve a encontrar y
        borrar otra vez no cuesta nada. Al revés, quedaría un punto de una
        cerrada que SQL ya no volvería a señalar."""
        repo, vec = RepoConVencidas([uuid4()]), FakeTenderVectorRepository()
        orden: list[str] = []

        async def delete_many_espia(ids):
            orden.append("qdrant")

        async def mark_as_closed_espia(ids):
            orden.append("sql")

        vec.delete_many = delete_many_espia  # type: ignore[method-assign]
        repo.mark_as_closed = mark_as_closed_espia  # type: ignore[method-assign]

        await MarkExpiredTendersUseCase(repo, vec).execute()

        assert orden == ["qdrant", "sql"]

    async def test_barre_los_puntos_no_activos_aunque_no_haya_vencidas(self):
        """El barrido por payload corrige solo lo que quedó de antes o de una
        escritura a medias, y no depende de que ese día venza algo."""
        repo, vec = RepoConVencidas([]), FakeTenderVectorRepository()

        marcadas = await MarkExpiredTendersUseCase(repo, vec).execute()

        assert marcadas == 0
        assert vec.status_sweeps == [set(ACTIVE_TENDER_STATUSES)]

    async def test_es_idempotente(self):
        repo, vec = RepoConVencidas([uuid4()]), FakeTenderVectorRepository()
        caso = MarkExpiredTendersUseCase(repo, vec)

        assert (await caso.execute(), await caso.execute()) == (1, 0)


class TestPurgaUnica:
    async def test_borra_las_inactivas_segun_sql_y_barre_por_payload(self):
        """El filtro por payload no alcanza a los puntos cuyo payload quedó
        diciendo `publicada` cuando SQL ya no (6.24: desiertas leídas como
        publicadas). Para esos manda Postgres."""
        inactivas = [uuid4(), uuid4(), uuid4()]
        repo = RepoConVencidas([], inactivas=inactivas)
        vec = FakeTenderVectorRepository()

        borradas = await PurgeInactiveTenderVectorsUseCase(repo, vec).execute()

        assert borradas == 3
        assert vec.deleted == inactivas
        assert vec.status_sweeps == [set(ACTIVE_TENDER_STATUSES)]

    async def test_sin_inactivas_solo_barre(self):
        repo, vec = RepoConVencidas([]), FakeTenderVectorRepository()

        borradas = await PurgeInactiveTenderVectorsUseCase(repo, vec).execute()

        assert borradas == 0
        assert vec.deleted == []
        assert len(vec.status_sweeps) == 1
