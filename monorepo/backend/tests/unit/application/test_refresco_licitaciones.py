"""Una licitación que ya está en la base tiene que poder actualizarse.

`TenderIngestionUseCase` hacía `get_by_code` y, si la encontraba, devolvía
`skipped`. Se le pide a Mercado Público el endpoint de **cambios** y se
descartaban justamente los cambios: variaciones de monto, de fecha de cierre o
de estado no se reflejaban nunca, y el dashboard mostraba para siempre lo que se
vio el día de la ingesta.

La distinción que gobierna todo esto es entre dos clases de cambio:

- **Semántico** (`name`, `description`, `items`): es lo que consume
  `TextBuilder`, así que cambia el vector y hay que pagar una inferencia.
- **De metadatos** (estado, cierre, monto): no cambia lo que la licitación pide.
  Basta actualizar SQL y el payload de Qdrant, que es mucho más barato — y es
  el caso frecuente, porque lo que se mueve a diario son las fechas y el estado.

Detectar cuál es cuál no necesita una columna nueva: se reconstruye el texto
desde la fila persistida y se compara con el que saldría del detalle nuevo.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.tender_ingestion_use_case import TenderIngestionUseCase
from app.domain.models.tender_ingestion_dto import ItemLicitacionDTO, TenderIngestaDTO
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel

from .fakes import FakeEmbeddingService, FakeTenderVectorRepository
from .test_tender_ingestion_use_case import FakeTenderRepository

pytestmark = pytest.mark.asyncio

AHORA = datetime(2026, 9, 1, 12, tzinfo=UTC).replace(tzinfo=None)


def _dto(**cambios) -> TenderIngestaDTO:
    base = dict(
        CodigoExterno="COD-1",
        Nombre="Servicio de aseo",
        Descripcion="Aseo de dependencias",
        CodigoEstado=2,
        EstadoCodigo="publicada",
        FechaPublicacion=AHORA - timedelta(days=5),
        FechaCierre=AHORA + timedelta(days=5),
        RutComprador="60.000.000-0",
        NombreOrganismo="Municipalidad de Santiago",
        UnidadCompra="Abastecimiento",
        RegionId=13,
        RegionUnidad="Región Metropolitana de Santiago",
        MontoEstimado=1_000_000.0,
        items=[
            ItemLicitacionDTO(
                codigo_unspsc=4321,
                codigo_categoria=None,
                categoria=None,
                nombre_producto="Detergente",
                descripcion="Bidón de 5 litros",
                cantidad=10,
                unidad_medida="UN",
            )
        ],
    )
    base.update(cambios)
    return TenderIngestaDTO(**base)  # type: ignore[arg-type]


class RepoConLicitacion(FakeTenderRepository):
    """Repositorio que ya tiene la licitación, y anota cómo se la actualizó."""

    def __init__(self, dto: TenderIngestaDTO):
        super().__init__()
        self.tender_id = uuid.uuid4()
        self.existente = TenderModel(
            id=self.tender_id,
            code=dto.code,
            name=dto.name,
            description=dto.description,
            status_id=dto.status_code,
            published_at=dto.published_at,
            closing_at=dto.closing_at,
            last_change_at=AHORA,
            buyer_rut=dto.buyer_rut,
            buyer_unit=dto.buyer_unit,
            available_amount_clp=dto.available_amount_clp,
            created_at=AHORA,
            updated_at=AHORA,
        )
        self.items = [
            TenderItemModel(
                id=uuid.uuid4(),
                tender_id=self.tender_id,
                product_code=str(i.codigo_unspsc),
                name=i.nombre_producto,
                description=i.descripcion,
                quantity=i.cantidad,
                unit_of_measure=i.unidad_medida,
            )
            for i in dto.items
        ]
        self.actualizada = False
        self.items_reemplazados: list[list[TenderItemModel]] = []

    async def get_by_code(self, code: str) -> TenderModel | None:
        return self.existente if code == self.existente.code else None

    async def get_items_by_tender_id(self, tender_id):
        return list(self.items) if tender_id == self.tender_id else []

    async def replace_tender_items(self, tender_id, items):
        self.items = list(items)
        self.items_reemplazados.append(list(items))

    async def update_tender(self, tender):
        self.actualizada = True


def _caso(repo, embedding, vector_repo) -> TenderIngestionUseCase:
    return TenderIngestionUseCase(
        repository=repo,
        embedding_service=embedding,
        tender_vector_repo=vector_repo,
    )


class TestCambioDeMetadatos:
    async def test_un_cambio_de_monto_no_recalcula_el_embedding(self):
        """Lo caro es la inferencia, y el monto no cambia lo que se pide."""
        original = _dto()
        repo = RepoConLicitacion(original)
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(
            _dto(MontoEstimado=2_000_000.0)
        )

        assert resultado["status"] == "updated"
        assert emb.calls == []
        assert vec.upserts == []

    async def test_un_cambio_de_monto_si_actualiza_el_payload(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto(MontoEstimado=2_000_000.0))

        assert vec.payloads[repo.tender_id]["available_amount_clp"] == 2_000_000.0

    async def test_un_cambio_de_estado_se_refleja_en_sql_y_en_el_payload(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(
            _dto(CodigoEstado=3, EstadoCodigo="cerrada")
        )

        assert repo.existente.status_id == 3
        assert vec.payloads[repo.tender_id]["status_code"] == "cerrada"
        assert emb.calls == []

    async def test_un_cambio_de_fecha_de_cierre_se_propaga(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()
        # Se compara contra el DTO ya construido y no contra la fecha cruda: el
        # DTO normaliza a UTC en el borde, interpretando los naive como hora de
        # Chile (ver `normalize_to_utc`). Comparar contra la entrada sin
        # normalizar mediría el desfase de zona, no la propagación.
        con_otro_cierre = _dto(FechaCierre=AHORA + timedelta(days=20))

        await _caso(repo, emb, vec).execute(con_otro_cierre)

        assert repo.existente.closing_at == con_otro_cierre.closing_at
        assert emb.calls == []


class TestCambioSemantico:
    async def test_un_cambio_de_descripcion_recalcula_el_embedding(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(
            _dto(Descripcion="Ahora también incluye jardinería")
        )

        assert resultado["status"] == "updated"
        assert len(emb.calls) == 1
        assert [t for t, _, _ in vec.upserts] == [repo.tender_id]

    async def test_un_cambio_de_nombre_recalcula_el_embedding(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        await _caso(repo, emb, vec).execute(_dto(Nombre="Servicio de jardinería"))

        assert len(emb.calls) == 1

    async def test_cambiar_las_partidas_recalcula_el_embedding(self):
        """Las partidas dicen qué se pide de verdad; entran al texto."""
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()
        otros_items = [
            ItemLicitacionDTO(
                codigo_unspsc=9999,
                codigo_categoria=None,
                categoria=None,
                nombre_producto="Cortadora de pasto",
                descripcion=None,
                cantidad=1,
                unidad_medida="UN",
            )
        ]

        await _caso(repo, emb, vec).execute(_dto(items=otros_items))

        assert len(emb.calls) == 1
        assert len(repo.items_reemplazados) == 1
        assert repo.items[0].name == "Cortadora de pasto"

    async def test_las_partidas_se_reemplazan_enteras_sin_duplicar(self):
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()
        dos_items = _dto().items + [
            ItemLicitacionDTO(
                codigo_unspsc=1111,
                codigo_categoria=None,
                categoria=None,
                nombre_producto="Escobas",
                descripcion=None,
                cantidad=3,
                unidad_medida="UN",
            )
        ]

        await _caso(repo, emb, vec).execute(_dto(items=dos_items))

        assert len(repo.items) == 2


class TestSinCambios:
    async def test_un_detalle_identico_no_escribe_nada(self):
        """Clave para 6.4: mover `updated_at` invalidaría todos los análisis.

        Si cada corrida diaria tocara la fila, Gemini regeneraría el análisis de
        cada licitación para cada proveedor todos los días sin motivo.
        """
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()

        resultado = await _caso(repo, emb, vec).execute(_dto())

        assert resultado["status"] == "unchanged"
        assert repo.actualizada is False
        assert emb.calls == []
        assert vec.upserts == []
        assert vec.payloads == {}
        assert repo.existente.updated_at == AHORA


class TestOrdenDeEscritura:
    async def test_el_vector_se_escribe_antes_que_sql(self):
        """Mismo criterio que en el alta: si SQL falla, la próxima corrida
        vuelve a detectar la diferencia y se autocorrige."""
        repo = RepoConLicitacion(_dto())
        emb, vec = FakeEmbeddingService(), FakeTenderVectorRepository()
        orden: list[str] = []

        upsert_real = vec.upsert

        async def upsert_espia(*a, **kw):
            orden.append("qdrant")
            return await upsert_real(*a, **kw)

        async def update_espia(tender):
            orden.append("sql")

        vec.upsert = upsert_espia  # type: ignore[method-assign]
        repo.update_tender = update_espia  # type: ignore[method-assign]

        await _caso(repo, emb, vec).execute(_dto(Descripcion="otra cosa"))

        assert orden == ["qdrant", "sql"]
