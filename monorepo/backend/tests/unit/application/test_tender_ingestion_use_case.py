"""
Tests unitarios de TenderIngestionUseCase.
Verifican que tras guardar cada licitación en SQL se genera su embedding
y se indexa en el repositorio vectorial (Qdrant).
"""

from datetime import datetime
from uuid import UUID

from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.tender import Tender
from app.domain.models.tender_ingestion_dto import TenderIngestaDTO
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel
from app.shared.constants import ACTIVE_TENDER_STATUSES
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeTenderVectorRepository,
)

# ---------------------------------------------------------------------------
# Fakes locales
# ---------------------------------------------------------------------------


class FakeTenderRepository(ITenderRepository):
    """Repositorio SQL en memoria que deja pasar todas las operaciones."""

    def __init__(self, comuna_ids_by_name: dict[str, int] | None = None) -> None:
        self.saved: list = []
        self.buyers_created: list[dict] = []
        self._comuna_ids_by_name = comuna_ids_by_name or {"Santiago": 295}

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:  # noqa: ARG002
        return []

    async def get_by_code(self, code: str) -> TenderModel | None:  # noqa: ARG002
        return None

    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,  # noqa: ARG002
        limit: int,  # noqa: ARG002
        offset: int = 0,  # noqa: ARG002
    ) -> tuple[list[Tender], int]:
        return [], 0

    async def get_or_create_buyer(
        self,
        rut: str,
        name: str,
        region_id: int,
        comuna_id: int | None = None,
        comuna_resolution_source: str | None = None,
    ) -> str:
        self.buyers_created.append(
            {
                "rut": rut,
                "name": name,
                "region_id": region_id,
                "comuna_id": comuna_id,
                "comuna_resolution_source": comuna_resolution_source,
            }
        )
        return rut

    async def get_comuna_id_by_name(self, name: str) -> int | None:
        return self._comuna_ids_by_name.get(name)

    async def get_or_create_status(self, status_id: int, code: str) -> int:
        return status_id

    async def save_complex_tender(
        self, tender_model: TenderModel, items: list[TenderItemModel]
    ) -> None:
        self.saved.append((tender_model, items))

    async def rollback(self) -> None:
        pass

    async def get_deep_analysis(
        self, tender_id: UUID, supplier_id: UUID
    ) -> DeepAnalysis | None:
        return None

    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        return deep_analysis

    async def get_latest_tender_created_at(self) -> datetime | None:
        return None


def _make_dto(
    code: str = "LIC-001",
    status_code: int = 2,
    estado_codigo: str = "publicada",
    organismo: str = "Municipalidad de Santiago",
) -> TenderIngestaDTO:
    return TenderIngestaDTO.model_validate(
        {
            "CodigoExterno": code,
            "Nombre": "Construcción de sede comunal",
            "Descripcion": "Se requiere construir edificio de 2 pisos",
            "CodigoEstado": status_code,
            "EstadoCodigo": estado_codigo,
            "FechaPublicacion": "2026-01-01T00:00:00",
            "FechaCierre": "2026-06-30T23:59:00",
            "RutComprador": "12.345.678-9",
            "NombreOrganismo": organismo,
            "UnidadCompra": "Depto. Obras",
            "RegionId": 13,
            "RegionUnidad": "Región Metropolitana de Santiago",
            "MontoEstimado": 50_000_000.0,
            "items": [
                {
                    "nombre_producto": "Mano de obra",
                    "cantidad": 10,
                    "unidad_medida": "hh",
                },
            ],
        }
    )


# ---------------------------------------------------------------------------
# Tests de indexación vectorial
# ---------------------------------------------------------------------------


async def test_ingesta_indexa_licitacion_en_qdrant() -> None:
    """Cada licitación procesada genera exactamente un upsert en Qdrant."""
    vector_repo = FakeTenderVectorRepository()
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto())

    assert len(vector_repo.upserts) == 1


async def test_ingesta_dos_licitaciones_genera_dos_upserts() -> None:
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto("LIC-001"))
    await use_case.execute(_make_dto("LIC-002"))

    assert len(vector_repo.upserts) == 2


async def test_vector_almacenado_proviene_del_embedding_service() -> None:
    """El vector en Qdrant es el que devuelve el EmbeddingService, no uno hardcodeado."""
    fake_vector = [0.7] * 1024
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(fake_vector),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto())

    _, stored_vector, _ = vector_repo.upserts[0]
    assert stored_vector == fake_vector


async def test_embedding_service_llamado_una_vez_por_licitacion() -> None:
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(_make_dto())

    assert len(embedding_service.calls) == 1


async def test_texto_enviado_al_embedding_incluye_nombre_licitacion() -> None:
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(_make_dto())

    assert any(
        "Construcción de sede comunal" in text for text in embedding_service.calls[0]
    )


async def test_payload_qdrant_contiene_status_code_publicada() -> None:
    """El payload del punto en Qdrant tiene status_code='publicada' para licitaciones activas."""
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto(estado_codigo="publicada"))

    _, _, payload = vector_repo.upserts[0]
    assert payload["status_code"] == "publicada"


async def test_una_desierta_no_se_indexa_como_publicada():
    """La regresión que motivó el cambio a códigos de string.

    `id_estado = 6` es "desierta" en Compra Ágil v2, pero el mapa heredado de la
    API de Licitaciones lo traducía a "publicada". La licitación quedaba
    marcada como abierta y entraba en recomendaciones, ficha y alertas. Ahora el
    estado sale de `estado.codigo`, así que no hay traducción que equivocar.
    """
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto(status_code=6, estado_codigo="desierta"))

    _, _, payload = vector_repo.upserts[0]
    assert payload["status_code"] == "desierta"
    assert payload["status_code"] not in ACTIVE_TENDER_STATUSES


async def test_licitacion_duplicada_no_genera_upsert_en_qdrant() -> None:
    """Si el código ya existe en SQL no se llama a Qdrant."""

    class RepoConDuplicado(FakeTenderRepository):
        async def get_by_code(self, code: str) -> TenderModel:  # noqa: ARG002
            return TenderModel.__new__(TenderModel)  # simula que ya existe

    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=RepoConDuplicado(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto())

    assert len(vector_repo.upserts) == 0


# ---------------------------------------------------------------------------
# Resolución de comuna del comprador (path "a": nombre de municipalidad)
# ---------------------------------------------------------------------------


async def test_buyer_nuevo_con_nombre_municipal_reconocible_resuelve_comuna() -> None:
    repo = FakeTenderRepository()
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(_make_dto(organismo="I Municipalidad de Santiago"))

    assert len(repo.buyers_created) == 1
    buyer = repo.buyers_created[0]
    assert buyer["comuna_id"] == 295
    assert buyer["comuna_resolution_source"] == "organismo_name"


async def test_buyer_nuevo_sin_nombre_reconocible_no_resuelve_comuna() -> None:
    repo = FakeTenderRepository()
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(_make_dto(organismo="Servicio Electoral"))

    assert len(repo.buyers_created) == 1
    buyer = repo.buyers_created[0]
    assert buyer["comuna_id"] is None
    assert buyer["comuna_resolution_source"] is None


async def test_respaldo_generico_apagado_por_defecto() -> None:
    """ "Hospital de Lota" no matchea "Municipalidad de X", y sin habilitar el
    respaldo genérico (comportamiento por defecto) queda sin resolver."""
    repo = FakeTenderRepository(comuna_ids_by_name={"Lota": 151})
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(
        _make_dto(organismo="SERVICIO NACIONAL DE SALUD HOSPITAL DE LOTA")
    )

    assert len(repo.buyers_created) == 1
    buyer = repo.buyers_created[0]
    assert buyer["comuna_id"] is None
    assert buyer["comuna_resolution_source"] is None


async def test_buyer_nuevo_sin_nombre_municipal_cae_al_respaldo_generico_si_esta_habilitado() -> (
    None
):
    repo = FakeTenderRepository(comuna_ids_by_name={"Lota": 151})
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
        enable_comuna_generic_heuristic=True,
    )

    await use_case.execute(
        _make_dto(organismo="SERVICIO NACIONAL DE SALUD HOSPITAL DE LOTA")
    )

    assert len(repo.buyers_created) == 1
    buyer = repo.buyers_created[0]
    assert buyer["comuna_id"] == 151
    assert buyer["comuna_resolution_source"] == "organismo_name_generic"


async def test_heuristica_especifica_sigue_activa_con_el_respaldo_apagado() -> None:
    """El interruptor solo afecta al respaldo genérico -- "Municipalidad de X"
    corre siempre, esté prendido o apagado el respaldo."""
    repo = FakeTenderRepository()
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
        enable_comuna_generic_heuristic=False,
    )

    await use_case.execute(_make_dto(organismo="I Municipalidad de Santiago"))

    assert len(repo.buyers_created) == 1
    buyer = repo.buyers_created[0]
    assert buyer["comuna_id"] == 295
    assert buyer["comuna_resolution_source"] == "organismo_name"
