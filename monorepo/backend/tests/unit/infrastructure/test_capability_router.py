"""Router del banco de capacidades (HU-20, B0b).

Se arma con los casos de uso reales sobre repositorios en memoria: lo que se
prueba es el contrato HTTP —empresa activa, permiso, códigos de error—, no la
persistencia, que cubren los tests de integración.
"""

from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.use_cases.capabilities.add_capability_evidence import (
    AddCapabilityEvidenceUseCase,
)
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.domain.entities.capability import CapabilityOption, CapabilityQuestion
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_member import (
    ALL_PERMISSIONS,
    MemberRole,
    SupplierMember,
    WorkspaceContext,
)
from app.infrastructure.routers.capability import create_capability_router
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.fakes import (
    InMemoryCapabilityAnswerRepository,
    InMemoryCapabilityEvidenceRepository,
    InMemoryCapabilityQuestionRepository,
    InMemorySupplierRepository,
)

SEC = CapabilityQuestion(
    question="¿Cuenta con certificación SEC clase A?",
    target_field="sec_clase_a",
    category="construccion",
    kind="certificacion",
    options=[
        CapabilityOption(label="No", polarity="negativa"),
        CapabilityOption(label="Sí", polarity="afirmativa"),
    ],
)
VIALES = CapabilityQuestion(
    question="¿Tiene experiencia en obras viales?",
    target_field="experiencia:obras-viales",
    category="construccion",
    kind="experiencia_proyecto",
    work_type="obras viales",
    options=[
        CapabilityOption(label="No", polarity="negativa"),
        CapabilityOption(label="Sí", polarity="afirmativa"),
    ],
)


def _contexto(user_id: UUID, supplier_id: UUID, role: MemberRole) -> WorkspaceContext:
    member = SupplierMember(user_id=user_id, supplier_id=supplier_id, role=role)
    return WorkspaceContext(
        user_id=user_id,
        active_supplier_id=supplier_id,
        active_supplier_name="Activa",
        role=role,
        permissions=[p for p in ALL_PERMISSIONS if member.has_permission(p)],
    )


class Api:
    """Un usuario que es miembro (con el rol que se elija) de una empresa ajena."""

    def __init__(self, role: MemberRole | None = MemberRole.MEMBER) -> None:
        self.suppliers = InMemorySupplierRepository()
        self.questions = InMemoryCapabilityQuestionRepository([SEC, VIALES])
        self.answers = InMemoryCapabilityAnswerRepository()
        self.evidences = InMemoryCapabilityEvidenceRepository()
        self.user_id = uuid4()
        self.role = role

    async def preparar(self) -> "Api":
        # La empresa activa no es del usuario: llega por el `WorkspaceContext`.
        self.empresa = await self.suppliers.save(
            Supplier(user_id=uuid4(), rut="76086428-5", legal_name="Activa SpA")
        )
        app = FastAPI()
        contexto = (
            _contexto(self.user_id, self.empresa.id, self.role) if self.role else None
        )
        app.include_router(
            create_capability_router(
                get_current_user=lambda: SimpleNamespace(id=self.user_id),
                get_build_catalog_use_case=lambda: BuildExperienceCatalogUseCase(
                    self.suppliers, self.questions, self.answers, self.evidences
                ),
                get_answer_use_case=lambda: AnswerCapabilityQuestionUseCase(
                    self.suppliers, self.questions, self.answers
                ),
                get_add_evidence_use_case=lambda: AddCapabilityEvidenceUseCase(
                    self.suppliers, self.questions, self.answers, self.evidences
                ),
                get_current_workspace_context=lambda: contexto,
            )
        )
        self.client = TestClient(app)
        return self

    def responder(self, question: CapabilityQuestion, answer: str = "Sí", **extra):
        return self.client.post(
            f"/capabilities/questions/{question.id}/answer",
            json={"answer": answer, **extra},
        )

    def evidencia(self, question: CapabilityQuestion, **datos):
        cuerpo = {"title": "Pavimentación calle Los Aromos", "year": 2024, **datos}
        return self.client.post(
            f"/capabilities/questions/{question.id}/evidence", json=cuerpo
        )


@pytest.fixture
async def api() -> Api:
    return await Api().preparar()


class TestResponder:
    async def test_responde_por_la_empresa_activa(self, api: Api):
        response = api.responder(SEC)

        assert response.status_code == 200
        cuerpo = response.json()
        assert cuerpo["supplier_id"] == str(api.empresa.id)
        assert cuerpo["answered_by_user_id"] == str(api.user_id)
        assert await api.answers.get(api.empresa.id, SEC.id) is not None

    async def test_ignora_un_supplier_id_del_cliente(self, api: Api):
        response = api.responder(SEC, supplier_id=str(uuid4()))

        assert response.status_code == 422

    async def test_guarda_la_vigencia_en_utc_sin_zona(self, api: Api):
        response = api.responder(SEC, valid_until="2027-06-30T00:00:00-03:00")

        assert response.status_code == 200
        assert response.json()["valid_until"] == "2027-06-30T03:00:00Z"
        guardada = await api.answers.get(api.empresa.id, SEC.id)
        assert guardada is not None
        assert guardada.valid_until == datetime(2027, 6, 30, 3, 0)

    async def test_una_vigencia_sin_zona_es_422(self, api: Api):
        """Sin zona no se sabe si es UTC u hora de Chile: se rechaza en vez de adivinar."""
        assert api.responder(SEC, valid_until="2027-06-30T00:00:00").status_code == 422

    async def test_una_respuesta_que_no_es_opcion_es_422(self, api: Api):
        assert api.responder(SEC, answer="Tal vez").status_code == 422

    async def test_una_pregunta_inexistente_es_404(self, api: Api):
        response = api.client.post(
            f"/capabilities/questions/{uuid4()}/answer", json={"answer": "Sí"}
        )
        assert response.status_code == 404

    async def test_un_viewer_no_puede_responder(self):
        api = await Api(MemberRole.VIEWER).preparar()

        assert api.responder(SEC).status_code == 403
        assert await api.answers.get(api.empresa.id, SEC.id) is None


class TestEvidencia:
    async def test_agrega_un_proyecto_al_si(self, api: Api):
        api.responder(VIALES)

        response = api.evidencia(
            VIALES, buyer="Municipalidad de Quilpué", amount_clp=45_000_000
        )

        assert response.status_code == 201
        cuerpo = response.json()
        assert cuerpo["work_type"] == "obras viales"
        assert cuerpo["origin"] == "manual"
        assert cuerpo["created_by_user_id"] == str(api.user_id)
        assert len(api.evidences.filas) == 1

    async def test_no_acepta_elegir_el_origen(self, api: Api):
        api.responder(VIALES)

        assert api.evidencia(VIALES, origin="mercado_publico").status_code == 422

    async def test_sin_un_si_es_409(self, api: Api):
        api.responder(VIALES, answer="No")

        assert api.evidencia(VIALES).status_code == 409

    async def test_un_anio_futuro_es_422(self, api: Api):
        api.responder(VIALES)

        response = api.evidencia(VIALES, year=utc_now_naive().year + 1)

        assert response.status_code == 422
        assert api.evidences.filas == []

    async def test_un_viewer_no_puede_agregar(self):
        api = await Api(MemberRole.VIEWER).preparar()

        assert api.evidencia(VIALES).status_code == 403


class TestCatalogo:
    async def test_muestra_lo_que_respondio_la_empresa(self, api: Api):
        api.responder(SEC)

        response = api.client.get("/capabilities/catalog")

        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["items"]}
        assert f"capacidad:{SEC.id}" in ids

    async def test_un_viewer_si_puede_verlo(self):
        api = await Api(MemberRole.VIEWER).preparar()

        assert api.client.get("/capabilities/catalog").status_code == 200

    async def test_sin_empresa_es_404(self):
        api = await Api(role=None).preparar()

        assert api.client.get("/capabilities/catalog").status_code == 404
