from datetime import datetime
from uuid import uuid4

import pytest

from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.infrastructure.services.field_weighting_service import FieldWeightingService


@pytest.fixture
def supplier() -> Supplier:
    # Fixture para instanciar un proveedor con datos completos para la coincidencia de campos.
    # Se utiliza un RUT chileno válido ("76086428-5") que pasa la validación de módulo 11.
    return Supplier(
        id=uuid4(),
        rut="76086428-5",
        legal_name="Comercializadora Limitada",
        regions=["Metropolitana", "Valparaíso"],
        sectors=["Tecnología", "Electrónica"],
        keywords=["cables", "redes"],
        years_experience=5,
        num_employees=10,
    )


@pytest.fixture
def service() -> FieldWeightingService:
    # Fixture para instanciar el servicio con pesos personalizados.
    return FieldWeightingService(
        reranker_weight=0.5, region_weight=0.2, sector_weight=0.2, keyword_weight=0.1
    )


def test_calculate_scores_con_coincidencia_completa(
    service: FieldWeightingService, supplier: Supplier
) -> None:
    # Comprueba que un tender con coincidencia en región, sector y palabras clave
    # sume todos los pesos correspondientes al score final.
    now = datetime.now()
    t1 = Tender(
        id=uuid4(),
        code="T1",
        name="Licitación de Tecnología",
        description="Proyecto de redes de datos",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="11.111.111-1",
        buyer_unit="TI",
        region="Santiago, Metropolitana",  # Coincide con región Metropolitana
        available_amount_clp=5000000.0,
        items=[
            TenderItem(
                tender_id=uuid4(),
                product_code="999",
                name="Cables de fibra",  # Contiene keyword 'cables'
                quantity=10,
                unit_of_measure="metros",
            )
        ],
    )

    # Reranker score = 0.8.
    # Score esperado: (0.8 * 0.5) + 0.2 (region) + 0.2 (sector) + 0.1 (keyword) = 0.4 + 0.5 = 0.9
    results = service.calculate_scores([(t1, 0.8)], supplier)

    assert len(results) == 1
    assert results[0][0] == t1.id
    assert pytest.approx(results[0][1], rel=1e-3) == 0.9


def test_calculate_scores_sin_coincidencias(
    service: FieldWeightingService, supplier: Supplier
) -> None:
    # Comprueba que si no hay coincidencias de metadatos, el score final sea
    # únicamente el score del reranker ponderado.
    now = datetime.now()
    t1 = Tender(
        id=uuid4(),
        code="T2",
        name="Licitación de Construcción",  # No coincide con sectores
        description="Pintura de oficina",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="22.222.222-2",
        buyer_unit="Obras",
        region="Concepción",  # No coincide con regiones Metropolitana/Valparaíso
        available_amount_clp=100000.0,
        items=[
            TenderItem(
                tender_id=uuid4(),
                product_code="888",
                name="Rodillos para pintar",  # No coincide con keywords cables/redes
                quantity=2,
                unit_of_measure="unidades",
            )
        ],
    )

    # Reranker score = 0.6.
    # Score esperado: (0.6 * 0.5) + 0.0 = 0.3
    results = service.calculate_scores([(t1, 0.6)], supplier)

    assert len(results) == 1
    assert results[0][0] == t1.id
    assert pytest.approx(results[0][1], rel=1e-3) == 0.3


def test_calculate_scores_ordena_resultados_descendente(
    service: FieldWeightingService, supplier: Supplier
) -> None:
    # Comprueba que el listado de salida esté ordenado de mayor a menor score final.
    now = datetime.now()
    t_low = Tender(
        id=uuid4(),
        code="T_LOW",
        name="Construcción",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="2",
        buyer_unit="X",
        region="Biobío",
    )  # Score final esperado: 0.2 * 0.5 = 0.1

    t_high = Tender(
        id=uuid4(),
        code="T_HIGH",
        name="Licitación de Tecnología",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="1",
        buyer_unit="X",
        region="Santiago",
    )  # Score final esperado: (0.9 * 0.5) + 0.2 (region) + 0.2 (sector) = 0.45 + 0.4 = 0.85

    results = service.calculate_scores([(t_low, 0.2), (t_high, 0.9)], supplier)

    assert len(results) == 2
    assert results[0][0] == t_high.id  # El de mayor score primero
    assert results[1][0] == t_low.id
