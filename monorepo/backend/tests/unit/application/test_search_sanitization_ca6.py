"""Tests dedicados para CA-6: Sanitización y mitigación demostrable de Inyección SQL.

Valida que el buscador responda de forma segura, controlada y sin errores 500 ante
payloads clásicos de inyección SQL (SQLi), ataques XSS y caracteres de control,
demostrando que ninguna entrada maliciosa altera el predicado de consulta.
"""

from uuid import uuid4
import pytest

from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.repositories.tender_vector_repository import ITenderVectorRepository
from app.application.schemas.tender_schema import TenderFilterCriteria
from app.application.use_cases.tender.search_tenders import SearchTendersUseCase
from app.domain.entities.tender import Tender
from app.shared.search_sanitizer import sanitize_search_query
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemorySupplierRepository,
)


# ---------------------------------------------------------------------------
# Dobles de prueba
# ---------------------------------------------------------------------------


class FakeTenderVectorRepo(ITenderVectorRepository):
    def __init__(self) -> None:
        self.search_results: list[tuple] = []
        self.total = 0
        self.searched_vectors: list[list[float]] = []

    async def ensure_collection(self) -> None:
        pass

    async def upsert(self, tender_id, embedding, p) -> None:
        pass

    async def delete(self, tender_id) -> None:
        pass

    async def search_by_vector(self, vector, limit, offset=0, criteria=None):
        self.searched_vectors.append(vector)
        return self.search_results

    async def count(self, criteria=None) -> int:
        return self.total


class FakeTenderRepo(ITenderRepository):
    def __init__(self) -> None:
        self.tenders: dict = {}
        self.search_calls: list[tuple] = []

    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:
        return [self.tenders[i] for i in (filters.ids or []) if i in self.tenders]

    async def search_tenders(
        self, criteria: TenderFilterCriteria, limit: int, offset: int = 0, q: str | None = None
    ) -> tuple[list[Tender], int]:
        self.search_calls.append((criteria, limit, offset, q))
        if q:
            matches = [
                t for t in self.tenders.values()
                if q.lower() in t.name.lower() or (t.description and q.lower() in t.description.lower())
            ]
            return matches[:limit], len(matches)
        return list(self.tenders.values())[:limit], len(self.tenders)

    async def get_by_code(self, code: str):
        return None

    async def get_or_create_buyer(self, *args, **kwargs):
        return ""

    async def get_comuna_id_by_name(self, name: str):
        return None

    async def get_provincia_id_by_comuna_id(self, comuna_id: int):
        return None

    async def get_or_create_status(self, status_id: int, code: str):
        return status_id

    async def save_complex_tender(self, tender_model, items):
        pass

    async def rollback(self):
        pass

    async def get_deep_analysis(self, tender_id, supplier_id):
        return None

    async def save_deep_analysis(self, deep_analysis):
        return deep_analysis

    async def get_latest_tender_created_at(self):
        return None


# ---------------------------------------------------------------------------
# 1. Tests del Sanitizador Unitario
# ---------------------------------------------------------------------------


class TestSearchSanitizer:
    @pytest.mark.parametrize(
        "payload",
        [
            "' OR 1=1 --",
            "' OR '1'='1",
            "1; DROP TABLE tenders;",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "1' AND 1=1 --",
            "/* comment */ ' OR 1=1 --",
            "'; EXEC xp_cmdshell('dir');--",
        ],
    )
    def test_neutraliza_payloads_de_inyeccion_sql(self, payload: str) -> None:
        sanitized = sanitize_search_query(payload)
        assert "'" not in sanitized
        assert '"' not in sanitized
        assert ";" not in sanitized
        assert "--" not in sanitized
        assert "/*" not in sanitized
        assert "*/" not in sanitized
        assert "DROP TABLE" not in sanitized.upper()
        assert "UNION SELECT" not in sanitized.upper()
        assert "1=1" not in sanitized

    def test_remueve_etiquetas_html_y_scripts(self) -> None:
        payload = "<script>alert('xss')</script>vehículo"
        sanitized = sanitize_search_query(payload)
        assert "<script>" not in sanitized
        assert "</script>" not in sanitized
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "vehículo" in sanitized

    def test_remueve_caracteres_nulos_y_de_control(self) -> None:
        payload = "\x00lluvia\r\n"
        sanitized = sanitize_search_query(payload)
        assert "\x00" not in sanitized
        assert sanitized == "lluvia"

    def test_preserva_terminos_lexicos_validos_con_tildes(self) -> None:
        query = "  Construcción de Techumbre y Vehículos  "
        sanitized = sanitize_search_query(query)
        assert sanitized == "Construcción de Techumbre y Vehículos"


# ---------------------------------------------------------------------------
# 2. Tests de Use Case ante Payloads de Inyección SQL (CA-6)
# ---------------------------------------------------------------------------


class TestSearchTendersUseCaseSanitizationCA6:
    @pytest.fixture
    def setup_use_case(self):
        user_id = uuid4()
        supplier_repo = InMemorySupplierRepository()
        supplier_vector_repo = FakeSupplierVectorRepository()
        tender_vector_repo = FakeTenderVectorRepo()
        tender_repo = FakeTenderRepo()
        embedding_service = FakeEmbeddingService()
        use_case = SearchTendersUseCase(
            supplier_repo=supplier_repo,
            supplier_vector_repo=supplier_vector_repo,
            tender_vector_repo=tender_vector_repo,
            tender_repo=tender_repo,
            embedding_service=embedding_service,
        )
        return use_case, user_id, tender_repo, tender_vector_repo, embedding_service

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sqli_payload",
        [
            "' OR 1=1 --",
            "1; DROP TABLE tenders;",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "' OR '1'='1",
            "<script>alert(1)</script>",
        ],
    )
    async def test_sqli_payload_retorna_cero_resultados_sin_error_500(
        self, setup_use_case, sqli_payload: str
    ) -> None:
        use_case, user_id, tender_repo, tender_vector_repo, embedding_service = setup_use_case

        result = await use_case.execute(user_id=user_id, q=sqli_payload)

        assert result.items == []
        assert result.total == 0
        assert result.is_truncated is False
        assert len(tender_vector_repo.searched_vectors) == 0

    @pytest.mark.asyncio
    async def test_busqueda_lexica_no_llama_a_qdrant_con_terminos_reales(
        self, setup_use_case
    ) -> None:
        """Una búsqueda léxica como 'lluvia' o 'vehiculo' consulta a Postgres FTS, no a Qdrant."""
        use_case, user_id, tender_repo, tender_vector_repo, embedding_service = setup_use_case

        result = await use_case.execute(user_id=user_id, q="lluvia")

        assert len(tender_repo.search_calls) == 1
        assert tender_repo.search_calls[0][3] == "lluvia"
        assert len(embedding_service.calls) == 0
        assert len(tender_vector_repo.searched_vectors) == 0
