from datetime import datetime
from uuid import uuid4

import pytest

from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.infrastructure.services.field_weighting_service import FieldWeightingService


@pytest.fixture
def supplier() -> Supplier:
    """Fixture para un proveedor de tecnología con RUT válido."""
    return Supplier(
        id=uuid4(),
        rut="76086428-5",
        legal_name="Comercializadora Limitada",
        regions=["Región Metropolitana de Santiago", "Región de Valparaíso"],
        sectors=["Tecnología", "Desarrollo de Software"],
        keywords=["cables", "redes"],
        years_experience=5,
        num_employees=10,
    )


@pytest.fixture
def service() -> FieldWeightingService:
    """Fixture para el servicio con la ponderación híbrida por componentes y densidad (0.50 / 0.25 / 0.25)."""
    return FieldWeightingService(
        reranker_weight=0.50,
        sector_weight=0.25,
        keyword_weight=0.25,
    )


def test_calculate_scores_con_coincidencia_completa(
    service: FieldWeightingService, supplier: Supplier
) -> None:
    """Verifica que con múltiples coincidencias de sector y keywords (densidad completa) se sumen los pesos correctamente (0.50 + 0.25 + 0.25)."""
    now = datetime.now()
    t1 = Tender(
        id=uuid4(),
        code="T1",
        name="Licitación de Tecnología e Informática con cables y redes",
        description="Proyecto de desarrollo de software y redes de datos",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="11.111.111-1",
        buyer_unit="TI",
        region="Región Metropolitana de Santiago",
        available_amount_clp=5000000.0,
        items=[
            TenderItem(
                tender_id=uuid4(),
                product_code="999",
                name="Cables de fibra óptica",
                quantity=10,
                unit_of_measure="metros",
            )
        ],
    )

    # Reranker score = 0.80.
    # Score esperado: (0.80 * 0.50) + 0.25 (sector) + 0.25 (keyword completo por >=2 keywords) = 0.40 + 0.50 = 0.90
    results = service.calculate_scores([(t1, 0.80)], supplier)

    assert len(results) == 1
    assert results[0][0] == t1.id
    assert pytest.approx(results[0][1], rel=1e-3) == 0.90


def test_calculate_scores_sin_coincidencias(
    service: FieldWeightingService, supplier: Supplier
) -> None:
    """Verifica que sin coincidencias el score final sea exclusivamente el score del Reranker ponderado al 50%."""
    now = datetime.now()
    t1 = Tender(
        id=uuid4(),
        code="T2",
        name="Licitación de Construcción y Obras Civiles",
        description="Pintura de oficina",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="22.222.222-2",
        buyer_unit="Obras",
        region="Región del Biobío",
        available_amount_clp=100000.0,
        items=[
            TenderItem(
                tender_id=uuid4(),
                product_code="888",
                name="Rodillos para pintar",
                quantity=2,
                unit_of_measure="unidades",
            )
        ],
    )

    # Reranker score = 0.60.
    # Score esperado: (0.60 * 0.50) = 0.30
    results = service.calculate_scores([(t1, 0.60)], supplier)

    assert len(results) == 1
    assert results[0][0] == t1.id
    assert pytest.approx(results[0][1], rel=1e-3) == 0.30


def test_keywords_match_in_title_and_description(
    service: FieldWeightingService, supplier: Supplier
) -> None:
    """Verifica que las keywords se detecten en el título/descripción y apliquen el bono de densidad proporcional."""
    now = datetime.now()
    # Licitación sin items pero con 1 keyword ('redes') en el título
    t_no_items = Tender(
        id=uuid4(),
        code="T_TITLE_KW",
        name="Mantenimiento de Redes de Comunicaciones",
        description="Soporte integral",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="11.111.111-1",
        buyer_unit="TI",
        items=[],
    )

    # Reranker = 0.70. Coincide 1 keyword -> ratio 0.75 (0.25 * 0.75 = 0.1875)
    results = service.calculate_scores([(t_no_items, 0.70)], supplier)
    assert pytest.approx(results[0][1], rel=1e-3) == (0.70 * 0.50) + (0.25 * 0.75)


def test_sector_matching_avoids_substring_false_positives(
    service: FieldWeightingService,
) -> None:
    """Verifica que subcadenas parciales accidentales (ej. 'red' en 'alrededor', 'TI' en 'tierra')
    NO activen el bono de sector si no son palabras completas."""
    now = datetime.now()
    supplier_with_short_sectors = Supplier(
        id=uuid4(),
        rut="76086428-5",
        legal_name="Redes SpA",
        sectors=["Red", "TI"],
        keywords=["fibra"],
    )

    tender = Tender(
        id=uuid4(),
        code="T_FALSE",
        name="Movimiento de tierra y obras alrededor de la plaza",
        description="Reparación de pavimento",
        status_id=1,
        published_at=now,
        closing_at=now,
        last_change_at=now,
        buyer_rut="11.111.111-1",
        buyer_unit="Obras",
        items=[
            TenderItem(
                tender_id=uuid4(),
                product_code="111",
                name="Arena gruesa",
                quantity=5,
                unit_of_measure="m3",
            )
        ],
    )

    # Reranker score = 0.10. No debe recibir bono de sector ni keyword
    results = service.calculate_scores([(tender, 0.10)], supplier_with_short_sectors)
    assert pytest.approx(results[0][1], rel=1e-3) == 0.05  # 0.10 * 0.50 = 0.05
