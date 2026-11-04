"""El servicio de ingesta le entrega al caso de uso el repositorio de partidas.

Sin este cableado, la ingesta diaria no llenaría `tender_items` y cada licitación
nueva caería en el camino lento del puntaje (embeber sus partidas al leer).
"""

from unittest.mock import MagicMock

from app.config import settings
from app.infrastructure.repositories.qdrant_tender_item_vector_repository import (
    QdrantTenderItemVectorRepository,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeTenderVectorRepository,
    InMemoryTenderItemVectorRepository,
)


def _servicio(**kwargs) -> TenderIngestionService:
    return TenderIngestionService(
        engine=MagicMock(),
        client=MagicMock(),
        embedding_service=FakeEmbeddingService(),
        **kwargs,
    )


def test_con_cliente_qdrant_arma_el_repositorio_de_partidas() -> None:
    qdrant = MagicMock()
    servicio = _servicio(qdrant_client=qdrant)

    caso = servicio._construir_use_case(MagicMock())

    repo = caso.tender_item_vector_repo
    assert isinstance(repo, QdrantTenderItemVectorRepository)
    assert repo._client is qdrant
    assert repo._vector_size == settings.embedding_vector_size


def test_un_repositorio_inyectado_tiene_prioridad() -> None:
    """Mismo patrón que `tender_vector_repo`: lo inyectado gana sobre Qdrant."""
    inyectado = InMemoryTenderItemVectorRepository()
    servicio = _servicio(qdrant_client=MagicMock(), tender_item_vector_repo=inyectado)

    caso = servicio._construir_use_case(MagicMock())

    assert caso.tender_item_vector_repo is inyectado


def test_sin_cliente_qdrant_ni_repositorio_no_guarda_partidas() -> None:
    """Los tests de integración inyectan solo `tender_vector_repo`: no hay cliente
    contra el cual armar el repositorio de partidas, y no debe explotar."""
    servicio = _servicio(tender_vector_repo=FakeTenderVectorRepository())

    caso = servicio._construir_use_case(MagicMock())

    assert caso.tender_item_vector_repo is None
