"""La ingesta guarda las cotizaciones recibidas que trae el detalle (plan 312, §4.3).

Sigue las reglas del llamado (`test_ingesta_segundo_llamado.py`): una cifra
nueva se escribe sin mover `updated_at` ni tocar Qdrant, y un `None` nunca
borra lo que dejó sync-estados desde el listado.
"""

import pytest

from .fakes import FakeEmbeddingService, FakeTenderVectorRepository
from .test_refresco_licitaciones import AHORA, RepoConLicitacion, _caso, _dto
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


class TestActualizacion:
    async def test_solo_cambio_de_cifra_se_guarda_sin_mover_updated_at(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(_dto(TotalOfertasRecibidas=4))

        assert resultado["status"] == "updated"
        assert repo.actualizada is True
        assert repo.existente.received_offers_count == 4
        assert repo.existente.offers_checked_at is not None
        # Mover `updated_at` regeneraría el análisis de Gemini (6.4).
        assert repo.existente.updated_at == AHORA
        assert repo.existente.last_change_at == AHORA
        assert emb.calls == []
        assert vec.upserts == []
        assert vec.payloads == {}

    async def test_la_misma_cifra_no_cuenta_como_cambio(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.received_offers_count = 4
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(_dto(TotalOfertasRecibidas=4))

        assert resultado["status"] == "unchanged"
        assert repo.actualizada is False

    async def test_con_cambio_de_metadatos_la_cifra_tambien_se_aplica(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(
            _dto(MontoEstimado=2_000_000.0, TotalOfertasRecibidas=6)
        )

        assert repo.existente.available_amount_clp == 2_000_000.0
        assert repo.existente.received_offers_count == 6

    async def test_un_detalle_sin_cifra_no_borra_la_que_escribio_el_cron(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.received_offers_count = 5
        repo.existente.offers_checked_at = AHORA
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        identico = await _caso(repo, emb, vec).execute(_dto())
        # Con un cambio de metadatos, `_aplicar_ofertas` también corre.
        await _caso(repo, emb, vec).execute(_dto(MontoEstimado=2_000_000.0))

        assert identico["status"] == "unchanged"
        assert repo.existente.received_offers_count == 5
        assert repo.existente.offers_checked_at == AHORA


class TestPrimerLlamado:
    """La API cuenta solo el llamado actual: la cifra del primero se congela."""

    async def test_el_alta_en_primer_llamado_copia_la_cifra(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(
            _dto(NumeroLlamado=1, TotalOfertasRecibidas=3)
        )

        modelo, _ = repo.saved[0]
        assert modelo.first_call_offers_count == 3

    async def test_el_alta_en_segundo_llamado_no_la_inventa(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(
            _dto(NumeroLlamado=2, TotalOfertasRecibidas=3)
        )

        modelo, _ = repo.saved[0]
        assert modelo.first_call_offers_count is None

    async def test_la_actualizacion_en_primer_llamado_la_copia(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(
            _dto(NumeroLlamado=1, TotalOfertasRecibidas=4)
        )

        assert repo.existente.first_call_offers_count == 4

    async def test_la_actualizacion_en_segundo_llamado_la_conserva(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.call_number = 1
        repo.existente.received_offers_count = 5
        repo.existente.first_call_offers_count = 5
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(
            _dto(NumeroLlamado=2, TotalOfertasRecibidas=1)
        )

        assert repo.existente.received_offers_count == 1
        assert repo.existente.first_call_offers_count == 5
