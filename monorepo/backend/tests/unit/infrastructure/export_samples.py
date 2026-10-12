"""Snapshots de ejemplo para probar los renderers de PDF y Excel."""

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.application.use_cases.exports.export_snapshot import (
    ExportSnapshot,
    key_dates_for,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.quotation import StoredMaterialItem, Quotation
from app.domain.entities.tender import Tender, TenderItem

# 28-sep-2026 15:00 UTC = 12:00 en Chile (horario de verano, UTC-3).
GENERADO = datetime(2026, 9, 28, 15, 0, 0)


def snapshot(**cambios: object) -> ExportSnapshot:
    tender = Tender(
        code="1057539-228-COT26",
        name="Mantención de áreas verdes Ñuñoa",
        description="Corte de pasto y poda en plazas de la comuna.",
        status_id=1,
        status_code="publicada",
        published_at=datetime(2026, 9, 26, 15, 0),
        closing_at=datetime(2026, 10, 8, 18, 0),
        last_change_at=GENERADO,
        buyer_rut="61.980.170-9",
        buyer_name="Municipalidad de Ñuñoa",
        buyer_unit="Operaciones",
        region="Metropolitana",
        commune="Ñuñoa",
        available_amount_clp=5_000_000,
    )
    tender = tender.model_copy(
        update={
            "items": [
                TenderItem(
                    tender_id=tender.id,
                    product_code="70111703",
                    name="Corte de pasto",
                    description="Plazas y bandejones",
                    quantity=12,
                    unit_of_measure="Servicio",
                )
            ]
        }
    )
    # Incluye una cotización histórica con fracciones para verificar su lectura.
    quotation = Quotation(
        id=uuid4(),
        supplier_id=uuid4(),
        tender_id=tender.id,
        currency="CLP",
        items=[
            StoredMaterialItem(
                description="Semilla de pasto",
                unit="kg",
                quantity=Decimal("10"),
                unit_price=Decimal("1500"),
            ),
            StoredMaterialItem(
                description="Fertilizante",
                unit="saco",
                quantity=Decimal("2.5"),
                unit_price=Decimal("12990"),
            ),
        ],
        updated_at=GENERADO,
    )
    datos: dict[str, object] = {
        "tender": tender,
        "supplier_name": "Constructora Andes",
        "score_pct": 84,
        "analysis": DeepAnalysis(
            tender_id=tender.id,
            supplier_id=uuid4(),
            compatibility_score=84,
            recommendation="Postular",
            justification="El rubro coincide con la experiencia declarada en mantención.",
        ),
        "quotation": quotation,
        "key_dates": key_dates_for(tender),
        "generated_at": GENERADO,
    }
    datos.update(cambios)
    return ExportSnapshot(**datos)  # type: ignore[arg-type]


def con_licitacion(base: ExportSnapshot, **cambios: object) -> ExportSnapshot:
    return replace(base, tender=base.tender.model_copy(update=cambios))
