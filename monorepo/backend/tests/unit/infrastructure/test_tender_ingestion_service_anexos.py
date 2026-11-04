"""El servicio de ingesta le entrega al caso de uso el repositorio de anexos.

Sin este cableado, la ingesta no guardaría la lista oficial que trae el detalle
(plan 233, decisión 1). Va con la misma sesión que `TenderRepository`: el
rollback del caso de uso también cubre lo que se escribió en `tender_attachment`.
"""

from unittest.mock import MagicMock

from app.infrastructure.repositories.sql_tender_attachment_repository import (
    SqlTenderAttachmentRepository,
)
from app.infrastructure.services.tenders.tender_ingestion_service import (
    TenderIngestionService,
)
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeTenderVectorRepository,
)


def _servicio() -> TenderIngestionService:
    return TenderIngestionService(
        engine=MagicMock(),
        client=MagicMock(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
    )


def test_el_caso_de_uso_recibe_el_repositorio_de_anexos_con_la_misma_sesion() -> None:
    session = MagicMock()

    caso = _servicio()._construir_use_case(session)

    assert isinstance(caso.attachment_repo, SqlTenderAttachmentRepository)
    assert caso.attachment_repo.session is session
    assert caso.repo.session is session  # type: ignore[attr-defined]
