"""Pruebas del servicio que calcula la compatibilidad proveedor/licitación.

Es la fórmula que antes vivía dentro de `RankTendersUseCase`: la comparten el
ranking (muchas candidatas) y el cálculo a pedido (una sola).

El puntaje sale de tres señales: R (reranker con consulta corta), B (mejor calce
keyword ↔ partida) y C (cobertura de partidas). Los tests que distinguen buenos de
malos calces usan `FakeEmbeddingPorTexto`, que da un vector distinto por texto;
con el doble de siempre todo se parece a todo y B y C valdrían 1 para cualquiera.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.compatibility_formula import item_match_signals
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.reranker_service import IRerankerService
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.domain.errors.matching_errors import ScoreCalculationError
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    FORMULA_DE_PRUEBA,
    FakeEmbeddingPorTexto,
    FakeEmbeddingService,
    FakeRerankerService,
    InMemoryMatchingResultRepository,
    InMemoryTenderItemVectorRepository,
    armar_scorer,
)

FORMULA = FORMULA_DE_PRUEBA
MODEL_VERSION = "bge-m3+compat-calib-v1"

# Vectores ortogonales de 3 dimensiones: cemento, fierro y "otra cosa".
CEMENTO = [1.0, 0.0, 0.0]
FIERRO = [0.0, 1.0, 0.0]
OTRO = [0.0, 0.0, 1.0]


def crear_licitacion(
    tender_id: UUID,
    nombre: str = "Servicio de aseo",
    descripcion: str | None = "Aseo de oficinas",
    partidas: list[tuple[str, str | None]] | None = None,
) -> Tender:
    ahora = datetime.now(UTC).replace(tzinfo=None)
    return Tender(
        id=tender_id,
        code=f"COT-{tender_id}",
        name=nombre,
        description=descripcion,
        status_id=1,
        status_code=TENDER_STATUSES["PUBLISHED"],
        published_at=ahora - timedelta(days=1),
        closing_at=ahora + timedelta(days=2),
        last_change_at=ahora,
        buyer_rut="12.345.678-9",
        buyer_name="Municipalidad de Santiago",
        buyer_unit="TI",
        items=[
            TenderItem(
                tender_id=tender_id,
                product_code="0",
                name=nombre_partida,
                description=descripcion_partida,
                quantity=1,
                unit_of_measure="UN",
            )
            for nombre_partida, descripcion_partida in (partidas or [])
        ],
    )


def crear_proveedor(**kwargs) -> Supplier:
    datos = {"rut": "76086428-5", "legal_name": "Empresa SpA", "user_id": uuid4()}
    datos.update(kwargs)
    return Supplier(**datos)


def crear_scorer(
    reranker: IRerankerService | None = None,
    repo: InMemoryMatchingResultRepository | None = None,
    embedding: FakeEmbeddingService | FakeEmbeddingPorTexto | None = None,
    item_repo: InMemoryTenderItemVectorRepository | None = None,
) -> tuple[CompatibilityScorer, InMemoryMatchingResultRepository]:
    repo = repo or InMemoryMatchingResultRepository()
    scorer = armar_scorer(
        reranker=reranker,
        matching_result_repo=repo,
        embedding=embedding,
        item_repo=item_repo,
        model_version=MODEL_VERSION,
    )
    return scorer, repo


class RerankerVacio(FakeRerankerService):
    """Simula un reranker que no devuelve la candidata que se le mandó."""

    async def rerank(self, query_text, candidates, limit):  # noqa: ANN001, ARG002
        return []


class RerankerPorDocumento(IRerankerService):
    """Puntúa cada par por su texto, sin mirar a los demás: como el real."""

    def __init__(self, puntajes: dict[str, float] | None = None) -> None:
        self.puntajes = puntajes or {}

    async def rerank(
        self, query_text: str, candidates: list[tuple[UUID, str]], limit: int
    ) -> list[tuple[UUID, float]]:
        pares = [(uid, self.puntajes.get(doc, 0.6)) for uid, doc in candidates]
        return sorted(pares, key=lambda par: par[1], reverse=True)[:limit]


# ---------------------------------------------------------------------------
# score_many: qué se le pide al reranker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_many_puntua_todas_las_candidatas() -> None:
    scorer, _ = crear_scorer()
    licitaciones = [crear_licitacion(uuid4()) for _ in range(3)]

    resultados = await scorer.score_many(crear_proveedor(), licitaciones, limit=3)

    assert [r.tender_id for r in resultados] == [t.id for t in licitaciones]
    assert all(r.reranker_score is not None for r in resultados)
    # Con vectores idénticos B y C valen lo mismo para todas: manda el reranker.
    assert resultados[0].final_score > resultados[1].final_score


@pytest.mark.asyncio
async def test_score_many_respeta_el_limite() -> None:
    scorer, _ = crear_scorer()
    licitaciones = [crear_licitacion(uuid4()) for _ in range(5)]

    resultados = await scorer.score_many(crear_proveedor(), licitaciones, limit=2)

    assert len(resultados) == 2


@pytest.mark.asyncio
async def test_score_many_rerankea_todas_aunque_el_limite_sea_menor() -> None:
    """El corte ya no lo hace el reranker: hace falta R de cada candidata para
    combinarlo con B y C, y recién después se queda con las mejores."""
    reranker = FakeRerankerService()
    scorer, _ = crear_scorer(reranker=reranker)
    licitaciones = [crear_licitacion(uuid4()) for _ in range(5)]

    await scorer.score_many(crear_proveedor(), licitaciones, limit=2)

    assert len(reranker.calls) == 1
    _, candidatos, limite = reranker.calls[0]
    assert len(candidatos) == 5
    assert limite == 5


@pytest.mark.asyncio
async def test_score_many_rerankea_con_la_consulta_corta() -> None:
    reranker = FakeRerankerService()
    scorer, _ = crear_scorer(reranker=reranker)
    proveedor = crear_proveedor(
        sectors=["Construcción"], keywords=["cemento", "fierro"]
    )

    await scorer.score_many(proveedor, [crear_licitacion(uuid4())], limit=1)

    consulta, _, _ = reranker.calls[0]
    assert consulta == "Rubro: Construcción. Productos: cemento, fierro."


@pytest.mark.asyncio
async def test_score_many_rerankea_contra_el_documento_completo_de_la_licitacion() -> None:
    reranker = FakeRerankerService()
    scorer, _ = crear_scorer(reranker=reranker)
    licitacion = crear_licitacion(uuid4(), partidas=[("Cemento", "Saco de 25 kg")])

    await scorer.score_many(crear_proveedor(), [licitacion], limit=1)

    _, candidatos, _ = reranker.calls[0]
    assert candidatos == [
        (
            licitacion.id,
            "Servicio de aseo. Aseo de oficinas. Items: Cemento: Saco de 25 kg",
        )
    ]


@pytest.mark.asyncio
async def test_score_many_sin_candidatas_no_llama_a_nadie() -> None:
    reranker = FakeRerankerService()
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(reranker=reranker, embedding=embedding)

    assert await scorer.score_many(crear_proveedor(), [], limit=5) == []
    assert reranker.calls == []
    assert embedding.calls == []


# ---------------------------------------------------------------------------
# score_many: la fórmula con R, B y C
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_puntaje_final_es_la_formula_aplicada_a_r_b_y_c() -> None:
    """Se recalcula a mano con las piezas ya probadas por separado."""
    item_repo = InMemoryTenderItemVectorRepository()
    licitacion = crear_licitacion(uuid4(), partidas=[("Cemento", None), ("Pintura", None)])
    await item_repo.upsert(licitacion.id, [CEMENTO, OTRO])
    embedding = FakeEmbeddingPorTexto({"cemento": CEMENTO, "fierro": FIERRO})
    scorer, _ = crear_scorer(
        reranker=RerankerPorDocumento(), embedding=embedding, item_repo=item_repo
    )
    proveedor = crear_proveedor(keywords=["cemento", "fierro"])

    [resultado] = await scorer.score_many(proveedor, [licitacion], limit=1)

    b, c = item_match_signals([CEMENTO, FIERRO], [CEMENTO, OTRO])
    assert (b, c) == pytest.approx((1.0, 0.5))
    assert resultado.reranker_score == pytest.approx(0.6)
    assert resultado.final_score == pytest.approx(FORMULA.score(0.6, b, c))


@pytest.mark.asyncio
async def test_un_buen_calce_de_partidas_supera_a_un_reranker_mas_alto() -> None:
    """El punto de la fórmula nueva: el reranker solo no alcanza (AUC 0,54-0,65)."""
    item_repo = InMemoryTenderItemVectorRepository()
    calza = crear_licitacion(uuid4(), nombre="Obra", partidas=[("Cemento", None)])
    no_calza = crear_licitacion(uuid4(), nombre="Aseo", partidas=[("Escobas", None)])
    await item_repo.upsert(calza.id, [CEMENTO])
    await item_repo.upsert(no_calza.id, [OTRO])
    # El reranker prefiere la que no calza.
    reranker = RerankerPorDocumento(
        {
            "Obra. Aseo de oficinas. Items: Cemento": 0.55,
            "Aseo. Aseo de oficinas. Items: Escobas": 0.9,
        }
    )
    scorer, _ = crear_scorer(
        reranker=reranker,
        embedding=FakeEmbeddingPorTexto({"cemento": CEMENTO}),
        item_repo=item_repo,
    )

    resultados = await scorer.score_many(
        crear_proveedor(keywords=["cemento"]), [no_calza, calza], limit=2
    )

    assert [r.tender_id for r in resultados] == [calza.id, no_calza.id]
    por_id = {r.tender_id: r for r in resultados}
    assert por_id[no_calza.id].reranker_score > por_id[calza.id].reranker_score  # type: ignore[operator]
    assert por_id[calza.id].final_score > por_id[no_calza.id].final_score


@pytest.mark.asyncio
async def test_el_limite_se_aplica_despues_de_puntuar() -> None:
    """Las `limit` mejores por puntaje final, no las primeras del reranker."""
    item_repo = InMemoryTenderItemVectorRepository()
    licitaciones = [crear_licitacion(uuid4(), nombre=f"L{i}") for i in range(3)]
    # Solo la última calza con lo que ofrece el proveedor.
    await item_repo.upsert(licitaciones[0].id, [OTRO])
    await item_repo.upsert(licitaciones[1].id, [OTRO])
    await item_repo.upsert(licitaciones[2].id, [CEMENTO])
    scorer, _ = crear_scorer(
        reranker=RerankerPorDocumento(),
        embedding=FakeEmbeddingPorTexto({"cemento": CEMENTO}),
        item_repo=item_repo,
    )

    resultados = await scorer.score_many(
        crear_proveedor(keywords=["cemento"]), licitaciones, limit=1
    )

    assert [r.tender_id for r in resultados] == [licitaciones[2].id]


@pytest.mark.asyncio
async def test_el_tamano_del_lote_no_cambia_el_resultado() -> None:
    """Puntuar una licitación sola o entre otras da el mismo número.

    Es lo que garantiza que dashboard y ficha muestren el mismo porcentaje: ni el
    reranker (puntúa cada par por separado) ni la fórmula normalizan contra el lote.
    """
    item_repo = InMemoryTenderItemVectorRepository()
    licitaciones = [
        crear_licitacion(uuid4(), nombre=f"L{i}", partidas=[(f"P{i}", None)])
        for i in range(4)
    ]
    for licitacion, vector in zip(
        licitaciones, [CEMENTO, FIERRO, OTRO, [1.0, 1.0, 0.0]], strict=True
    ):
        await item_repo.upsert(licitacion.id, [vector])
    embedding = FakeEmbeddingPorTexto({"cemento": CEMENTO})
    proveedor = crear_proveedor(keywords=["cemento"])
    reranker = RerankerPorDocumento(
        {
            "L0. Aseo de oficinas. Items: P0": 0.8,
            "L1. Aseo de oficinas. Items: P1": 0.4,
            "L2. Aseo de oficinas. Items: P2": 0.7,
        }
    )
    scorer, _ = crear_scorer(reranker=reranker, embedding=embedding, item_repo=item_repo)

    en_lote = {
        r.tender_id: r.final_score
        for r in await scorer.score_many(proveedor, licitaciones, limit=4)
    }
    for licitacion in licitaciones:
        [sola] = await scorer.score_many(proveedor, [licitacion], limit=1)
        assert sola.final_score == pytest.approx(en_lote[licitacion.id])


@pytest.mark.asyncio
async def test_una_candidata_que_el_reranker_no_devuelve_se_omite() -> None:
    scorer, _ = crear_scorer(reranker=RerankerVacio())

    assert await scorer.score_many(crear_proveedor(), [crear_licitacion(uuid4())], 1) == []


# ---------------------------------------------------------------------------
# score_many: de dónde salen los vectores de keywords
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_los_vectores_de_keywords_salen_de_una_sola_llamada_sin_vacias() -> None:
    item_repo = InMemoryTenderItemVectorRepository()
    licitacion = crear_licitacion(uuid4())
    await item_repo.upsert(licitacion.id, [CEMENTO])
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(embedding=embedding, item_repo=item_repo)
    proveedor = crear_proveedor(keywords=["cemento", "", "  ", "fierro"])

    await scorer.score_many(proveedor, [licitacion], limit=1)

    assert embedding.calls == [["cemento", "fierro"]]


@pytest.mark.asyncio
async def test_sin_keywords_usa_la_descripcion() -> None:
    item_repo = InMemoryTenderItemVectorRepository()
    licitacion = crear_licitacion(uuid4())
    await item_repo.upsert(licitacion.id, [CEMENTO])
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(embedding=embedding, item_repo=item_repo)
    proveedor = crear_proveedor(keywords=[], description="Venta de materiales")

    await scorer.score_many(proveedor, [licitacion], limit=1)

    assert embedding.calls == [["Venta de materiales"]]


@pytest.mark.asyncio
async def test_sin_keywords_ni_descripcion_usa_la_razon_social() -> None:
    item_repo = InMemoryTenderItemVectorRepository()
    licitacion = crear_licitacion(uuid4())
    await item_repo.upsert(licitacion.id, [CEMENTO])
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(embedding=embedding, item_repo=item_repo)

    await scorer.score_many(crear_proveedor(), [licitacion], limit=1)

    assert embedding.calls == [["Empresa SpA"]]


# ---------------------------------------------------------------------------
# score_many: de dónde salen los vectores de partidas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_con_vectores_guardados_no_se_embeben_las_partidas() -> None:
    item_repo = InMemoryTenderItemVectorRepository()
    licitaciones = [
        crear_licitacion(uuid4(), partidas=[("Cemento", None)]) for _ in range(3)
    ]
    for licitacion in licitaciones:
        await item_repo.upsert(licitacion.id, [CEMENTO])
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(embedding=embedding, item_repo=item_repo)

    await scorer.score_many(crear_proveedor(keywords=["cemento"]), licitaciones, 3)

    assert embedding.calls == [["cemento"]]  # solo las keywords


@pytest.mark.asyncio
async def test_las_que_faltan_se_embeben_en_un_solo_lote() -> None:
    """Licitaciones aún no reindexadas: una llamada para todas, no una por cada una."""
    item_repo = InMemoryTenderItemVectorRepository()
    con_vectores = crear_licitacion(uuid4(), partidas=[("Cemento", None)])
    await item_repo.upsert(con_vectores.id, [CEMENTO])
    sin_vectores_a = crear_licitacion(
        uuid4(), partidas=[("Fierro", "Barra de 8 mm"), ("Pintura", None)]
    )
    sin_vectores_b = crear_licitacion(uuid4(), partidas=[("Cemento", None)])
    embedding = FakeEmbeddingPorTexto(
        {
            "cemento": CEMENTO,
            "Fierro: Barra de 8 mm": FIERRO,
            "Pintura": OTRO,
            "Cemento": CEMENTO,
        }
    )
    scorer, _ = crear_scorer(
        reranker=RerankerPorDocumento(), embedding=embedding, item_repo=item_repo
    )
    proveedor = crear_proveedor(keywords=["cemento"])

    resultados = await scorer.score_many(
        proveedor, [con_vectores, sin_vectores_a, sin_vectores_b], limit=3
    )

    assert embedding.calls == [
        ["cemento"],
        ["Fierro: Barra de 8 mm", "Pintura", "Cemento"],
    ]
    # Y el calce se calcula con lo recién embebido, repartido a cada licitación.
    por_id = {r.tender_id: r.final_score for r in resultados}
    b_a, c_a = item_match_signals([CEMENTO], [FIERRO, OTRO])
    b_b, c_b = item_match_signals([CEMENTO], [CEMENTO])
    assert por_id[sin_vectores_a.id] == pytest.approx(FORMULA.score(0.6, b_a, c_a))
    assert por_id[sin_vectores_b.id] == pytest.approx(FORMULA.score(0.6, b_b, c_b))


@pytest.mark.asyncio
async def test_lo_embebido_al_vuelo_no_se_persiste() -> None:
    """Es un camino de lectura: los vectores los llena la ingesta o el backfill.

    Escribir desde acá haría que un GET /tenders/recommended toque Qdrant y que
    dos peticiones concurrentes se pisen reemplazando el mismo punto.
    """
    item_repo = InMemoryTenderItemVectorRepository()
    licitacion = crear_licitacion(uuid4(), partidas=[("Cemento", None)])
    scorer, _ = crear_scorer(
        embedding=FakeEmbeddingPorTexto({"Cemento": CEMENTO}), item_repo=item_repo
    )

    await scorer.score_many(crear_proveedor(keywords=["cemento"]), [licitacion], 1)

    assert item_repo.vectors == {}


@pytest.mark.asyncio
async def test_sin_partidas_se_embebe_el_nombre_y_la_descripcion() -> None:
    licitacion = crear_licitacion(
        uuid4(), nombre="Compra de cemento", descripcion="Para la sede", partidas=[]
    )
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(embedding=embedding)

    await scorer.score_many(crear_proveedor(keywords=["cemento"]), [licitacion], 1)

    assert embedding.calls[1] == ["Compra de cemento. Para la sede"]


@pytest.mark.asyncio
async def test_sin_partidas_ni_descripcion_se_embebe_solo_el_nombre() -> None:
    licitacion = crear_licitacion(
        uuid4(), nombre="Compra de cemento", descripcion=None, partidas=[]
    )
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(embedding=embedding)

    await scorer.score_many(crear_proveedor(keywords=["cemento"]), [licitacion], 1)

    assert embedding.calls[1] == ["Compra de cemento. "]  # sin descripción queda el punto y el espacio


@pytest.mark.asyncio
async def test_partidas_sin_nombre_tambien_caen_al_nombre_de_la_licitacion() -> None:
    """`build_item_texts` omite las partidas sin nombre; si no queda ninguna, no
    hay que dejar a la licitación sin ningún vector."""
    licitacion = crear_licitacion(
        uuid4(), nombre="Compra de cemento", descripcion=None, partidas=[("", None)]
    )
    embedding = FakeEmbeddingPorTexto()
    scorer, _ = crear_scorer(embedding=embedding)

    await scorer.score_many(crear_proveedor(keywords=["cemento"]), [licitacion], 1)

    assert embedding.calls[1] == ["Compra de cemento. "]  # sin descripción queda el punto y el espacio


# ---------------------------------------------------------------------------
# score_and_persist / score_pct_and_persist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_and_persist_guarda_la_fila_a_pedido() -> None:
    scorer, repo = crear_scorer()
    proveedor = crear_proveedor()
    licitacion = crear_licitacion(uuid4())

    resultado = await scorer.score_and_persist(proveedor, licitacion)

    assert resultado.source == "on_demand"
    # No pasó por Qdrant: "no se midió" no es lo mismo que un parecido de cero.
    assert resultado.similarity_score is None
    assert resultado.reranker_score is not None
    guardado = await repo.get_by_proveedor_and_licitacion(proveedor.id, licitacion.id)
    assert guardado is not None
    assert guardado.final_score == resultado.final_score


@pytest.mark.asyncio
async def test_score_and_persist_marca_la_fila_con_la_version_de_la_formula() -> None:
    """La versión identifica la fórmula: es lo que invalida los porcentajes viejos."""
    scorer, _ = crear_scorer()

    resultado = await scorer.score_and_persist(crear_proveedor(), crear_licitacion(uuid4()))

    assert resultado.model_version == MODEL_VERSION


@pytest.mark.asyncio
async def test_score_and_persist_reemplaza_el_calculo_anterior() -> None:
    scorer, repo = crear_scorer()
    proveedor = crear_proveedor()
    licitacion = crear_licitacion(uuid4())

    await scorer.score_and_persist(proveedor, licitacion)
    await scorer.score_and_persist(proveedor, licitacion)

    filas = await repo.get_by_supplier_id(proveedor.id)
    assert len(filas) == 1


@pytest.mark.asyncio
async def test_score_pct_and_persist_devuelve_el_porcentaje_de_la_formula() -> None:
    item_repo = InMemoryTenderItemVectorRepository()
    licitacion = crear_licitacion(uuid4())
    await item_repo.upsert(licitacion.id, [CEMENTO])
    scorer, _ = crear_scorer(
        reranker=RerankerPorDocumento(),
        embedding=FakeEmbeddingPorTexto({"cemento": CEMENTO}),
        item_repo=item_repo,
    )

    porcentaje = await scorer.score_pct_and_persist(
        crear_proveedor(keywords=["cemento"]), licitacion
    )

    assert porcentaje == pytest.approx(FORMULA.score(0.6, 1.0, 1.0) * 100.0)


@pytest.mark.asyncio
async def test_score_and_persist_falla_si_el_reranker_no_responde() -> None:
    scorer, repo = crear_scorer(reranker=RerankerVacio())
    proveedor = crear_proveedor()
    licitacion = crear_licitacion(uuid4())

    with pytest.raises(ScoreCalculationError):
        await scorer.score_and_persist(proveedor, licitacion)

    assert await repo.get_by_supplier_id(proveedor.id) == []
