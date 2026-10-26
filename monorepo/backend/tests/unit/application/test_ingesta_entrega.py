"""La ingesta guarda la entrega y los requisitos del detalle (plan #294).

Sigue las reglas del llamado y de las cotizaciones: un cambio que solo toca
estos datos se escribe sin mover `updated_at` ni tocar Qdrant, y un `None`
nunca borra lo guardado.
"""

import pytest

from .fakes import FakeEmbeddingService, FakeTenderVectorRepository
from .test_refresco_licitaciones import _caso, _dto
from .test_tender_ingestion_use_case import FakeTenderRepository

pytestmark = pytest.mark.asyncio

ENTREGA = {
    "DireccionEntrega": "SERVIU REGION DE AYSEN RAMON FREIRE 5",
    "PlazoEntregaDias": 5,
    "RequisitosMedioambientales": True,
    "RequisitosImpactoSocial": False,
}


class TestAlta:
    async def test_el_alta_guarda_la_entrega_y_los_requisitos(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto(**ENTREGA))

        modelo, _ = repo.saved[0]
        assert modelo.delivery_address == "SERVIU REGION DE AYSEN RAMON FREIRE 5"
        assert modelo.delivery_term_days == 5
        assert modelo.requires_environmental_criteria is True
        assert modelo.requires_social_impact_criteria is False

    async def test_un_alta_sin_entrega_la_deja_en_none(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto())

        modelo, _ = repo.saved[0]
        assert modelo.delivery_address is None
        assert modelo.delivery_term_days is None
        assert modelo.requires_environmental_criteria is None
        assert modelo.requires_social_impact_criteria is None
