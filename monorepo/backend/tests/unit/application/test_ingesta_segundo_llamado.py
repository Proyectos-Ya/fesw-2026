"""La ingesta guarda el llamado vigente y el cierre de cada llamado (plan 233, decisión 3).

La regla que manda es la de `updated_at`: mover ese campo hace que el análisis
de Gemini se regenere para cada proveedor, así que un cambio que solo afecta al
llamado se escribe **sin** tocarlo (ni tocar Qdrant). Un cambio de llamado de
verdad trae además otro `closing_at`, y eso sí lo mueve, por la vía de siempre.

Y un `None` nunca sobrescribe: que el detalle de la API traiga `convocatoria` y
los cierres por llamado no está verificado, y tomar su ausencia como "sin
llamado" borraría lo que escribió el cron de estados desde el listado.
"""

from datetime import datetime, timedelta

import pytest

from .fakes import FakeEmbeddingService, FakeTenderVectorRepository
from .test_refresco_licitaciones import AHORA, RepoConLicitacion, _caso, _dto
from .test_tender_ingestion_use_case import FakeTenderRepository

pytestmark = pytest.mark.asyncio


class TestAlta:
    async def test_el_alta_guarda_el_llamado_y_los_cierres(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()
        dto = _dto(
            NumeroLlamado=2,
            FechaCierrePrimerLlamado=datetime(2026, 9, 26, 17, 10),
            FechaCierreSegundoLlamado=datetime(2026, 9, 27, 17, 28),
            FechaCierre=datetime(2026, 9, 27, 17, 28),
        )

        await _caso(repo, emb, vec).execute(dto)

        modelo, _ = repo.saved[0]
        assert modelo.call_number == 2
        # Chile está en UTC-3 en esas fechas.
        assert modelo.first_call_closing_at == datetime(2026, 9, 26, 20, 10)
        assert modelo.second_call_closing_at == datetime(2026, 9, 27, 20, 28)
        assert modelo.closing_at == modelo.second_call_closing_at

    async def test_un_alta_sin_llamado_lo_deja_en_none(self):
        repo = FakeTenderRepository()
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto())

        modelo, _ = repo.saved[0]
        assert modelo.call_number is None
        assert modelo.first_call_closing_at is None
        assert modelo.second_call_closing_at is None


class TestActualizacion:
    async def test_solo_cambio_de_llamado_se_guarda_sin_mover_updated_at(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()
        nuevo = _dto(
            NumeroLlamado=1,
            FechaCierreSegundoLlamado=AHORA + timedelta(days=6),
        )

        resultado = await _caso(repo, emb, vec).execute(nuevo)

        assert resultado["status"] == "updated"
        assert repo.actualizada is True
        assert repo.existente.call_number == 1
        assert repo.existente.second_call_closing_at == nuevo.second_call_closing_at
        # Mover `updated_at` regeneraría el análisis de Gemini (6.4).
        assert repo.existente.updated_at == AHORA
        assert repo.existente.last_change_at == AHORA
        # No cambia lo que se pide ni el estado: ni inferencia ni Qdrant.
        assert emb.calls == []
        assert vec.upserts == []
        assert vec.payloads == {}

    async def test_un_detalle_sin_llamado_no_borra_el_que_escribio_el_cron(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.call_number = 2
        repo.existente.first_call_closing_at = AHORA - timedelta(days=1)
        repo.existente.second_call_closing_at = AHORA + timedelta(days=5)
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        # Cambia el monto (metadato), así que `_aplicar_cambios` sí corre.
        await _caso(repo, emb, vec).execute(_dto(MontoEstimado=2_000_000.0))

        assert repo.existente.available_amount_clp == 2_000_000.0
        assert repo.existente.call_number == 2
        assert repo.existente.first_call_closing_at == AHORA - timedelta(days=1)
        assert repo.existente.second_call_closing_at == AHORA + timedelta(days=5)

    async def test_un_detalle_identico_sin_llamado_sigue_sin_escribir(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.call_number = 2
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(_dto())

        assert resultado["status"] == "unchanged"
        assert repo.actualizada is False
        assert repo.existente.call_number == 2

    async def test_un_detalle_con_el_mismo_llamado_sigue_sin_escribir(self):
        repo = RepoConLicitacion(_dto())
        repo.existente.call_number = 2
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(_dto(NumeroLlamado=2))

        assert resultado["status"] == "unchanged"
        assert repo.actualizada is False

    async def test_un_cambio_real_de_llamado_mueve_updated_at_por_el_cierre(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()
        nuevo = _dto(
            NumeroLlamado=2,
            FechaCierre=AHORA + timedelta(days=10),
            FechaCierreSegundoLlamado=AHORA + timedelta(days=10),
        )

        resultado = await _caso(repo, emb, vec).execute(nuevo)

        assert resultado["status"] == "updated"
        assert repo.existente.updated_at != AHORA
        assert repo.existente.call_number == 2
        assert repo.existente.closing_at == repo.existente.second_call_closing_at
