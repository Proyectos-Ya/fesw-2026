from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.tender_repository import TenderFilters
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    ComunaModel,
    ProvinciaModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.shared.regions import CHILE_REGIONS

# `db_session` y el esquema limpio los aporta tests/integration/conftest.py,
# que apunta a la base de test y no a la de desarrollo.


def utc_now_naive() -> datetime:
    """Returns a timezone-naive UTC datetime to avoid Python 3.12 deprecations and DB offset issues."""
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_get_tenders_empty(db_session: AsyncSession):
    repo = TenderRepository(db_session)
    filters = TenderFilters()
    tenders = await repo.get_tenders(filters)
    assert tenders == []


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession):
    repo = TenderRepository(db_session)

    # 1. Seed region
    region = RegionModel(id=13, name=CHILE_REGIONS[13])
    db_session.add(region)

    # 2. Seed status
    status = TenderStatusModel(id=1, code="publicada", name="Publicada")
    db_session.add(status)

    # 3. Seed buyer institution
    buyer = BuyerInstitutionModel(
        rut="12.345.678-9",
        name="Municipalidad de Santiago",
        region_id=13,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(buyer)
    await db_session.commit()

    # 4. Create and save tender model directly
    tender_id = uuid4()
    tender_model = TenderModel(
        id=tender_id,
        code="1057539-228-COT26",
        name="Materiales Eléctricos",
        description="Compra de cables y enchufes",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="12.345.678-9",
        buyer_unit="Operaciones",
        available_amount_clp=500000.0,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(tender_model)
    await db_session.commit()

    # 5. Retrieve using filter by id
    filters = TenderFilters(ids=[tender_id])
    results = await repo.get_tenders(filters)
    assert len(results) == 1
    assert results[0].id == tender_id
    assert results[0].name == "Materiales Eléctricos"
    assert results[0].region == CHILE_REGIONS[13]


@pytest.mark.asyncio
async def test_get_tenders_filter_by_region(db_session: AsyncSession):
    repo = TenderRepository(db_session)

    # Seed regions
    r1 = RegionModel(id=13, name=CHILE_REGIONS[13])
    r2 = RegionModel(id=5, name=CHILE_REGIONS[5])
    db_session.add(r1)
    db_session.add(r2)

    # Seed status
    status = TenderStatusModel(id=1, code="publicada", name="Publicada")
    db_session.add(status)

    # Seed buyers
    b1 = BuyerInstitutionModel(
        rut="11.111.111-1",
        name="Municipalidad de Santiago",
        region_id=13,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    b2 = BuyerInstitutionModel(
        rut="22.222.222-2",
        name="Municipalidad de Valparaíso",
        region_id=5,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(b1)
    db_session.add(b2)
    await db_session.commit()

    # Create tenders directly
    t1 = TenderModel(
        id=uuid4(),
        code="COT-METRO",
        name="Tender Metro",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="11.111.111-1",
        buyer_unit="IT",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    t2 = TenderModel(
        id=uuid4(),
        code="COT-VALPO",
        name="Tender Valpo",
        status_id=1,
        published_at=utc_now_naive(),
        closing_at=utc_now_naive(),
        last_change_at=utc_now_naive(),
        buyer_rut="22.222.222-2",
        buyer_unit="IT",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(t1)
    db_session.add(t2)
    await db_session.commit()

    # Filter by region
    filters = TenderFilters(regions=[CHILE_REGIONS[13]])
    results = await repo.get_tenders(filters)
    assert len(results) == 1
    assert results[0].code == "COT-METRO"
    assert results[0].region == CHILE_REGIONS[13]


# ---------------------------------------------------------------------------
# search_tenders: respaldo del buscador cuando no hay vector que ordene
# ---------------------------------------------------------------------------


async def _seed_para_busqueda(session: AsyncSession) -> None:
    """Dos regiones, y licitaciones que varían en cierre, monto y estado."""
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(RegionModel(id=5, name=CHILE_REGIONS[5]))
    session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
    session.add(TenderStatusModel(id=7, code="cerrada", name="Cerrada"))
    for rut, nombre, region_id in (
        ("11.111.111-1", "Municipalidad RM", 13),
        ("22.222.222-2", "Municipalidad Valpo", 5),
    ):
        session.add(
            BuyerInstitutionModel(
                rut=rut,
                name=nombre,
                region_id=region_id,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
    await session.commit()

    base = datetime(2026, 9, 1, 12, 0, 0)
    filas = [
        # code,      buyer,          status, cierre,          monto
        ("RM-PRONTO", "11.111.111-1", 1, base + timedelta(days=1), 200_000.0),
        ("RM-MEDIO", "11.111.111-1", 1, base + timedelta(days=5), 1_000_000.0),
        ("RM-TARDE", "11.111.111-1", 1, base + timedelta(days=10), 5_000_000.0),
        ("RM-SIN-MONTO", "11.111.111-1", 1, base + timedelta(days=3), None),
        ("RM-CERRADA", "11.111.111-1", 7, base + timedelta(days=2), 300_000.0),
        ("VALPO-1", "22.222.222-2", 1, base + timedelta(days=4), 800_000.0),
    ]
    for code, buyer, status_id, cierre, monto in filas:
        session.add(
            TenderModel(
                id=uuid4(),
                code=code,
                name=f"Licitación {code}",
                status_id=status_id,
                published_at=base - timedelta(days=30),
                closing_at=cierre,
                last_change_at=base,
                buyer_rut=buyer,
                buyer_unit="Obras",
                available_amount_clp=monto,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
    await session.commit()


@pytest.mark.asyncio
async def test_search_sin_criterios_devuelve_todo(db_session: AsyncSession):
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(TenderFilterCriteria(), limit=100)

    assert total == 6
    assert len(items) == 6


@pytest.mark.asyncio
async def test_search_ordena_por_fecha_de_cierre_ascendente(db_session: AsyncSession):
    """Sin relevancia que calcular, lo más útil es lo que vence primero."""
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, _ = await repo.search_tenders(TenderFilterCriteria(), limit=100)

    assert [t.code for t in items][:3] == ["RM-PRONTO", "RM-CERRADA", "RM-SIN-MONTO"]


@pytest.mark.asyncio
async def test_search_filtra_por_estado(db_session: AsyncSession):
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(status_codes=["publicada"]), limit=100
    )

    assert total == 5
    assert "RM-CERRADA" not in [t.code for t in items]


@pytest.mark.asyncio
async def test_search_filtra_por_region(db_session: AsyncSession):
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(region_ids=[5]), limit=100
    )

    assert total == 1
    assert [t.code for t in items] == ["VALPO-1"]


@pytest.mark.asyncio
async def test_search_filtra_por_rango_de_cierre(db_session: AsyncSession):
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)
    base = datetime(2026, 9, 1, 12, 0, 0)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(
            closing_from=base + timedelta(days=3),
            closing_to=base + timedelta(days=5),
        ),
        limit=100,
    )

    assert total == 3
    assert set(t.code for t in items) == {"RM-SIN-MONTO", "VALPO-1", "RM-MEDIO"}


@pytest.mark.asyncio
async def test_search_excluye_las_licitaciones_sin_monto(db_session: AsyncSession):
    """Misma semántica que `tenderMatchesBudget` del frontend y que Qdrant.

    En SQL sale gratis porque una comparación contra NULL no es verdadera, pero
    conviene fijarlo: es una decisión de producto, no un detalle del motor.
    """
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(min_amount=1.0), limit=100
    )

    assert "RM-SIN-MONTO" not in [t.code for t in items]
    assert total == 5


@pytest.mark.asyncio
async def test_search_rango_de_monto_es_inclusivo(db_session: AsyncSession):
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, _ = await repo.search_tenders(
        TenderFilterCriteria(min_amount=200_000.0, max_amount=800_000.0), limit=100
    )

    # 200.000 y 800.000 son exactamente los extremos y deben entrar.
    assert set(t.code for t in items) == {"RM-PRONTO", "RM-CERRADA", "VALPO-1"}


@pytest.mark.asyncio
async def test_search_combina_criterios(db_session: AsyncSession):
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(status_codes=["publicada"], region_ids=[13]),
        limit=100,
    )

    assert total == 4
    assert "VALPO-1" not in [t.code for t in items]
    assert "RM-CERRADA" not in [t.code for t in items]


@pytest.mark.asyncio
async def test_el_total_no_depende_del_limite(db_session: AsyncSession):
    """El total son las coincidencias, no lo que cupo en la respuesta."""
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(TenderFilterCriteria(), limit=2)

    assert len(items) == 2
    assert total == 6


@pytest.mark.asyncio
async def test_el_offset_devuelve_el_bloque_siguiente(db_session: AsyncSession):
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    primeros, _ = await repo.search_tenders(TenderFilterCriteria(), limit=2, offset=0)
    siguientes, total = await repo.search_tenders(
        TenderFilterCriteria(), limit=2, offset=2
    )

    assert total == 6
    assert not set(t.code for t in primeros) & set(t.code for t in siguientes)


@pytest.mark.asyncio
async def test_search_hidrata_la_region(db_session: AsyncSession):
    """La entidad debe traer el nombre de región, no solo el id de la institución."""
    await _seed_para_busqueda(db_session)
    repo = TenderRepository(db_session)

    items, _ = await repo.search_tenders(
        TenderFilterCriteria(region_ids=[5]), limit=100
    )

    assert items[0].region == CHILE_REGIONS[5]


# ---------------------------------------------------------------------------
# search_tenders: filtro por provincia/comuna
# ---------------------------------------------------------------------------

PROVINCIA_CORDILLERA_ID = 1
PROVINCIA_SANTIAGO_ID = 2
COMUNA_PUENTE_ALTO_SEARCH_ID = 1
COMUNA_SANTIAGO_SEARCH_ID = 2


async def _seed_para_busqueda_geografica(session: AsyncSession) -> None:
    """Dos provincias dentro de la misma región, más un buyer sin comuna.

    - Puente Alto (comuna) / Cordillera (provincia) / RM (región 13)
    - Santiago (comuna) / Santiago (provincia) / RM (región 13)
    - Valparaíso: buyer sin comuna resuelta, región 5
    """
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(RegionModel(id=5, name=CHILE_REGIONS[5]))
    session.add(
        ProvinciaModel(id=PROVINCIA_CORDILLERA_ID, name="Cordillera", region_id=13)
    )
    session.add(ProvinciaModel(id=PROVINCIA_SANTIAGO_ID, name="Santiago", region_id=13))
    session.add(
        ComunaModel(
            id=COMUNA_PUENTE_ALTO_SEARCH_ID,
            name="Puente Alto",
            provincia_id=PROVINCIA_CORDILLERA_ID,
        )
    )
    session.add(
        ComunaModel(
            id=COMUNA_SANTIAGO_SEARCH_ID,
            name="Santiago",
            provincia_id=PROVINCIA_SANTIAGO_ID,
        )
    )
    session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
    for rut, nombre, region_id, comuna_id in (
        (
            "11.111.111-1",
            "I Municipalidad de Puente Alto",
            13,
            COMUNA_PUENTE_ALTO_SEARCH_ID,
        ),
        ("22.222.222-2", "I Municipalidad de Santiago", 13, COMUNA_SANTIAGO_SEARCH_ID),
        ("33.333.333-3", "Servicio Electoral Valparaíso", 5, None),
    ):
        session.add(
            BuyerInstitutionModel(
                rut=rut,
                name=nombre,
                region_id=region_id,
                comuna_id=comuna_id,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
    await session.commit()

    base = datetime(2026, 9, 1, 12, 0, 0)
    for code, buyer in (
        ("PUENTE-ALTO", "11.111.111-1"),
        ("SANTIAGO", "22.222.222-2"),
        ("VALPO-SIN-COMUNA", "33.333.333-3"),
    ):
        session.add(
            TenderModel(
                id=uuid4(),
                code=code,
                name=f"Licitación {code}",
                status_id=1,
                published_at=base - timedelta(days=30),
                closing_at=base + timedelta(days=5),
                last_change_at=base,
                buyer_rut=buyer,
                buyer_unit="Obras",
                available_amount_clp=500_000.0,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
    await session.commit()


@pytest.mark.asyncio
async def test_search_filtra_por_comuna(db_session: AsyncSession):
    await _seed_para_busqueda_geografica(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(commune_id=COMUNA_PUENTE_ALTO_SEARCH_ID), limit=100
    )

    assert total == 1
    assert [t.code for t in items] == ["PUENTE-ALTO"]


@pytest.mark.asyncio
async def test_search_filtra_por_provincia(db_session: AsyncSession):
    """Dos comunas distintas dentro de la misma provincia deben calzar ambas."""
    await _seed_para_busqueda_geografica(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(province_id=PROVINCIA_SANTIAGO_ID), limit=100
    )

    assert total == 1
    assert [t.code for t in items] == ["SANTIAGO"]


@pytest.mark.asyncio
async def test_search_provincia_no_confunde_comunas_de_otra_provincia(
    db_session: AsyncSession,
):
    """Cordillera y Santiago comparten región; filtrar por una no debe traer la otra."""
    await _seed_para_busqueda_geografica(db_session)
    repo = TenderRepository(db_session)

    items, _ = await repo.search_tenders(
        TenderFilterCriteria(province_id=PROVINCIA_CORDILLERA_ID), limit=100
    )

    assert [t.code for t in items] == ["PUENTE-ALTO"]


@pytest.mark.asyncio
async def test_search_combina_provincia_con_region(db_session: AsyncSession):
    await _seed_para_busqueda_geografica(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(region_ids=[13], province_id=PROVINCIA_SANTIAGO_ID),
        limit=100,
    )

    assert total == 1
    assert [t.code for t in items] == ["SANTIAGO"]


@pytest.mark.asyncio
async def test_search_comuna_sin_coincidencias(db_session: AsyncSession):
    """El buyer sin comuna resuelta no debe calzar con ningún filtro de comuna/provincia."""
    await _seed_para_busqueda_geografica(db_session)
    repo = TenderRepository(db_session)

    items, total = await repo.search_tenders(
        TenderFilterCriteria(commune_id=999), limit=100
    )

    assert total == 0
    assert items == []


# ---------------------------------------------------------------------------
# comuna/provincia del organismo comprador
# ---------------------------------------------------------------------------


COMUNA_PUENTE_ALTO_ID = 1


async def _seed_comuna(session: AsyncSession) -> int:
    """Región 13 -> provincia Cordillera -> comuna Puente Alto, ya sembradas.

    Devuelve el id de la comuna (ids fijados a mano, no leídos de vuelta del
    ORM tras el commit: un `AsyncSession` expira los atributos al confirmar, y
    releerlos dispara una recarga perezosa que no funciona en este contexto).
    """
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(ProvinciaModel(id=1, name="Cordillera", region_id=13))
    session.add(
        ComunaModel(id=COMUNA_PUENTE_ALTO_ID, name="Puente Alto", provincia_id=1)
    )
    await session.commit()
    return COMUNA_PUENTE_ALTO_ID


@pytest.mark.asyncio
async def test_get_or_create_buyer_crea_con_comuna(db_session: AsyncSession):
    comuna_id = await _seed_comuna(db_session)
    repo = TenderRepository(db_session)

    await repo.get_or_create_buyer(
        rut="12.345.678-9",
        name="I Municipalidad de Puente Alto",
        region_id=13,
        comuna_id=comuna_id,
        comuna_resolution_source="organismo_name",
    )

    buyer = await db_session.get(BuyerInstitutionModel, "12.345.678-9")
    assert buyer is not None
    assert buyer.comuna_id == comuna_id
    assert buyer.comuna_resolution_source == "organismo_name"


@pytest.mark.asyncio
async def test_get_or_create_buyer_no_actualiza_uno_ya_existente(
    db_session: AsyncSession,
):
    """Get-or-create puro: un buyer ya creado nunca gana comuna en una llamada posterior."""
    comuna_id = await _seed_comuna(db_session)
    repo = TenderRepository(db_session)

    await repo.get_or_create_buyer(
        rut="12.345.678-9", name="Organismo Original", region_id=13
    )
    await repo.get_or_create_buyer(
        rut="12.345.678-9",
        name="Nombre Distinto",
        region_id=13,
        comuna_id=comuna_id,
        comuna_resolution_source="organismo_name",
    )

    buyer = await db_session.get(BuyerInstitutionModel, "12.345.678-9")
    assert buyer is not None
    assert buyer.name == "Organismo Original"
    assert buyer.comuna_id is None
    assert buyer.comuna_resolution_source is None


@pytest.mark.asyncio
async def test_get_comuna_id_by_name(db_session: AsyncSession):
    comuna_id = await _seed_comuna(db_session)
    repo = TenderRepository(db_session)

    assert await repo.get_comuna_id_by_name("Puente Alto") == comuna_id
    assert await repo.get_comuna_id_by_name("Comuna Inexistente") is None


@pytest.mark.asyncio
async def test_get_tenders_hidrata_province_y_commune(db_session: AsyncSession):
    comuna_id = await _seed_comuna(db_session)
    repo = TenderRepository(db_session)

    session = db_session
    session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="I Municipalidad de Puente Alto",
            region_id=13,
            comuna_id=comuna_id,
            comuna_resolution_source="organismo_name",
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    await session.commit()

    tender_id = uuid4()
    session.add(
        TenderModel(
            id=tender_id,
            code="COT-PUENTE-ALTO",
            name="Tender Puente Alto",
            status_id=1,
            published_at=utc_now_naive(),
            closing_at=utc_now_naive(),
            last_change_at=utc_now_naive(),
            buyer_rut="12.345.678-9",
            buyer_unit="Obras",
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    await session.commit()

    results = await repo.get_tenders(TenderFilters(ids=[tender_id]))

    assert len(results) == 1
    assert results[0].commune == "Puente Alto"
    assert results[0].province == "Cordillera"
    assert results[0].region == CHILE_REGIONS[13]


@pytest.mark.asyncio
async def test_search_hidrata_province_y_commune(db_session: AsyncSession):
    comuna_id = await _seed_comuna(db_session)
    repo = TenderRepository(db_session)

    session = db_session
    session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="I Municipalidad de Puente Alto",
            region_id=13,
            comuna_id=comuna_id,
            comuna_resolution_source="organismo_name",
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    await session.commit()

    session.add(
        TenderModel(
            id=uuid4(),
            code="COT-PUENTE-ALTO",
            name="Tender Puente Alto",
            status_id=1,
            published_at=utc_now_naive(),
            closing_at=utc_now_naive(),
            last_change_at=utc_now_naive(),
            buyer_rut="12.345.678-9",
            buyer_unit="Obras",
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    await session.commit()

    items, _ = await repo.search_tenders(TenderFilterCriteria(), limit=100)

    assert items[0].commune == "Puente Alto"
    assert items[0].province == "Cordillera"


@pytest.mark.asyncio
async def test_get_tenders_buyer_sin_comuna_no_falla(db_session: AsyncSession):
    """Sin comuna resuelta, province/commune quedan en None, sin regresión."""
    repo = TenderRepository(db_session)
    session = db_session

    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=1, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="12.345.678-9",
            name="Servicio Electoral",
            region_id=13,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    await session.commit()

    tender_id = uuid4()
    session.add(
        TenderModel(
            id=tender_id,
            code="COT-SIN-COMUNA",
            name="Tender sin comuna",
            status_id=1,
            published_at=utc_now_naive(),
            closing_at=utc_now_naive(),
            last_change_at=utc_now_naive(),
            buyer_rut="12.345.678-9",
            buyer_unit="Obras",
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
    )
    await session.commit()

    results = await repo.get_tenders(TenderFilters(ids=[tender_id]))

    assert len(results) == 1
    assert results[0].commune is None
    assert results[0].province is None
    assert results[0].region == CHILE_REGIONS[13]
