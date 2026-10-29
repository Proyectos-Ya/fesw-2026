"""
Pruebas unitarias para la PR #61
Cubre issues: #38, #39, #40, #41

Ubicar en: tests/test_smart_question.py
Ejecutar con: pytest -v
"""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

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
    # Mismo id que el usuario en estas pruebas: el caso de uso ahora resuelve la
    # empresa desde la sesión, y la cola de preguntas se guarda por empresa.
    # Igualarlos mantiene las aserciones legibles sin dos constantes casi iguales.
    supplier.id = PROVIDER_ID
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

    def _make_service(self, existing_questions=None):
        repo = AsyncMock()
        repo.get_active_by_provider.return_value = existing_questions or []
        return SmartQuestionServiceImpl(question_repository=repo), repo

    async def test_returns_existing_questions_from_repo(self):
        """Retorna las preguntas activas persistidas para el proveedor."""
        existing = [make_question(), make_question()]
        service, repo = self._make_service(existing_questions=existing)

        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")

        assert result == existing
        repo.get_active_by_provider.assert_awaited_once_with(PROVIDER_ID)

    async def test_returns_empty_list_when_no_active_questions(self):
        """No genera preguntas estáticas: si no hay preguntas activas, retorna lista vacía."""
        service, repo = self._make_service(existing_questions=[])

        result = await service.get_or_generate_questions(PROVIDER_ID, "construccion")

        assert result == []
        repo.get_active_by_provider.assert_awaited_once_with(PROVIDER_ID)


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
            supplier_repo.get_by_user_id.return_value = None
        else:
            supplier_repo.get_by_user_id.return_value = make_supplier(supplier_sectors)

        uc = SmartQuestionUseCase(
            smart_question_service=smart_service,
            supplier_repository=supplier_repo,
        )
        return uc, smart_service, supplier_repo

    # — Resolución de categoría (plan 311, CA 1) —
    # El use case traduce los rubros de Mercado Público a las categorías que
    # entiende `SmartQuestionServiceImpl`: "construccion", "ti" o "general".

    async def _categoria_para(self, sectores):
        uc, service, _ = self._make_use_case(supplier_sectors=sectores)
        await uc.execute(PROVIDER_ID)
        return service.get_or_generate_questions.call_args.kwargs["category"]

    @pytest.mark.parametrize(
        "sector", ["Obras", "Obras MINVU", "Servicios de construcción y mantenimiento"]
    )
    async def test_rubros_de_obras_dan_construccion(self, sector):
        assert await self._categoria_para([sector]) == "construccion"

    async def test_rubro_de_tecnologia_da_ti(self):
        assert (
            await self._categoria_para(
                ["Tecnologías de la información, telecomunicaciones y radiodifusión"]
            )
            == "ti"
        )

    async def test_rubro_sin_banco_propio_da_general(self):
        assert await self._categoria_para(["Productos de papel"]) == "general"

    async def test_con_rubros_de_dos_categorias_gana_el_primero(self):
        assert (
            await self._categoria_para(
                [
                    "Tecnologías de la información, telecomunicaciones y radiodifusión",
                    "Obras",
                ]
            )
            == "ti"
        )
        assert (
            await self._categoria_para(
                [
                    "Productos de papel",
                    "Obras",
                    "Tecnologías de la información, telecomunicaciones y radiodifusión",
                ]
            )
            == "construccion"
        )

    async def test_espacios_alrededor_del_rubro_no_cambian_la_categoria(self):
        assert await self._categoria_para(["  Obras  "]) == "construccion"

    def test_cada_rubro_del_mapa_existe_en_la_lista(self):
        """Un nombre mal copiado caería en "general" sin aviso."""
        from app.application.use_cases.questions.smart_question_use_case import (
            QUESTION_CATEGORY_BY_SECTOR,
        )
        from app.shared.sectors import PRODUCT_SECTORS

        assert set(QUESTION_CATEGORY_BY_SECTOR) <= set(PRODUCT_SECTORS)
        assert set(QUESTION_CATEGORY_BY_SECTOR.values()) == {"construccion", "ti"}

    async def test_uses_general_category_when_no_supplier(self):
        """Si no se encuentra el supplier, usa categoría 'general'."""
        assert await self._categoria_para(None) == "general"

    async def test_uses_general_category_when_empty_sectors(self):
        """Supplier sin sectores retorna categoría 'general'."""
        assert await self._categoria_para([]) == "general"

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
        supplier_repo.get_by_user_id.assert_called_once_with(PROVIDER_ID)


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

        session = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
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
