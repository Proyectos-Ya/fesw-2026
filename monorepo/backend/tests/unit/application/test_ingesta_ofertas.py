"""La ingesta guarda las cotizaciones recibidas que trae el detalle (plan 312, §4.3).

Sigue las reglas del llamado (`test_ingesta_segundo_llamado.py`): una cifra
nueva se escribe sin mover `updated_at` ni tocar Qdrant, y un `None` nunca
borra lo que dejó sync-estados desde el listado.
"""

import pytest

from .fakes import FakeEmbeddingService, FakeTenderVectorRepository
from .test_refresco_licitaciones import _caso, _dto
from .test_tender_ingestion_use_case import FakeTenderRepository

pytestmark = pytest.mark.asyncio


class TestAlta:
    async def test_el_alta_guarda_la_cifra_y_la_fecha_de_revision(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto(TotalOfertasRecibidas=2))

        modelo, _ = repo.saved[0]
        assert modelo.received_offers_count == 2
        assert modelo.offers_checked_at is not None

    async def test_un_alta_sin_cifra_deja_las_dos_en_none(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto())

        modelo, _ = repo.saved[0]
        assert modelo.received_offers_count is None
        assert modelo.offers_checked_at is None
