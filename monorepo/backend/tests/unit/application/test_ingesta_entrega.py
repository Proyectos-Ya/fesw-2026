"""La ingesta guarda la entrega y los requisitos del detalle (plan #294).

Sigue las reglas del llamado y de las cotizaciones: un cambio que solo toca
estos datos se escribe sin mover `updated_at` ni tocar Qdrant, y un `None`
nunca borra lo guardado.
"""

import pytest

from .fakes import FakeEmbeddingService, FakeTenderVectorRepository
from .test_refresco_licitaciones import AHORA, RepoConLicitacion, _caso, _dto
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


class TestActualizacion:
    async def test_solo_cambio_de_entrega_se_guarda_sin_mover_updated_at(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(_dto(**ENTREGA))

        assert resultado["status"] == "updated"
        assert repo.actualizada is True
        assert repo.existente.delivery_address == ENTREGA["DireccionEntrega"]
        assert repo.existente.delivery_term_days == 5
        assert repo.existente.requires_environmental_criteria is True
        assert repo.existente.requires_social_impact_criteria is False
        # Mover `updated_at` regeneraría el análisis de Gemini (6.4).
        assert repo.existente.updated_at == AHORA
        assert repo.existente.last_change_at == AHORA
        assert emb.calls == []
        assert vec.upserts == []
        assert vec.payloads == {}

    async def test_un_flag_en_false_tambien_es_un_cambio(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.requires_environmental_criteria = True
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(
            _dto(RequisitosMedioambientales=False)
        )

        assert resultado["status"] == "updated"
        assert repo.existente.requires_environmental_criteria is False

    async def test_la_misma_entrega_no_cuenta_como_cambio(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.delivery_address = ENTREGA["DireccionEntrega"]
        repo.existente.delivery_term_days = 5
        repo.existente.requires_environmental_criteria = True
        repo.existente.requires_social_impact_criteria = False
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(_dto(**ENTREGA))

        assert resultado["status"] == "unchanged"
        assert repo.actualizada is False

    async def test_con_cambio_de_metadatos_la_entrega_tambien_se_aplica(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(
            _dto(MontoEstimado=2_000_000.0, PlazoEntregaDias=10)
        )

        assert repo.existente.available_amount_clp == 2_000_000.0
        assert repo.existente.delivery_term_days == 10

    async def test_un_detalle_sin_entrega_no_borra_lo_guardado(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.delivery_address = ENTREGA["DireccionEntrega"]
        repo.existente.delivery_term_days = 5
        repo.existente.requires_environmental_criteria = False
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        identico = await _caso(repo, emb, vec).execute(_dto())
        # Con un cambio de metadatos, `_aplicar_entrega` también corre.
        await _caso(repo, emb, vec).execute(_dto(MontoEstimado=2_000_000.0))

        assert identico["status"] == "unchanged"
        assert repo.existente.delivery_address == ENTREGA["DireccionEntrega"]
        assert repo.existente.delivery_term_days == 5
        assert repo.existente.requires_environmental_criteria is False


def _ubicada(repo: RepoConLicitacion, direccion: str) -> None:
    """Deja la licitación guardada con una dirección ya geocodificada (#314)."""
    repo.existente.delivery_address = direccion
    repo.existente.delivery_lat = -45.57
    repo.existente.delivery_lng = -72.07
    repo.existente.delivery_geo_precision = "direccion"
    repo.existente.delivery_geocoded_at = AHORA


class TestReencolarGeocodificacion:
    """HU-22 (#314): una dirección nueva vuelve a la cola del mapa."""

    async def test_otra_direccion_borra_el_punto_y_la_deja_pendiente(self):
        repo = RepoConLicitacion(_dto())
        _ubicada(repo, "SERVIU REGION DE AYSEN RAMON FREIRE 5")
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto(DireccionEntrega="Baquedano 50"))

        assert repo.existente.delivery_address == "Baquedano 50"
        # El punto viejo es de otra dirección: mostrarlo sería inventar.
        assert repo.existente.delivery_lat is None
        assert repo.existente.delivery_lng is None
        assert repo.existente.delivery_geo_precision is None
        assert repo.existente.delivery_geocoded_at is None
        assert repo.existente.updated_at == AHORA

    async def test_la_misma_direccion_conserva_el_punto(self):
        repo = RepoConLicitacion(_dto())
        _ubicada(repo, ENTREGA["DireccionEntrega"])
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto(**ENTREGA))

        assert repo.existente.delivery_lat == -45.57
        assert repo.existente.delivery_geocoded_at == AHORA

    async def test_un_detalle_sin_direccion_conserva_el_punto(self):
        repo = RepoConLicitacion(_dto())
        _ubicada(repo, ENTREGA["DireccionEntrega"])
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto(PlazoEntregaDias=9))

        assert repo.existente.delivery_lat == -45.57
        assert repo.existente.delivery_geocoded_at == AHORA
