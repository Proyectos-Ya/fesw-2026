"""
Tests unitarios de TenderIngestionUseCase.
Verifican que tras guardar cada licitación en SQL se genera su embedding
y se indexa en el repositorio vectorial (Qdrant).
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

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
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.fakes import (
    FakeEmbeddingPorTexto,
    FakeEmbeddingService,
    FakeLexicalTenderRepository,
    FakeTenderVectorRepository,
    InMemoryTenderItemVectorRepository,
)

# ---------------------------------------------------------------------------
# Fakes locales
# ---------------------------------------------------------------------------


class FakeTenderRepository(ITenderRepository):
    """Repositorio SQL en memoria que deja pasar todas las operaciones."""

    def __init__(
        self,
        comuna_ids_by_name: dict[str, int] | None = None,
        provincia_ids_by_comuna_id: dict[int, int] | None = None,
    ) -> None:
        self.items_reemplazados: list = []
        self.actualizadas: list = []
        self.saved: list = []
        self.buyers_created: list[dict] = []
        self._comuna_ids_by_name = comuna_ids_by_name or {"Santiago": 295}
        self._provincia_ids_by_comuna_id = provincia_ids_by_comuna_id or {295: 51}

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:  # noqa: ARG002
        return []

    async def get_items_by_tender_id(self, tender_id: UUID) -> list:
        return []

    async def replace_tender_items(self, tender_id: UUID, items: list) -> None:
        self.items_reemplazados = list(items)

    async def update_tender(self, tender) -> None:
        self.actualizadas.append(tender)

    async def get_expired_published_ids(self) -> list[UUID]:
        return []

    async def get_inactive_ids(self) -> list[UUID]:
        return []

    async def mark_as_closed(self, tender_ids: list[UUID]) -> None:
        self.cerradas.extend(tender_ids)

    async def get_by_code(self, code: str) -> TenderModel | None:  # noqa: ARG002
        return None

    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,  # noqa: ARG002
        limit: int,  # noqa: ARG002
        offset: int = 0,  # noqa: ARG002
        q: str | None = None,  # noqa: ARG002
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

    async def get_provincia_id_by_comuna_id(self, comuna_id: int) -> int | None:
        return self._provincia_ids_by_comuna_id.get(comuna_id)

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

    async def get_latest_ingestion_finished_at(self) -> datetime | None:
        return None


# Id fijo para las licitaciones que un fake finge tener ya guardadas.
_ID_EXISTENTE = uuid4()


def _make_dto(
    code: str = "LIC-001",
    status_code: int = 2,
    estado_codigo: str = "publicada",
    organismo: str = "Municipalidad de Santiago",
    nombre: str = "Construcción de sede comunal",
    monto: float = 50_000_000.0,
    items: list[dict] | None = None,
    documentos: list[dict] | None = None,
) -> TenderIngestaDTO:
    datos: dict = {
        "CodigoExterno": code,
        "Nombre": nombre,
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
        "MontoEstimado": monto,
        "items": items
        if items is not None
        else [
            {
                "nombre_producto": "Mano de obra",
                "cantidad": 10,
                "unidad_medida": "hh",
            },
        ],
    }
    # Sin la clave el DTO deja `documentos` en None: "la fuente no informa".
    if documentos is not None:
        datos["documentos"] = documentos
    return TenderIngestaDTO.model_validate(datos)


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


async def test_payload_qdrant_incluye_comuna_id_y_provincia_id_cuando_se_resuelve() -> (
    None
):
    """Filtrar `/tenders/search` por provincia/comuna se apoya en el payload de
    Qdrant (igual que región), así que ambos campos tienen que viajar ahí."""
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto(organismo="I Municipalidad de Santiago"))

    _, _, payload = vector_repo.upserts[0]
    assert payload["comuna_id"] == 295
    assert payload["provincia_id"] == 51


async def test_payload_qdrant_sin_comuna_resuelta_deja_esos_campos_en_none() -> None:
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto(organismo="Servicio Electoral"))

    _, _, payload = vector_repo.upserts[0]
    assert payload["comuna_id"] is None
    assert payload["provincia_id"] is None


async def test_una_desierta_no_se_indexa_como_publicada():
    """La regresión que motivó el cambio a códigos de string.

    `id_estado = 6` es "desierta" en Compra Ágil v2, pero el mapa heredado de la
    API de Licitaciones lo traducía a "publicada". La licitación quedaba
    marcada como abierta y entraba en recomendaciones, ficha y alertas. Ahora el
    estado sale de `estado.codigo`, y además una licitación no activa no entra
    al índice vectorial.
    """
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    await use_case.execute(_make_dto(status_code=6, estado_codigo="desierta"))

    assert all(
        p["status_code"] in ACTIVE_TENDER_STATUSES for _, _, p in vector_repo.upserts
    )


async def test_una_licitacion_que_llega_cerrada_se_guarda_sin_vector() -> None:
    """Qdrant guarda solo activas. Guardarla en SQL basta para la ficha y para
    el buscador, que resuelve las cerradas en Postgres; y no paga inferencia."""
    repo = FakeTenderRepository()
    vector_repo = FakeTenderVectorRepository()
    embedding = FakeEmbeddingService()
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=embedding,
        tender_vector_repo=vector_repo,
    )

    resultado = await use_case.execute(
        _make_dto(status_code=3, estado_codigo="cerrada")
    )

    assert resultado["status"] == "success"
    assert len(repo.saved) == 1
    assert vector_repo.upserts == []
    assert embedding.calls == []


async def test_una_licitacion_sin_cambios_no_toca_qdrant() -> None:
    """Un detalle idéntico al guardado no escribe en ningún lado.

    Este test decía antes "si el código ya existe no se llama a Qdrant", que era
    fijar el defecto 6.3: se pedía el endpoint de cambios y se descartaban los
    cambios. Ahora una licitación existente **sí** se actualiza; lo que se
    conserva de aquella intención —y es lo que de verdad importaba— es que un
    detalle sin novedades no pague una inferencia ni una escritura.

    Que no escriba tiene además una consecuencia que no es de rendimiento: mover
    `updated_at` sin motivo haría que el análisis de Gemini se regenerara para
    cada proveedor todos los días.
    """
    dto = _make_dto()

    class RepoSinCambios(FakeTenderRepository):
        """Ya tiene exactamente esta licitación, con sus mismas partidas."""

        async def get_by_code(self, code: str) -> TenderModel:  # noqa: ARG002
            return TenderModel(
                id=_ID_EXISTENTE,
                code=dto.code,
                name=dto.name,
                description=dto.description,
                status_id=dto.status_code,
                published_at=dto.published_at,
                closing_at=dto.closing_at,
                last_change_at=dto.published_at,
                buyer_rut=dto.buyer_rut,
                buyer_unit=dto.buyer_unit,
                available_amount_clp=dto.available_amount_clp,
            )

        async def get_items_by_tender_id(self, tender_id: UUID) -> list:  # noqa: ARG002
            return [
                TenderItemModel(
                    id=uuid4(),
                    tender_id=_ID_EXISTENTE,
                    product_code="0",
                    name=item.nombre_producto,
                    description=item.descripcion,
                    quantity=item.cantidad,
                    unit_of_measure=item.unidad_medida,
                )
                for item in dto.items
            ]

    repo = RepoSinCambios()
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=vector_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["status"] == "unchanged"
    assert vector_repo.upserts == []
    assert vector_repo.payloads == {}
    assert repo.actualizadas == []


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


# ---------------------------------------------------------------------------
# Vectores de partidas (uno por ítem, para el calce keyword ↔ partida)
# ---------------------------------------------------------------------------

_ITEMS_DOS_PARTIDAS = [
    {
        "nombre_producto": "Cemento",
        "descripcion": "Saco de 25 kg",
        "cantidad": 5,
        "unidad_medida": "sc",
    },
    {"nombre_producto": "Fierro", "cantidad": 2, "unidad_medida": "kg"},
]


class RepoQueTeniaLaLicitacion(FakeTenderRepository):
    """Ya tiene guardada `dto`, con las partidas y el monto que se le indiquen."""

    def __init__(
        self,
        dto: TenderIngestaDTO,
        *,
        items_guardados: list[TenderItemModel] | None = None,
        monto_guardado: float | None = None,
    ) -> None:
        super().__init__()
        self._dto = dto
        self._items = items_guardados if items_guardados is not None else []
        self._monto = (
            monto_guardado if monto_guardado is not None else dto.available_amount_clp
        )

    async def get_by_code(self, code: str) -> TenderModel:  # noqa: ARG002
        dto = self._dto
        return TenderModel(
            id=_ID_EXISTENTE,
            code=dto.code,
            name=dto.name,
            description=dto.description,
            status_id=dto.status_code,
            published_at=dto.published_at,
            closing_at=dto.closing_at,
            last_change_at=dto.published_at,
            buyer_rut=dto.buyer_rut,
            buyer_unit=dto.buyer_unit,
            available_amount_clp=self._monto,
            created_at=dto.published_at,
            updated_at=dto.published_at,
        )

    async def get_items_by_tender_id(self, tender_id: UUID) -> list:  # noqa: ARG002
        return list(self._items)


def _items_modelo(dto: TenderIngestaDTO) -> list[TenderItemModel]:
    """Las partidas de `dto` tal como quedarían guardadas en SQL."""
    return [
        TenderItemModel(
            id=uuid4(),
            tender_id=_ID_EXISTENTE,
            product_code="0",
            name=item.nombre_producto,
            description=item.descripcion,
            quantity=item.cantidad,
            unit_of_measure=item.unidad_medida,
        )
        for item in dto.items
    ]


async def test_alta_guarda_un_vector_por_partida() -> None:
    repo = FakeTenderRepository()
    item_repo = InMemoryTenderItemVectorRepository()
    embedding = FakeEmbeddingPorTexto(
        {"Cemento: Saco de 25 kg": [1.0, 0.0, 0.0], "Fierro": [0.0, 1.0, 0.0]}
    )
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=embedding,
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    await use_case.execute(_make_dto(items=_ITEMS_DOS_PARTIDAS))

    tender_model, _ = repo.saved[0]
    assert item_repo.vectors == {
        tender_model.id: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    }


async def test_alta_embebe_las_partidas_en_una_sola_llamada_aparte() -> None:
    """Un batch para las partidas, además del embedding del texto de la licitación."""
    embedding = FakeEmbeddingPorTexto()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding,
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=InMemoryTenderItemVectorRepository(),
    )

    await use_case.execute(_make_dto(items=_ITEMS_DOS_PARTIDAS))

    assert len(embedding.calls) == 2
    assert embedding.calls[1] == ["Cemento: Saco de 25 kg", "Fierro"]


async def test_alta_sin_partidas_no_embebe_y_deja_la_lista_vacia() -> None:
    """Sin partidas no hay nada que inferir: se llama a upsert con [] y no se paga
    otra llamada al modelo."""
    embedding = FakeEmbeddingPorTexto()
    item_repo = InMemoryTenderItemVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding,
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    await use_case.execute(_make_dto(items=[]))

    assert len(embedding.calls) == 1  # solo el de la licitación
    assert item_repo.vectors == {}


async def test_alta_escribe_los_vectores_de_partidas_antes_que_sql() -> None:
    """Mismo orden Qdrant → SQL que el vector de la licitación.

    Un desbalance hacia "vectores sin fila en SQL" lo limpia solo el ranking; el
    contrario dejaría una licitación en SQL sin partidas vectorizadas.
    """
    repo = FakeTenderRepository()
    guardadas_al_escribir: list[int] = []

    class ItemRepoEspia(InMemoryTenderItemVectorRepository):
        async def upsert(self, tender_id, item_vectors, payload=None) -> None:
            guardadas_al_escribir.append(len(repo.saved))
            await super().upsert(tender_id, item_vectors, payload)

    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=ItemRepoEspia(),
    )

    await use_case.execute(_make_dto(items=_ITEMS_DOS_PARTIDAS))

    assert guardadas_al_escribir == [0]
    assert len(repo.saved) == 1


async def test_alta_sin_repositorio_de_partidas_no_embebe_de_mas() -> None:
    """El repositorio es opcional: sin él la ingesta se comporta como siempre."""
    embedding = FakeEmbeddingPorTexto()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=embedding,
        tender_vector_repo=FakeTenderVectorRepository(),
    )

    await use_case.execute(_make_dto(items=_ITEMS_DOS_PARTIDAS))

    assert len(embedding.calls) == 1


async def test_cambio_semantico_regenera_los_vectores_de_partidas() -> None:
    """Si cambian las partidas, los vectores viejos ya no describen la licitación."""
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS)
    guardadas = _items_modelo(
        _make_dto(items=[{"nombre_producto": "Ladrillo", "cantidad": 1, "unidad_medida": "un"}])
    )
    item_repo = InMemoryTenderItemVectorRepository()
    await item_repo.upsert(_ID_EXISTENTE, [[9.0, 9.0, 9.0]])
    embedding = FakeEmbeddingPorTexto(
        {"Cemento: Saco de 25 kg": [1.0, 0.0, 0.0], "Fierro": [0.0, 1.0, 0.0]}
    )
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(dto, items_guardados=guardadas),
        embedding_service=embedding,
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["semantico"] is True
    assert item_repo.vectors == {_ID_EXISTENTE: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]}


async def test_cambio_semantico_que_deja_sin_partidas_borra_los_vectores() -> None:
    dto = _make_dto(items=[])
    guardadas = _items_modelo(_make_dto(items=_ITEMS_DOS_PARTIDAS))
    item_repo = InMemoryTenderItemVectorRepository()
    await item_repo.upsert(_ID_EXISTENTE, [[1.0, 0.0, 0.0]])
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(dto, items_guardados=guardadas),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    await use_case.execute(dto)

    assert item_repo.vectors == {}


async def test_cambio_solo_de_metadatos_no_toca_los_vectores_de_partidas() -> None:
    """Un cambio de monto no altera lo que la licitación pide: cero inferencias."""
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS, monto=80_000_000.0)
    item_repo = InMemoryTenderItemVectorRepository()
    await item_repo.upsert(_ID_EXISTENTE, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    embedding = FakeEmbeddingPorTexto()
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(
            dto,
            items_guardados=_items_modelo(dto),
            monto_guardado=50_000_000.0,
        ),
        embedding_service=embedding,
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["status"] == "updated"
    assert resultado["semantico"] is False
    assert embedding.calls == []
    assert item_repo.vectors == {_ID_EXISTENTE: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]}


async def test_sin_cambios_no_toca_los_vectores_de_partidas() -> None:
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS)
    item_repo = InMemoryTenderItemVectorRepository()
    await item_repo.upsert(_ID_EXISTENTE, [[1.0, 0.0, 0.0]])
    embedding = FakeEmbeddingPorTexto()
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(dto, items_guardados=_items_modelo(dto)),
        embedding_service=embedding,
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["status"] == "unchanged"
    assert embedding.calls == []
    assert item_repo.vectors == {_ID_EXISTENTE: [[1.0, 0.0, 0.0]]}


# ---------------------------------------------------------------------------
# Payload en las partidas (pre-filtro del segundo canal de recuperación)
#
# Las partidas viven en su propia colección; para buscar dentro de ella por estado,
# región o plazo el punto necesita el mismo payload que el de "tenders".
# ---------------------------------------------------------------------------


async def test_alta_guarda_las_partidas_con_el_mismo_payload_que_la_licitacion() -> None:
    vector_repo = FakeTenderVectorRepository()
    item_repo = InMemoryTenderItemVectorRepository()
    repo = FakeTenderRepository()
    use_case = TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=vector_repo,
        tender_item_vector_repo=item_repo,
    )

    await use_case.execute(_make_dto(items=_ITEMS_DOS_PARTIDAS))

    tender_model, _ = repo.saved[0]
    _, _, payload_licitacion = vector_repo.upserts[0]
    assert payload_licitacion["status_code"] == "publicada"
    assert payload_licitacion["comuna_id"] == 295
    assert item_repo.payloads[tender_model.id] == payload_licitacion


async def test_alta_sin_partidas_no_deja_payload_huerfano() -> None:
    item_repo = InMemoryTenderItemVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    await use_case.execute(_make_dto(items=[]))

    assert item_repo.payloads == {}


async def test_cambio_semantico_reescribe_las_partidas_con_el_payload_nuevo() -> None:
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS, monto=80_000_000.0)
    guardadas = _items_modelo(
        _make_dto(items=[{"nombre_producto": "Ladrillo", "cantidad": 1, "unidad_medida": "un"}])
    )
    vector_repo = FakeTenderVectorRepository()
    item_repo = InMemoryTenderItemVectorRepository()
    await item_repo.upsert(_ID_EXISTENTE, [[9.0, 9.0, 9.0]], {"status_code": "publicada"})
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(dto, items_guardados=guardadas),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=vector_repo,
        tender_item_vector_repo=item_repo,
    )

    await use_case.execute(dto)

    _, _, payload_licitacion = vector_repo.upserts[0]
    assert payload_licitacion["available_amount_clp"] == 80_000_000.0
    assert item_repo.payloads[_ID_EXISTENTE] == payload_licitacion


async def test_cambio_semantico_conserva_comuna_y_provincia_en_ambos_payloads() -> None:
    """Un cambio de texto reescribe el punto entero (`upsert`), no lo fusiona.

    El payload de `_actualizar` no llevaba `provincia_id` ni `comuna_id`: tras
    cualquier cambio de nombre, descripción o partidas, la licitación dejaba de
    aparecer al filtrar `/tenders/search` por provincia o comuna, y ahora también
    en el pre-filtro del canal de keywords (colección de partidas).
    """
    dto = _make_dto(organismo="I Municipalidad de Santiago", items=_ITEMS_DOS_PARTIDAS)
    guardadas = _items_modelo(
        _make_dto(items=[{"nombre_producto": "Ladrillo", "cantidad": 1, "unidad_medida": "un"}])
    )
    vector_repo = FakeTenderVectorRepository()
    item_repo = InMemoryTenderItemVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(dto, items_guardados=guardadas),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=vector_repo,
        tender_item_vector_repo=item_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["semantico"] is True
    _, _, payload_licitacion = vector_repo.upserts[0]
    assert payload_licitacion["comuna_id"] == 295
    assert payload_licitacion["provincia_id"] == 51
    assert item_repo.payloads[_ID_EXISTENTE] == payload_licitacion


async def test_cambio_de_metadatos_actualiza_el_payload_de_las_partidas_sin_tocar_vectores() -> (
    None
):
    """Es el caso frecuente (estado, cierre, monto): además del payload de
    "tenders", el de las partidas, o el pre-filtro del segundo canal quedaría
    apuntando a un estado o plazo viejos."""
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS, monto=80_000_000.0)
    vector_repo = FakeTenderVectorRepository()
    item_repo = InMemoryTenderItemVectorRepository()
    vectores = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    await item_repo.upsert(
        _ID_EXISTENTE, vectores, {"status_code": "publicada", "comuna_id": 295}
    )
    embedding = FakeEmbeddingPorTexto()
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(
            dto, items_guardados=_items_modelo(dto), monto_guardado=50_000_000.0
        ),
        embedding_service=embedding,
        tender_vector_repo=vector_repo,
        tender_item_vector_repo=item_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["semantico"] is False
    assert embedding.calls == []
    payload_licitacion = vector_repo.payloads[_ID_EXISTENTE]
    assert payload_licitacion["status_code"] == "publicada"
    assert payload_licitacion["available_amount_clp"] == 80_000_000.0
    # Mismas claves y valores en ambas colecciones; `comuna_id` (que este camino no
    # recalcula) se conserva porque `set_payload` fusiona.
    assert item_repo.payloads[_ID_EXISTENTE] == {**payload_licitacion, "comuna_id": 295}
    assert item_repo.vectors == {_ID_EXISTENTE: vectores}


async def test_cambio_de_metadatos_sin_punto_de_partidas_no_falla_ni_lo_crea() -> None:
    """Licitación ingestada antes de existir la colección y aún sin backfill."""
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS, monto=80_000_000.0)
    item_repo = InMemoryTenderItemVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(
            dto, items_guardados=_items_modelo(dto), monto_guardado=50_000_000.0
        ),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["status"] == "updated"
    assert item_repo.vectors == {}
    assert item_repo.payloads == {}


async def test_sin_cambios_no_toca_el_payload_de_las_partidas() -> None:
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS)
    item_repo = InMemoryTenderItemVectorRepository()
    await item_repo.upsert(_ID_EXISTENTE, [[1.0, 0.0, 0.0]], {"status_code": "otro"})
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(dto, items_guardados=_items_modelo(dto)),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=FakeTenderVectorRepository(),
        tender_item_vector_repo=item_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["status"] == "unchanged"
    assert item_repo.payloads == {_ID_EXISTENTE: {"status_code": "otro"}}


async def test_cambio_de_metadatos_sin_repositorio_de_partidas_sigue_funcionando() -> None:
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS, monto=80_000_000.0)
    vector_repo = FakeTenderVectorRepository()
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(
            dto, items_guardados=_items_modelo(dto), monto_guardado=50_000_000.0
        ),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=vector_repo,
    )

    resultado = await use_case.execute(dto)

    assert resultado["status"] == "updated"
    assert vector_repo.payloads[_ID_EXISTENTE]["available_amount_clp"] == 80_000_000.0


async def test_una_licitacion_que_se_cierra_pierde_tambien_sus_vectores_de_partidas() -> None:
    """Qdrant guarda solo activas, y el canal de keywords busca en `tender_items`:
    si ahí quedara el punto de una cerrada, seguiría ocupando cupos del ranking
    hasta que la limpieza de huérfanos lo encontrara."""
    guardada = _make_dto(items=_ITEMS_DOS_PARTIDAS)  # publicada e indexada
    dto = _make_dto(items=_ITEMS_DOS_PARTIDAS, status_code=3, estado_codigo="cerrada")
    vector_repo = FakeTenderVectorRepository()
    item_repo = InMemoryTenderItemVectorRepository()
    await item_repo.upsert(_ID_EXISTENTE, [[1.0, 0.0, 0.0]], {"status_code": "publicada"})
    use_case = TenderIngestionUseCase(
        repository=RepoQueTeniaLaLicitacion(guardada, items_guardados=_items_modelo(guardada)),
        embedding_service=FakeEmbeddingPorTexto(),
        tender_vector_repo=vector_repo,
        tender_item_vector_repo=item_repo,
    )

    await use_case.execute(dto)

    assert await item_repo.get_many([_ID_EXISTENTE]) == {}


# ---------------------------------------------------------------------------
# Lista oficial de anexos (plan 233, decisión 1)
# ---------------------------------------------------------------------------

_DOCS_BASES = [{"mp_document_id": 1, "nombre": "Bases.pdf"}]


def _caso_con_anexos(
    repo: FakeTenderRepository, anexos: InMemoryTenderAttachmentRepository | None
) -> TenderIngestionUseCase:
    return TenderIngestionUseCase(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
        attachment_repo=anexos,
    )


async def test_alta_guarda_la_lista_oficial() -> None:
    repo = FakeTenderRepository()
    anexos = InMemoryTenderAttachmentRepository()

    await _caso_con_anexos(repo, anexos).execute(_make_dto(documentos=_DOCS_BASES))

    assert len(anexos.llamadas) == 1
    assert list(anexos.llamadas[0][0]) == [repo.saved[0][0].id]


async def test_alta_sin_documentos_no_toca_la_lista() -> None:
    """`None` es "la fuente no informa": no se confunde con "sin anexos"."""
    anexos = InMemoryTenderAttachmentRepository()

    await _caso_con_anexos(FakeTenderRepository(), anexos).execute(
        _make_dto(documentos=None)
    )

    assert anexos.llamadas == []


async def test_alta_con_lista_vacia_la_sincroniza_vacia() -> None:
    repo = FakeTenderRepository()
    anexos = InMemoryTenderAttachmentRepository()

    await _caso_con_anexos(repo, anexos).execute(_make_dto(documentos=[]))

    assert anexos.llamadas[0][0] == {repo.saved[0][0].id: []}


async def test_sin_cambios_igual_refresca_los_anexos_sin_tocar_la_licitacion() -> None:
    """Escribe en `tender_attachment` y en `attachments_synced_at`, no en
    `updated_at`: el contrato de no regenerar el análisis se mantiene."""
    dto = _make_dto(documentos=_DOCS_BASES)
    repo = RepoQueTeniaLaLicitacion(dto, items_guardados=_items_modelo(dto))
    anexos = InMemoryTenderAttachmentRepository()

    resultado = await _caso_con_anexos(repo, anexos).execute(dto)

    assert resultado["status"] == "unchanged"
    assert repo.actualizadas == []
    assert list(anexos.llamadas[0][0]) == [_ID_EXISTENTE]


async def test_actualizacion_refresca_los_anexos() -> None:
    dto = _make_dto(documentos=_DOCS_BASES)
    repo = RepoQueTeniaLaLicitacion(
        dto, items_guardados=_items_modelo(dto), monto_guardado=1.0
    )
    anexos = InMemoryTenderAttachmentRepository()

    resultado = await _caso_con_anexos(repo, anexos).execute(dto)

    assert resultado["status"] == "updated"
    assert list(anexos.llamadas[0][0]) == [_ID_EXISTENTE]


async def test_los_anexos_van_despues_de_guardar_la_licitacion() -> None:
    """Hay clave foránea: la fila de `tender` tiene que existir antes."""
    log: list[str] = []

    class RepoQueAnotaElGuardado(FakeTenderRepository):
        async def save_complex_tender(self, tender_model, items) -> None:
            log.append("sql")
            await super().save_complex_tender(tender_model, items)

    anexos = InMemoryTenderAttachmentRepository(log=log)

    await _caso_con_anexos(RepoQueAnotaElGuardado(), anexos).execute(
        _make_dto(documentos=_DOCS_BASES)
    )

    assert log == ["sql", "anexos"]


async def test_si_fallan_los_anexos_hace_rollback_y_propaga() -> None:
    hizo_rollback = False

    class RepoConRollback(FakeTenderRepository):
        async def rollback(self) -> None:
            nonlocal hizo_rollback
            hizo_rollback = True

    anexos = InMemoryTenderAttachmentRepository(falla_con=RuntimeError("x"))

    with pytest.raises(RuntimeError):
        await _caso_con_anexos(RepoConRollback(), anexos).execute(
            _make_dto(documentos=_DOCS_BASES)
        )

    assert hizo_rollback is True


async def test_sin_repositorio_de_anexos_funciona_igual() -> None:
    resultado = await _caso_con_anexos(FakeTenderRepository(), None).execute(
        _make_dto(documentos=_DOCS_BASES)
    )

    assert resultado["status"] == "success"


# ---------------------------------------------------------------------------
# Tests del canal léxico sparse BM25 (plan 256)
# ---------------------------------------------------------------------------


async def test_ingesta_nueva_guarda_vector_lexico() -> None:
    """Una licitación nueva activa genera un upsert en el repositorio léxico con sparse vector."""
    lexical_repo = FakeLexicalTenderRepository()
    use_case = TenderIngestionUseCase(
        repository=FakeTenderRepository(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
        lexical_tender_repo=lexical_repo,
    )

    dto = _make_dto(
        code="LIC-LEX-01",
        nombre="Adquisición de amonio cuaternario y mascarillas",
    )
    res = await use_case.execute(dto)

    assert res["status"] == "success"
    assert len(lexical_repo.vectors) == 1
    tid, vec = next(iter(lexical_repo.vectors.items()))
    assert len(vec.indices) > 0
    assert len(vec.values) == len(vec.indices)
    assert lexical_repo.payloads[tid]["status_code"] == "publicada"
    assert lexical_repo.payloads[tid]["region_id"] == 13


async def test_actualizar_con_cambio_semantico_actualiza_vector_lexico() -> None:
    """Si cambia el texto de una licitación existente, se regenera el vector léxico."""
    tender_id = _ID_EXISTENTE
    existente = TenderModel(
        id=tender_id,
        code="LIC-001",
        name="Texto original",
        description="Descripcion vieja",
        status_id=2,
        published_at=datetime(2026, 1, 1),
        closing_at=datetime(2026, 6, 30),
        buyer_rut="12.345.678-9",
        buyer_unit="Depto",
        last_change_at=datetime(2026, 1, 1),
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    class RepoConExistente(FakeTenderRepository):
        async def get_by_code(self, code: str):
            return existente

    lexical_repo = FakeLexicalTenderRepository()
    use_case = TenderIngestionUseCase(
        repository=RepoConExistente(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
        lexical_tender_repo=lexical_repo,
    )

    dto = _make_dto(code="LIC-001", nombre="Nuevo título modificado con palabras distintas")
    res = await use_case.execute(dto)

    assert res["status"] == "updated"
    assert res["semantico"] is True
    assert tender_id in lexical_repo.vectors
    assert len(lexical_repo.vectors[tender_id].indices) > 0


async def test_actualizar_que_se_cierra_elimina_vector_lexico() -> None:
    """Una licitación que pasa a cerrada pierde su vector del canal léxico."""
    tender_id = _ID_EXISTENTE
    existente = TenderModel(
        id=tender_id,
        code="LIC-001",
        name="Texto original",
        description="Descripcion",
        status_id=2,  # publicada
        published_at=datetime(2026, 1, 1),
        closing_at=datetime(2026, 6, 30),
        buyer_rut="12.345.678-9",
        buyer_unit="Depto",
        last_change_at=datetime(2026, 1, 1),
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    class RepoConExistente(FakeTenderRepository):
        async def get_by_code(self, code: str):
            return existente

    lexical_repo = FakeLexicalTenderRepository()
    # Fingimos que ya existía en el repo léxico con índices dummy
    from app.application.services.lexical_tokenizer import SparseTermVector
    lexical_repo.vectors[tender_id] = SparseTermVector(indices=[10], values=[1.0])

    use_case = TenderIngestionUseCase(
        repository=RepoConExistente(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
        lexical_tender_repo=lexical_repo,
    )

    dto = _make_dto(code="LIC-001", status_code=5, estado_codigo="cerrada")
    res = await use_case.execute(dto)

    assert res["status"] == "updated"
    assert tender_id in lexical_repo.deleted
    assert tender_id not in lexical_repo.vectors


async def test_actualizar_solo_metadatos_actualiza_payload_lexico() -> None:
    """Un cambio solo de fecha o monto actualiza el payload léxico sin re-tokenizar."""
    tender_id = _ID_EXISTENTE
    existente = TenderModel(
        id=tender_id,
        code="LIC-001",
        name="Construcción de sede comunal",
        description="Se requiere construir edificio de 2 pisos",
        status_id=2,
        published_at=datetime(2026, 1, 1),
        closing_at=datetime(2026, 6, 30, 23, 59),
        buyer_rut="12.345.678-9",
        buyer_unit="Depto. Obras",
        available_amount_clp=50_000_000.0,
        last_change_at=datetime(2026, 1, 1),
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    class RepoConExistente(FakeTenderRepository):
        async def get_by_code(self, code: str):
            return existente

        async def get_items_by_tender_id(self, tid):
            return [
                TenderItemModel(
                    id=uuid4(),
                    tender_id=tid,
                    product_code="0",
                    name="Mano de obra",
                    description=None,
                    quantity=10,
                    unit_of_measure="hh",
                )
            ]

    lexical_repo = FakeLexicalTenderRepository()
    from app.application.services.lexical_tokenizer import LexicalTokenizer
    tokenizer = LexicalTokenizer()
    lexical_repo.vectors[tender_id] = tokenizer.encode_sparse("Construcción de sede comunal")

    use_case = TenderIngestionUseCase(
        repository=RepoConExistente(),
        embedding_service=FakeEmbeddingService(),
        tender_vector_repo=FakeTenderVectorRepository(),
        lexical_tender_repo=lexical_repo,
    )

    # Solo cambia el monto estimado
    dto = _make_dto(code="LIC-001", monto=80_000_000.0)
    res = await use_case.execute(dto)

    assert res["status"] == "updated"
    assert res["semantico"] is False
    assert lexical_repo.payloads[tender_id]["available_amount_clp"] == 80_000_000.0
