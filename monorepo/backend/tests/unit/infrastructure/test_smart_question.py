"""
Pruebas unitarias para la PR #61
Cubre issues: #38, #39, #40, #41

Ubicar en: tests/test_smart_question.py
Ejecutar con: pytest -v
"""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)
from app.domain.entities.question import Question
from app.infrastructure.services.smart_question_service import SmartQuestionServiceImpl

# ─────────────────────────────────────────────
# Fixtures comunes
# ─────────────────────────────────────────────

PROVIDER_ID = uuid4()


def make_question(**kwargs) -> Question:
    # Sin la anotación, el valor del dict se infiere como la unión de los tipos
    # presentes y ningún campo de Question termina siendo asignable.
    defaults: dict[str, Any] = dict(
        provider_id=PROVIDER_ID,
        question="¿Pregunta de prueba?",
        target_profile_field="campo_prueba",
        target_category="general",
        options=["Sí", "No"],
    )
    defaults.update(kwargs)
    return Question(**defaults)


def make_supplier(sectors: list):
    supplier = MagicMock()
    supplier.sectors = sectors
    return supplier


# ─────────────────────────────────────────────
# Issue #41 — Entidad Question (domain)
# ─────────────────────────────────────────────


class TestQuestionEntity:
    """Tests para app/domain/entities/question.py"""

    def test_create_question_minimal(self):
        """Crea una Question con campos obligatorios mínimos."""
        q = Question(
            provider_id=PROVIDER_ID,
            question="¿Tiene registro MOP?",
            target_profile_field="mop_registration",
        )
        assert q.provider_id == PROVIDER_ID
        assert q.question == "¿Tiene registro MOP?"
        assert q.target_profile_field == "mop_registration"

    def test_default_values(self):
        """Verifica valores por defecto al crear la entidad."""
        q = make_question()
        assert q.answered is False
        assert q.omitted is False
        assert q.answer is None
        assert q.answered_at is None
        assert q.target_category == "general"
        assert q.options == ["Sí", "No"]
        assert q.discrepancy_type == "Category"

    def test_id_is_auto_generated(self):
        """Cada instancia genera un UUID distinto."""
        q1 = make_question()
        q2 = make_question()
        assert q1.id != q2.id

    def test_generated_at_is_naive_datetime(self):
        """generated_at debe ser naive (sin tzinfo) para compatibilidad con Postgres."""
        q = make_question()
        assert q.generated_at.tzinfo is None

    def test_options_default_is_empty_list(self):
        """Sin pasar options, debe ser lista vacía."""
        q = Question(
            provider_id=PROVIDER_ID,
            question="?",
            target_profile_field="field",
        )
        assert q.options == []

    def test_custom_options(self):
        """Las opciones pasadas se almacenan correctamente."""
        opts = ["Opción A", "Opción B", "Opción C"]
        q = make_question(options=opts)
        assert q.options == opts

    def test_provider_id_type(self):
        """provider_id debe ser UUID."""
        q = make_question()
        assert isinstance(q.provider_id, UUID)


# ─────────────────────────────────────────────
# Issue #40 — SmartQuestionServiceImpl
# ─────────────────────────────────────────────


class TestSmartQuestionServiceImpl:
    """Tests para app/infrastructure/services/smart_question_service.py"""

    def _make_service(self, existing_questions=None, saved_questions=None):
        repo = AsyncMock()
        repo.get_active_by_provider.return_value = existing_questions or []
        repo.save_all.side_effect = lambda qs: qs  # devuelve lo mismo que recibe
        return SmartQuestionServiceImpl(question_repository=repo), repo

    # — Preguntas existentes —

    async def test_returns_existing_questions_without_saving(self):
        """Si ya hay preguntas en BD, las retorna sin generar nuevas."""
        existing = [make_question(), make_question()]
        service, repo = self._make_service(existing_questions=existing)

        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")

        assert result == existing
        repo.save_all.assert_not_called()

    # — Categoría construccion —

    async def test_generates_10_questions_for_construccion(self):
        """Debe generar exactamente 10 preguntas para 'construccion'."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        assert len(result) == 10

    async def test_generates_10_questions_for_obras_civiles(self):
        """Debe generar exactamente 10 preguntas para 'obras_civiles'."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "obras_civiles")
        assert len(result) == 10

    async def test_category_string_is_normalized(self):
        """Categoría con mayúsculas/espacios debe normalizarse antes de matchear."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(
            PROVIDER_ID, "  CONSTRUCCION  "
        )
        assert len(result) == 10

    async def test_construction_questions_have_correct_category(self):
        """Todas las preguntas generadas deben tener target_category='construccion'."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        for q in result:
            assert q.target_category == "construccion"

    async def test_construction_questions_belong_to_provider(self):
        """Todas las preguntas deben tener el provider_id correcto."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        for q in result:
            assert q.provider_id == PROVIDER_ID

    async def test_construction_questions_have_options(self):
        """Todas las preguntas de construcción deben tener al menos 2 opciones."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        for q in result:
            assert len(q.options) >= 2

    async def test_mop_question_is_present(self):
        """El pool de construcción debe incluir la pregunta sobre registro MOP."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        questions_text = [q.question for q in result]
        assert any("MOP" in q for q in questions_text)

    async def test_bim_question_is_present(self):
        """El pool de construcción debe incluir la pregunta sobre metodología BIM."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        questions_text = [q.question for q in result]
        assert any("BIM" in q for q in questions_text)

    # — Categoría TI —

    async def test_generates_questions_for_ti(self):
        """Debe generar al menos 1 pregunta para categoría 'ti'."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "ti")
        assert len(result) >= 1

    # — Categoría general / desconocida —

    async def test_generates_questions_for_unknown_category(self):
        """Para categoría desconocida, debe generar al menos 1 pregunta."""
        service, _ = self._make_service()
        result = await service.get_or_generate_questions(PROVIDER_ID, "gastronomia")
        assert len(result) >= 1

    # — Persistencia —

    async def test_calls_save_all_when_generating(self):
        """Al generar preguntas nuevas debe llamar a save_all del repositorio."""
        service, repo = self._make_service()
        await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        repo.save_all.assert_called_once()

    async def test_returns_saved_questions(self):
        """El resultado final debe ser lo que devuelve save_all."""
        saved = [make_question(question="Guardada")]
        service, repo = self._make_service()
        repo.save_all.side_effect = lambda _: saved

        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")
        assert result == saved


# ─────────────────────────────────────────────
# Issue #39 — SmartQuestionUseCase
# ─────────────────────────────────────────────


class TestSmartQuestionUseCase:
    """Tests para app/application/useCases/smart_question_use_case.py"""

    def _make_use_case(self, supplier_sectors=None, questions=None):
        smart_service = AsyncMock()
        smart_service.get_or_generate_questions.return_value = questions or [
            make_question()
        ]

        supplier_repo = AsyncMock()
        if supplier_sectors is None:
            supplier_repo.get_by_id.return_value = None
        else:
            supplier_repo.get_by_id.return_value = make_supplier(supplier_sectors)

        uc = SmartQuestionUseCase(
            smart_question_service=smart_service,
            supplier_repository=supplier_repo,
        )
        return uc, smart_service, supplier_repo

    # — Resolución de categoría —

    async def test_uses_construction_category_for_construction_sector(self):
        """Si el supplier tiene sector 'construction', llama al servicio con 'construction'."""
        uc, service, _ = self._make_use_case(supplier_sectors=["construction"])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="construction"
        )

    async def test_uses_construction_category_for_construccion_with_accent(self):
        """Sector 'construcción' (con tilde) también debe mapear a categoría 'construction'."""
        uc, service, _ = self._make_use_case(supplier_sectors=["construcción"])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="construction"
        )

    async def test_uses_ti_category_for_ti_sector(self):
        """Sector 'ti' mapea a categoría 'ti'."""
        uc, service, _ = self._make_use_case(supplier_sectors=["ti"])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="ti"
        )

    async def test_uses_ti_category_for_tecnologia(self):
        """Sector 'tecnología' también mapea a categoría 'ti'."""
        uc, service, _ = self._make_use_case(supplier_sectors=["tecnología"])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="ti"
        )

    async def test_uses_general_category_when_no_supplier(self):
        """Si no se encuentra el supplier, usa categoría 'general'."""
        uc, service, _ = self._make_use_case(supplier_sectors=None)
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="general"
        )

    async def test_uses_general_category_when_empty_sectors(self):
        """Supplier sin sectores retorna categoría 'general'."""
        uc, service, _ = self._make_use_case(supplier_sectors=[])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="general"
        )

    async def test_uses_general_for_unknown_sector(self):
        """Sector no reconocido debe resultar en categoría 'general'."""
        uc, service, _ = self._make_use_case(supplier_sectors=["gastronomia"])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="general"
        )

    # — Normalización de sectores —

    async def test_sector_normalization_strips_whitespace(self):
        """Sectores con espacios deben normalizarse correctamente."""
        uc, service, _ = self._make_use_case(supplier_sectors=["  construction  "])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="construction"
        )

    async def test_sector_normalization_lowercases(self):
        """Sectores en mayúsculas deben normalizarse a minúsculas."""
        uc, service, _ = self._make_use_case(supplier_sectors=["CONSTRUCTION"])
        await uc.execute(PROVIDER_ID)
        service.get_or_generate_questions.assert_called_once_with(
            provider_id=PROVIDER_ID, category="construction"
        )

    # — Resultado final —

    async def test_returns_questions_from_service(self):
        """El use case debe retornar exactamente lo que devuelve el servicio."""
        expected = [make_question(), make_question()]
        uc, service, _ = self._make_use_case(
            supplier_sectors=["ti"], questions=expected
        )
        result = await uc.execute(PROVIDER_ID)
        assert result == expected

    async def test_calls_supplier_repo_with_correct_id(self):
        """El use case debe buscar al supplier usando el provider_id recibido."""
        uc, _, supplier_repo = self._make_use_case(supplier_sectors=["ti"])
        await uc.execute(PROVIDER_ID)
        supplier_repo.get_by_id.assert_called_once_with(supplier_id=PROVIDER_ID)


# ─────────────────────────────────────────────
# Issue #38 — Repositorio (lógica de mapeo)
# ─────────────────────────────────────────────


class TestQuestionRepositoryMapping:
    """
    Tests de la lógica de mapeo entity ↔ model en QuestionRepositoryImpl.
    Se prueba el mapeo directamente sin base de datos real.
    """

    def _make_repo(self):
        from app.infrastructure.repositories.question_repository import (
            QuestionRepositoryImpl,
        )

        session = AsyncMock()
        session.flush = AsyncMock()
        return QuestionRepositoryImpl(session=session)

    def test_to_entity_roundtrip(self):
        """_to_model y _to_entity deben ser inversas una de la otra."""
        repo = self._make_repo()

        original = make_question()
        model = repo._to_model(original)
        recovered = repo._to_entity(model)

        assert recovered.id == original.id
        assert recovered.provider_id == original.provider_id
        assert recovered.question == original.question
        assert recovered.target_profile_field == original.target_profile_field
        assert recovered.target_category == original.target_category
        assert recovered.options == original.options
        assert recovered.answered == original.answered
        assert recovered.omitted == original.omitted

    def test_to_model_preserves_answered_flag(self):
        """El flag 'answered' debe propagarse correctamente al modelo."""
        repo = self._make_repo()
        q = make_question(answered=True, answer="Sí")
        model = repo._to_model(q)
        assert model.answered is True
        assert model.answer == "Sí"

    def test_to_model_preserves_omitted_flag(self):
        """El flag 'omitted' debe propagarse correctamente al modelo."""
        repo = self._make_repo()
        q = make_question(omitted=True)
        model = repo._to_model(q)
        assert model.omitted is True

    async def test_save_all_flushes_each_question(self):
        """save_all debe llamar a session.flush por cada entidad guardada."""
        repo = self._make_repo()
        questions = [make_question(), make_question(), make_question()]
        await repo.save_all(questions)
        assert cast(AsyncMock, repo.session).flush.call_count == 3

    async def test_save_all_adds_each_model_to_session(self):
        """save_all debe llamar a session.add por cada entidad."""
        repo = self._make_repo()
        questions = [make_question(), make_question()]
        await repo.save_all(questions)
        assert cast(AsyncMock, repo.session).add.call_count == 2

    async def test_save_all_returns_same_count(self):
        """save_all debe retornar la misma cantidad de entidades que recibió."""
        repo = self._make_repo()
        questions = [make_question() for _ in range(5)]
        result = await repo.save_all(questions)
        assert len(result) == 5
