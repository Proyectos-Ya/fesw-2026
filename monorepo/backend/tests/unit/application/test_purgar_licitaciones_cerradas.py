"""Caso de uso de la retención de licitaciones cerradas (plan 306).

Qué y cuándo se borra lo decide el repositorio (ver
`tests/integration/test_retencion_licitaciones.py`). Acá se prueba el orden y
los lotes: Qdrant antes que SQL, las tres colecciones, el corte según los días
configurados y que `None` apague el borrado.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.repositories.tender_retention_repository import (
    ITenderRetentionRepository,
)
from app.application.services.lexical_tokenizer import SparseTermVector
from app.application.use_cases.purgar_licitaciones_cerradas import (
    PurgarLicitacionesCerradasUseCase,
)

from .fakes import (
    FakeTenderVectorRepository,
    InMemoryLexicalTenderRepository,
    InMemoryTenderItemVectorRepository,
)

pytestmark = pytest.mark.asyncio

AHORA = datetime(2026, 10, 15, 6, 0)


class RepoFalso(ITenderRetentionRepository):
    def __init__(self, borrables: list[UUID], log: list[str] | None = None) -> None:
        self.borrables = list(borrables)
        self.cortes: list[datetime] = []
        self.lotes: list[list[UUID]] = []
        self.log = log if log is not None else []
        # Ids que `borrar` se niega a borrar, como si alguien los hubiera usado.
        self.usadas: set[UUID] = set()

    async def ids_borrables(self, corte: datetime, limite: int) -> list[UUID]:
        self.cortes.append(corte)
        return [i for i in self.borrables if i not in self.usadas][:limite]

    async def borrar(self, tender_ids: list[UUID], corte: datetime) -> int:
        self.log.append("sql")
        self.lotes.append(list(tender_ids))
        borradas = [i for i in tender_ids if i not in self.usadas]
        self.borrables = [i for i in self.borrables if i not in borradas]
        return len(borradas)


def _caso(repo, *, dias=7, lote=1_000, vec=None, partidas=None, lexico=None):
    return PurgarLicitacionesCerradasUseCase(
        repository=repo,
        tender_vector_repo=vec or FakeTenderVectorRepository(),
        item_vector_repo=partidas,
        lexical_tender_repo=lexico,
        retencion_dias=dias,
        lote=lote,
        reloj=lambda: AHORA,
    )


async def test_borra_las_borrables_y_cuenta_cuantas():
    ids = [uuid4(), uuid4(), uuid4()]
    repo = RepoFalso(ids)

    assert await _caso(repo).execute() == 3
    assert repo.borrables == []


async def test_el_corte_son_los_dias_configurados_antes_de_ahora():
    repo = RepoFalso([])

    await _caso(repo, dias=10).execute()

    assert repo.cortes == [AHORA - timedelta(days=10)]


async def test_sin_dias_configurados_no_borra_nada():
    repo = RepoFalso([uuid4()])

    assert await _caso(repo, dias=None).execute() == 0
    assert repo.cortes == [] and repo.lotes == []


async def test_saca_de_las_tres_colecciones():
    borrable, otra = uuid4(), uuid4()
    vec = FakeTenderVectorRepository()
    partidas = InMemoryTenderItemVectorRepository()
    lexico = InMemoryLexicalTenderRepository()
    for i in (borrable, otra):
        await partidas.upsert(i, [[1.0, 0.0]], {"status_code": "cerrada"})
        await lexico.upsert(i, SparseTermVector(indices=[1], values=[1.0]))

    await _caso(
        RepoFalso([borrable]), vec=vec, partidas=partidas, lexico=lexico
    ).execute()

    assert vec.deleted == [borrable]
    assert set(partidas.vectors) == {otra}
    assert set(lexico.vectors) == {otra}


async def test_qdrant_antes_que_sql_en_cada_lote():
    """Si SQL falla, la licitación sigue borrable y la noche siguiente se
    repite. Al revés quedaría un punto que nadie volvería a señalar."""
    log: list[str] = []
    vec = FakeTenderVectorRepository()

    async def delete_many(ids):
        log.append("qdrant")

    vec.delete_many = delete_many  # type: ignore[method-assign]

    await _caso(RepoFalso([uuid4(), uuid4(), uuid4()], log), vec=vec, lote=2).execute()

    assert log == ["qdrant", "sql", "qdrant", "sql"]


async def test_va_por_lotes_hasta_vaciar():
    repo = RepoFalso([uuid4() for _ in range(5)])

    assert await _caso(repo, lote=2).execute() == 5
    assert [len(lote) for lote in repo.lotes] == [2, 2, 1]


async def test_corta_si_un_lote_no_borra_nada():
    """Si `borrar` se niega con todo el lote y `ids_borrables` las sigue
    devolviendo, sin este corte el bucle no terminaría nunca."""
    ids = [uuid4(), uuid4()]
    repo = RepoFalso(ids)
    repo.usadas = set(ids)
    repo.ids_borrables = lambda corte, limite: _devolver(ids)  # type: ignore[method-assign]

    assert await _caso(repo).execute() == 0
    assert len(repo.lotes) == 1


async def _devolver(ids):
    return list(ids)
