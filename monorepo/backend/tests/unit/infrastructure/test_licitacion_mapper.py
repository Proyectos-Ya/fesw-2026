from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from app.domain.entities.licitacion import ItemLicitacion, Licitacion
from app.infrastructure.repositories.licitacion_repository import LicitacionRepository

FECHA_CIERRE = datetime(2026, 8, 1, tzinfo=UTC)


def _make_repo() -> LicitacionRepository:
    return LicitacionRepository(session=MagicMock())


def _make_licitacion(**kwargs) -> Licitacion:
    defaults = dict(
        codigo_externo="1234-5-LQ24",
        nombre="Servicio de Limpieza",
        organismo_nombre="Municipalidad de Santiago",
        fecha_cierre=FECHA_CIERRE,
        region="Metropolitana",
        estado="activa",
    )
    defaults.update(kwargs)
    return Licitacion(**defaults)


# ---------------------------------------------------------------------------
# _to_model
# ---------------------------------------------------------------------------


def test_to_model_mapea_campos_basicos() -> None:
    lic = _make_licitacion()
    repo = _make_repo()

    model = repo._to_model(lic)

    assert model.id == lic.id
    assert model.codigo_externo == "1234-5-LQ24"
    assert model.nombre == "Servicio de Limpieza"
    assert model.organismo_nombre == "Municipalidad de Santiago"
    assert model.region == "Metropolitana"
    assert model.estado == "activa"


def test_to_model_serializa_items_como_dicts() -> None:
    lic = _make_licitacion(
        items=[
            ItemLicitacion(nombre="Escobas", descripcion="Escobas industriales"),
            ItemLicitacion(nombre="Detergente"),
        ]
    )
    repo = _make_repo()

    model = repo._to_model(lic)

    assert model.items == [
        {"nombre": "Escobas", "descripcion": "Escobas industriales"},
        {"nombre": "Detergente", "descripcion": None},
    ]


def test_to_model_serializa_categorias_como_lista() -> None:
    lic = _make_licitacion(categorias=["Aseo", "Mantención"])
    repo = _make_repo()

    model = repo._to_model(lic)

    assert model.categorias == ["Aseo", "Mantención"]


def test_to_model_items_vacios_producen_lista_vacia() -> None:
    lic = _make_licitacion(items=[])
    repo = _make_repo()

    model = repo._to_model(lic)

    assert model.items == []


# ---------------------------------------------------------------------------
# _to_entity
# ---------------------------------------------------------------------------


def test_to_entity_reconstruye_items_como_item_licitacion() -> None:
    lic = _make_licitacion(
        items=[ItemLicitacion(nombre="Escobas", descripcion="Industriales")]
    )
    repo = _make_repo()

    model = repo._to_model(lic)
    entity = repo._to_entity(model)

    assert len(entity.items) == 1
    assert isinstance(entity.items[0], ItemLicitacion)
    assert entity.items[0].nombre == "Escobas"
    assert entity.items[0].descripcion == "Industriales"


def test_to_entity_items_vacios_permanecen_vacios() -> None:
    lic = _make_licitacion()
    repo = _make_repo()

    model = repo._to_model(lic)
    entity = repo._to_entity(model)

    assert entity.items == []


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


def test_roundtrip_licitacion_minima() -> None:
    lic = _make_licitacion()
    repo = _make_repo()

    assert repo._to_entity(repo._to_model(lic)) == lic


def test_roundtrip_licitacion_completa() -> None:
    lic = _make_licitacion(
        descripcion="Contrato de aseo para edificios municipales",
        monto_estimado=5_000_000.0,
        categorias=["Aseo", "Mantención"],
        items=[
            ItemLicitacion(nombre="Escobas", descripcion="Industriales"),
            ItemLicitacion(nombre="Detergente"),
        ],
        qdrant_vector_id=uuid4(),
        version_modelo="bge-m3-v1",
    )
    repo = _make_repo()

    assert repo._to_entity(repo._to_model(lic)) == lic
