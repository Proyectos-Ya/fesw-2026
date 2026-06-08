from datetime import datetime, timezone
from unittest.mock import AsyncMock, call

import pytest

from app.application.repositories.licitacion_repository import ILicitacionRepository
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.mercado_publico_service import IMercadoPublicoService
from app.application.services.text_builder import TextBuilder
from app.application.services.vector_store_service import IVectorStoreService
from app.application.useCases.ingest_licitaciones import IngestLicitacionesUseCase
from app.domain.entities.licitacion import Licitacion
from app.domain.models.licitacion_schema import IngestRequest

FECHA_CIERRE = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _make_licitacion(codigo: str) -> Licitacion:
    return Licitacion(
        codigo_externo=codigo,
        nombre=f"Licitacion {codigo}",
        organismo_nombre="Organismo Test",
        fecha_cierre=FECHA_CIERRE,
        region="Metropolitana",
        estado="activa",
    )


def _make_vector() -> list[float]:
    return [0.1] * 1024


@pytest.fixture
def deps() -> dict:
    return {
        "mercado_publico": AsyncMock(spec=IMercadoPublicoService),
        "licitacion_repo": AsyncMock(spec=ILicitacionRepository),
        "embedding_service": AsyncMock(spec=IEmbeddingService),
        "vector_store": AsyncMock(spec=IVectorStoreService),
        "text_builder": TextBuilder(),
        "version_modelo": "bge-m3-v1",
    }


@pytest.fixture
def use_case(deps: dict) -> IngestLicitacionesUseCase:
    return IngestLicitacionesUseCase(**deps)


@pytest.fixture
def request_default() -> IngestRequest:
    return IngestRequest(estado="activas", limit=10, offset=0)


# ---------------------------------------------------------------------------
# Conteo de procesadas / duplicadas / errores
# ---------------------------------------------------------------------------


async def test_licitaciones_nuevas_se_procesan(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    licitaciones = [_make_licitacion(f"000{i}-1-LQ24") for i in range(3)]
    deps["mercado_publico"].fetch_licitaciones.return_value = licitaciones
    deps["licitacion_repo"].get_by_codigo_externo.return_value = None
    deps["embedding_service"].embed.return_value = [_make_vector() for _ in licitaciones]
    deps["licitacion_repo"].save.side_effect = lambda l: l

    resultado = await use_case.execute(request_default)

    assert resultado.procesadas == 3
    assert resultado.duplicadas == 0
    assert resultado.errores == 0


async def test_licitaciones_duplicadas_se_omiten(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    lic_nueva = _make_licitacion("0001-1-LQ24")
    lic_dup = _make_licitacion("0002-1-LQ24")
    deps["mercado_publico"].fetch_licitaciones.return_value = [lic_nueva, lic_dup]
    deps["licitacion_repo"].get_by_codigo_externo.side_effect = (
        lambda codigo: lic_dup if codigo == "0002-1-LQ24" else None
    )
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["licitacion_repo"].save.side_effect = lambda l: l

    resultado = await use_case.execute(request_default)

    assert resultado.procesadas == 1
    assert resultado.duplicadas == 1
    assert resultado.errores == 0


async def test_error_en_upsert_no_detiene_el_proceso(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    licitaciones = [_make_licitacion(f"000{i}-1-LQ24") for i in range(3)]
    deps["mercado_publico"].fetch_licitaciones.return_value = licitaciones
    deps["licitacion_repo"].get_by_codigo_externo.return_value = None
    deps["embedding_service"].embed.return_value = [_make_vector() for _ in licitaciones]

    call_count = 0

    async def upsert_con_fallo(*args, **kwargs) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Qdrant no disponible")

    deps["vector_store"].upsert.side_effect = upsert_con_fallo
    deps["licitacion_repo"].save.side_effect = lambda l: l

    resultado = await use_case.execute(request_default)

    assert resultado.procesadas == 2
    assert resultado.errores == 1


async def test_error_en_save_repo_no_detiene_el_proceso(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    licitaciones = [_make_licitacion(f"000{i}-1-LQ24") for i in range(3)]
    deps["mercado_publico"].fetch_licitaciones.return_value = licitaciones
    deps["licitacion_repo"].get_by_codigo_externo.return_value = None
    deps["embedding_service"].embed.return_value = [_make_vector() for _ in licitaciones]

    call_count = 0

    async def save_con_fallo(licitacion: Licitacion) -> Licitacion:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("DB no disponible")
        return licitacion

    deps["licitacion_repo"].save.side_effect = save_con_fallo

    resultado = await use_case.execute(request_default)

    assert resultado.procesadas == 2
    assert resultado.errores == 1


async def test_lista_vacia_retorna_ceros(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    deps["mercado_publico"].fetch_licitaciones.return_value = []

    resultado = await use_case.execute(request_default)

    assert resultado.procesadas == 0
    assert resultado.duplicadas == 0
    assert resultado.errores == 0
    deps["embedding_service"].embed.assert_not_called()


async def test_todas_duplicadas_no_llama_a_embed(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    licitaciones = [_make_licitacion(f"000{i}-1-LQ24") for i in range(2)]
    deps["mercado_publico"].fetch_licitaciones.return_value = licitaciones
    deps["licitacion_repo"].get_by_codigo_externo.side_effect = (
        lambda codigo: _make_licitacion(codigo)
    )

    resultado = await use_case.execute(request_default)

    assert resultado.procesadas == 0
    assert resultado.duplicadas == 2
    deps["embedding_service"].embed.assert_not_called()


async def test_fallo_batch_embedding_cuenta_todas_como_errores(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    licitaciones = [_make_licitacion(f"000{i}-1-LQ24") for i in range(3)]
    deps["mercado_publico"].fetch_licitaciones.return_value = licitaciones
    deps["licitacion_repo"].get_by_codigo_externo.return_value = None
    deps["embedding_service"].embed.side_effect = RuntimeError("modelo no cargado")

    resultado = await use_case.execute(request_default)

    assert resultado.procesadas == 0
    assert resultado.errores == 3
    deps["licitacion_repo"].save.assert_not_called()


# ---------------------------------------------------------------------------
# Comportamiento de dependencias
# ---------------------------------------------------------------------------


async def test_version_modelo_en_resultado(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    deps["mercado_publico"].fetch_licitaciones.return_value = []

    resultado = await use_case.execute(request_default)

    assert resultado.version_modelo == "bge-m3-v1"


async def test_ensure_collection_se_llama_una_vez(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    deps["mercado_publico"].fetch_licitaciones.return_value = []

    await use_case.execute(request_default)

    deps["vector_store"].ensure_collection.assert_called_once()


async def test_embed_se_llama_en_batch_unico(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    licitaciones = [_make_licitacion(f"000{i}-1-LQ24") for i in range(3)]
    deps["mercado_publico"].fetch_licitaciones.return_value = licitaciones
    deps["licitacion_repo"].get_by_codigo_externo.return_value = None
    deps["embedding_service"].embed.return_value = [_make_vector() for _ in licitaciones]
    deps["licitacion_repo"].save.side_effect = lambda l: l

    await use_case.execute(request_default)

    # embed debe haberse llamado exactamente UNA vez con los 3 textos (no 3 veces)
    deps["embedding_service"].embed.assert_called_once()
    textos_pasados = deps["embedding_service"].embed.call_args[0][0]
    assert len(textos_pasados) == 3


async def test_payload_qdrant_contiene_campos_requeridos(
    use_case: IngestLicitacionesUseCase,
    deps: dict,
    request_default: IngestRequest,
) -> None:
    lic = _make_licitacion("1234-5-LQ24")
    deps["mercado_publico"].fetch_licitaciones.return_value = [lic]
    deps["licitacion_repo"].get_by_codigo_externo.return_value = None
    deps["embedding_service"].embed.return_value = [_make_vector()]
    deps["licitacion_repo"].save.side_effect = lambda l: l

    await use_case.execute(request_default)

    _, kwargs = deps["vector_store"].upsert.call_args
    payload = kwargs.get("payload") or deps["vector_store"].upsert.call_args[0][2]

    assert "licitacion_id" in payload
    assert "estado" in payload
    assert "region" in payload
    assert "fecha_cierre" in payload
    assert "monto_estimado" in payload
