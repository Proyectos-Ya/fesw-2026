"""Las entidades expuestas por la API deben emitir ISO-8601 con sufijo Z.

Sin el sufijo, `new Date(iso)` en el navegador interpreta el string como hora
local y muestra la hora corrida por el offset de la zona del usuario.
"""

from datetime import datetime
from uuid import uuid4

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.question import Question
from app.domain.entities.tender import Tender


class TestDeepAnalysisSerialization:
    def _analysis(self) -> DeepAnalysis:
        return DeepAnalysis(
            tender_id=uuid4(),
            supplier_id=uuid4(),
            compatibility_score=87.5,
            recommendation="Postular",
            justification="Coincide con el rubro del proveedor.",
            created_at=datetime(2026, 7, 27, 21, 42, 0),
            updated_at=datetime(2026, 7, 27, 21, 42, 0),
        )

    def test_updated_at_is_serialized_as_utc_with_z(self):
        dumped = self._analysis().model_dump(mode="json")

        assert dumped["updated_at"] == "2026-07-27T21:42:00Z"
        assert dumped["created_at"] == "2026-07-27T21:42:00Z"

    def test_python_mode_dump_keeps_datetime_objects(self):
        # Los repositorios escriben en la base con el valor naive original.
        dumped = self._analysis().model_dump()

        assert dumped["updated_at"] == datetime(2026, 7, 27, 21, 42, 0)


class TestTenderSerialization:
    def test_all_tender_dates_are_serialized_as_utc_with_z(self):
        tender = Tender(
            code="1234-56-COT26",
            name="Compra ágil de prueba",
            status_id=5,
            status_code="publicada",
            published_at=datetime(2026, 7, 27, 21, 42, 0),
            closing_at=datetime(2026, 7, 30, 19, 0, 0),
            last_change_at=datetime(2026, 7, 27, 21, 42, 0),
            buyer_rut="60.000.000-0",
            buyer_unit="Unidad de Prueba",
        )

        dumped = tender.model_dump(mode="json")

        assert dumped["published_at"] == "2026-07-27T21:42:00Z"
        assert dumped["closing_at"] == "2026-07-30T19:00:00Z"
        assert dumped["last_change_at"] == "2026-07-27T21:42:00Z"
        assert dumped["created_at"].endswith("Z")
        assert dumped["updated_at"].endswith("Z")


class TestQuestionSerialization:
    def test_generated_at_is_serialized_as_utc_with_z(self):
        question = Question(
            provider_id=uuid4(),
            question="¿Cuál es el plazo de entrega?",
            target_profile_field="delivery_time",
            generated_at=datetime(2026, 7, 27, 21, 42, 0),
            answered_at=datetime(2026, 7, 27, 22, 0, 0),
        )

        dumped = question.model_dump(mode="json")

        assert dumped["generated_at"] == "2026-07-27T21:42:00Z"
        assert dumped["answered_at"] == "2026-07-27T22:00:00Z"

    def test_null_answered_at_stays_null(self):
        question = Question(
            provider_id=uuid4(),
            question="¿Cuál es el plazo de entrega?",
            target_profile_field="delivery_time",
        )

        assert question.model_dump(mode="json")["answered_at"] is None
