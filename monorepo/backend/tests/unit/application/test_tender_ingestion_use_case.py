"""
Tests unitarios de TenderIngestionUseCase.
Verifican que tras guardar cada licitación en SQL se genera su embedding
y se indexa en el repositorio vectorial (Qdrant).
"""

import calendar
from uuid import UUID

from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.tender import Tender
from app.domain.models.tender_ingestion_dto import TenderIngestaDTO
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeTenderVectorRepository,
)

# ---------------------------------------------------------------------------
# Fakes locales
# ---------------------------------------------------------------------------


class FakeIngestionService(ITenderIngestionService):
    def __init__(self, dtos: list[TenderIngestaDTO]) -> None:
        self._dtos = dtos

    async def fetch_public_tenders(self) -> list[TenderIngestaDTO]:
        return self._dtos


class FakeTenderRepository(ITenderRepository):
    """Repositorio SQL en memoria que deja pasar todas las operaciones."""

    def __init__(self) -> None:
        self.saved: list = []

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:  # noqa: ARG002
        return []

    async def get_by_code(self, code: str) -> TenderModel | None:  # noqa: ARG002
        return None

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:  # noqa: ARG002
        return rut

    async def get_or_create_status(self, status_id: int) -> int:
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


def _make_dto(
    code: str = "LIC-001",
    status_code: int = 1,
    region_id: int = 13,
    region_name: str = "Región Metropolitana de Santiago",
) -> TenderIngestaDTO:
    return TenderIngestaDTO.model_validate(
        {
            "CodigoExterno": code,
            "Nombre": "Construcción de sede comunal",
            "Descripcion": "Se requiere construir edificio de 2 pisos",
            "CodigoEstado": status_code,
            "FechaPublicacion": "2026-01-01T00:00:00",
            "FechaCierre": "2026-06-30T23:59:00",
            "RutComprador": "12.345.678-9",
            "NombreOrganismo": "Municipalidad de Santiago",
            "UnidadCompra": "Depto. Obras",
            "RegionId": region_id,
            "RegionUnidad": region_name,
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
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=vector_repo,
    )

    await use_case.execute()

    assert len(vector_repo.upserts) == 1


async def test_ingesta_dos_licitaciones_genera_dos_upserts() -> None:
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService(
            [_make_dto("LIC-001"), _make_dto("LIC-002")]
        ),
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute()

    assert len(vector_repo.upserts) == 2


async def test_vector_almacenado_proviene_del_embedding_service() -> None:
    """El vector en Qdrant es el que devuelve el EmbeddingService, no uno hardcodeado."""
    fake_vector = [0.7] * 1024
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(fake_vector),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute()

    _, stored_vector, _ = vector_repo.upserts[0]
    assert stored_vector == fake_vector


async def test_embedding_service_llamado_una_vez_por_licitacion() -> None:
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute()

    assert len(embedding_service.calls) == 1


async def test_texto_enviado_al_embedding_incluye_nombre_licitacion() -> None:
    embedding_service = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=FakeTenderRepository(),
        embedding_service=embedding_service,
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute()

    assert any(
        "Construcción de sede comunal" in text for text in embedding_service.calls[0]
    )


async def test_payload_qdrant_contiene_status_code_publicada() -> None:
    """El payload del punto en Qdrant tiene status_code='publicada' para licitaciones activas."""
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto(status_code=1)]),
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute()

    _, _, payload = vector_repo.upserts[0]
    assert payload["status_code"] == "publicada"


# ---------------------------------------------------------------------------
# Región: el id viene del DTO, no se deduce del nombre
# ---------------------------------------------------------------------------


class _RepoQueRegistraRegion(FakeTenderRepository):
    """Captura el region_id con que se crea la institución compradora."""

    def __init__(self) -> None:
        super().__init__()
        self.region_ids: list[int] = []

    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:
        self.region_ids.append(region_id)
        return await super().get_or_create_buyer(rut, name, region_id)


async def _ingesta(dto: TenderIngestaDTO) -> tuple[_RepoQueRegistraRegion, dict]:
    repo = _RepoQueRegistraRegion()
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([dto]),
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )
    await use_case.execute()
    _, _, payload = vector_repo.upserts[0]
    return repo, payload


async def test_la_institucion_usa_el_region_id_del_dto() -> None:
    repo, _ = await _ingesta(_make_dto(region_id=13))

    assert repo.region_ids == [13]


async def test_el_payload_de_qdrant_usa_el_region_id_del_dto() -> None:
    _, payload = await _ingesta(_make_dto(region_id=13))

    assert payload["region_id"] == 13


async def test_un_nombre_de_region_desconocido_ya_no_altera_el_id() -> None:
    """La regresión que motivó el cambio.

    Antes el id salía de buscar el nombre en una tabla de alias; cualquier
    grafía no contemplada caía en el valor por defecto (7, "Maule"). Ahora el
    nombre es solo para mostrar y el id viaja aparte.
    """
    repo, payload = await _ingesta(
        _make_dto(region_id=16, region_name="NOMBRE QUE NO ESTÁ EN NINGUNA TABLA")
    )

    assert repo.region_ids == [16]
    assert payload["region_id"] == 16


# ---------------------------------------------------------------------------
# Fechas en el payload: habilitan el pre-filtrado por rango en Qdrant
# ---------------------------------------------------------------------------


async def test_el_payload_lleva_las_fechas_como_epoch_utc() -> None:
    """Qdrant no compara `datetime`; el filtro de rango necesita enteros.

    El valor esperado se calcula con `timegm` —camino independiente del de la
    implementación— sobre la fecha ya normalizada a UTC naive por el DTO.
    """
    dto = _make_dto()
    _, payload = await _ingesta(dto)

    assert payload["closing_at"] == calendar.timegm(dto.closing_at.timetuple())
    assert payload["published_at"] == calendar.timegm(dto.published_at.timetuple())


async def test_las_fechas_del_payload_son_enteros() -> None:
    _, payload = await _ingesta(_make_dto())

    assert isinstance(payload["closing_at"], int)
    assert isinstance(payload["published_at"], int)


async def test_el_payload_conserva_los_campos_previos() -> None:
    """Agregar las fechas no debe alterar lo que ya se indexaba."""
    _, payload = await _ingesta(_make_dto())

    assert payload["status_code"] == "publicada"
    assert payload["region_id"] == 13
    assert payload["available_amount_clp"] == 50_000_000.0


async def test_licitacion_duplicada_no_genera_upsert_en_qdrant() -> None:
    """Si el código ya existe en SQL no se llama a Qdrant."""

    class RepoConDuplicado(FakeTenderRepository):
        async def get_by_code(self, code: str) -> TenderModel:  # noqa: ARG002
            return TenderModel.__new__(TenderModel)  # simula que ya existe

    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=RepoConDuplicado(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute()

    assert len(vector_repo.upserts) == 0


# ---------------------------------------------------------------------------
# Consistencia entre los dos almacenes
#
# La ingesta escribe en Postgres y en Qdrant sin una transacción común, así que
# siempre habrá una ventana en la que uno puede fallar tras el otro. Lo que sí
# se puede elegir es HACIA QUÉ LADO se rompe:
#
#   - Fila en SQL sin punto en Qdrant → la licitación es invisible para el
#     matching de forma permanente: Qdrant es el único punto de entrada del
#     pipeline y get_by_code impide que la ingesta la reintente.
#   - Punto en Qdrant sin fila en SQL → rank_tenders (paso 3.3.1) lo detecta y
#     lo elimina la próxima vez que aparece en una búsqueda.
#
# Por eso Qdrant se escribe primero: el único desbalance posible es el que el
# sistema ya sabe reconciliar solo.
# ---------------------------------------------------------------------------


class VectorRepoQueFalla(FakeTenderVectorRepository):
    """Simula Qdrant caído o rechazando la escritura."""

    async def upsert(
        self, tender_id: UUID, embedding: list[float], payload: dict
    ) -> None:
        raise ConnectionError("Qdrant no disponible")


async def test_si_qdrant_falla_la_licitacion_no_se_persiste_en_sql() -> None:
    """Sin vector no debe quedar fila: sería invisible para el matching para siempre."""
    repo = FakeTenderRepository()
    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=VectorRepoQueFalla(),
    )

    await use_case.execute()

    assert repo.saved == []


async def test_qdrant_se_escribe_antes_que_sql() -> None:
    """El orden importa: define hacia qué lado se rompe la consistencia."""
    orden: list[str] = []

    class RepoQueRegistra(FakeTenderRepository):
        async def save_complex_tender(
            self, tender_model: TenderModel, items: list[TenderItemModel]
        ) -> None:
            orden.append("sql")
            await super().save_complex_tender(tender_model, items)

    class VectorRepoQueRegistra(FakeTenderVectorRepository):
        async def upsert(
            self, tender_id: UUID, embedding: list[float], payload: dict
        ) -> None:
            orden.append("qdrant")
            await super().upsert(tender_id, embedding, payload)

    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=RepoQueRegistra(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=VectorRepoQueRegistra(),
    )

    await use_case.execute()

    assert orden == ["qdrant", "sql"]


async def test_el_embedding_se_calcula_antes_de_abrir_la_transaccion_sql() -> None:
    """El embedding tarda segundos en CPU; calcularlo tras el primer flush
    mantendría la transacción (y sus locks) abierta todo ese tiempo. No depende
    de la base, así que va antes."""
    orden: list[str] = []

    class RepoQueRegistra(FakeTenderRepository):
        async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str:
            orden.append("sql:buyer")
            return await super().get_or_create_buyer(rut, name, region_id)

        async def save_complex_tender(
            self, tender_model: TenderModel, items: list[TenderItemModel]
        ) -> None:
            orden.append("sql:commit")
            await super().save_complex_tender(tender_model, items)

    class EmbeddingQueRegistra(FakeEmbeddingService):
        async def embed(self, texts: list[str]) -> list[list[float]]:
            orden.append("embed")
            return await super().embed(texts)

    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=RepoQueRegistra(),
        embedding_service=EmbeddingQueRegistra(),
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute()

    assert orden == ["embed", "sql:buyer", "sql:commit"]


async def test_fallo_de_qdrant_hace_rollback_de_la_transaccion() -> None:
    """get_or_create_buyer/status hacen flush; hay que deshacerlos explícitamente."""
    rollbacks: list[int] = []

    class RepoQueCuentaRollbacks(FakeTenderRepository):
        async def rollback(self) -> None:
            rollbacks.append(1)

    use_case = TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=RepoQueCuentaRollbacks(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=VectorRepoQueFalla(),
    )

    await use_case.execute()

    assert len(rollbacks) == 1


# ---------------------------------------------------------------------------
# Visibilidad de los fallos
#
# El bloque `except` absorbe cada error con un print, así que una caída
# sistémica de Qdrant se veía idéntica a una corrida exitosa sin licitaciones
# nuevas. El resultado debe distinguir ambos casos.
# ---------------------------------------------------------------------------


async def test_las_licitaciones_fallidas_se_reportan_en_el_resultado() -> None:
    resultado = await TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto("LIC-001")]),
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=VectorRepoQueFalla(),
    ).execute()

    assert resultado["summary"]["failed"] == 1
    assert resultado["summary"]["failed_codes"] == ["LIC-001"]


async def test_el_estado_es_partial_cuando_hubo_fallos() -> None:
    """Una caída total de Qdrant no puede reportarse como 'success'."""
    resultado = await TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=VectorRepoQueFalla(),
    ).execute()

    assert resultado["status"] == "partial"


async def test_el_estado_sigue_siendo_success_sin_fallos() -> None:
    resultado = await TenderIngestionUseCase(
        ingestion_service=FakeIngestionService([_make_dto()]),
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
    ).execute()

    assert resultado["status"] == "success"
    assert resultado["summary"]["failed"] == 0
