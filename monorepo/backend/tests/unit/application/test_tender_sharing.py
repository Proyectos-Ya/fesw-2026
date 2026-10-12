from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.sharing.tender_sharing import (
    CreateShareLinkUseCase,
    GetSharedTenderUseCase,
    ListShareLinksUseCase,
    RevokeShareLinkUseCase,
)
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.supplier_member import MemberRole, WorkspaceContext
from app.domain.entities.tender import Tender
from app.domain.entities.tender_share_link import hash_share_token
from app.domain.errors.sharing_errors import (
    ShareLinkExpired,
    ShareLinkForbidden,
    ShareLinkNotFound,
    ShareLinkRevoked,
)
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import (
    InMemoryMatchingResultRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.sharing_fakes import InMemoryTenderShareLinkRepository

AHORA = datetime(2026, 9, 28, 12, 0, 0)
BASE_URL = "https://app.proyectosya.cl"
EMPRESA = uuid4()


def _contexto(
    rol: MemberRole = MemberRole.MEMBER,
    user_id: UUID | None = None,
    supplier_id: UUID = EMPRESA,
    permisos: list[str] | None = None,
) -> WorkspaceContext:
    return WorkspaceContext(
        user_id=user_id or uuid4(),
        active_supplier_id=supplier_id,
        active_supplier_name="Constructora Andes",
        role=rol,
        permissions=["view_matches"] if permisos is None else permisos,
        is_admin=rol is MemberRole.ADMIN,
    )


def _licitacion() -> Tender:
    return Tender(
        code="1057539-228-COT26",
        name="Mantención de áreas verdes",
        description="Corte de pasto y poda en plazas.",
        status_id=1,
        status_code="publicada",
        published_at=AHORA - timedelta(days=2),
        closing_at=AHORA + timedelta(days=10),
        last_change_at=AHORA,
        buyer_rut="61.980.170-9",
        buyer_name="Municipalidad de Providencia",
        buyer_unit="Operaciones",
        available_amount_clp=5_000_000,
    )


class Escenario:
    def __init__(self) -> None:
        self.links = InMemoryTenderShareLinkRepository()
        self.tenders = InMemoryTenderRepository()
        self.suppliers = InMemorySupplierRepository()
        self.matching = InMemoryMatchingResultRepository()
        self.ahora = AHORA
        self.tender = _licitacion()
        self.tenders.tenders[self.tender.id] = self.tender

    def reloj(self) -> datetime:
        return self.ahora

    def crear(self) -> CreateShareLinkUseCase:
        return CreateShareLinkUseCase(
            links=self.links, tenders=self.tenders, base_url=BASE_URL, now=self.reloj
        )

    def listar(self) -> ListShareLinksUseCase:
        return ListShareLinksUseCase(links=self.links, now=self.reloj)

    def revocar(self) -> RevokeShareLinkUseCase:
        return RevokeShareLinkUseCase(links=self.links, now=self.reloj)

    def abrir(self) -> GetSharedTenderUseCase:
        return GetSharedTenderUseCase(
            links=self.links,
            tenders=self.tenders,
            suppliers=self.suppliers,
            matching_results=self.matching,
            now=self.reloj,
        )


@pytest.fixture
def esc() -> Escenario:
    return Escenario()


def _token(url: str) -> str:
    return url.rsplit("/", 1)[1]


class TestCrear:
    async def test_devuelve_una_url_publica_con_vigencia_de_siete_dias(self, esc):
        creado = await esc.crear().execute(_contexto(), esc.tender.id)

        assert creado.url.startswith(f"{BASE_URL}/compartido/")
        assert creado.link.expires_at == AHORA + timedelta(days=7)

    async def test_guarda_solo_el_hash_del_token(self, esc):
        creado = await esc.crear().execute(_contexto(), esc.tender.id)

        guardado = esc.links.links[creado.link.id]
        assert guardado.token_hash == hash_share_token(_token(creado.url))

    async def test_cada_vez_genera_una_url_distinta(self, esc):
        uno = await esc.crear().execute(_contexto(), esc.tender.id)
        otro = await esc.crear().execute(_contexto(), esc.tender.id)

        assert uno.url != otro.url

    async def test_fija_la_empresa_activa_y_quien_lo_creo(self, esc):
        contexto = _contexto()

        creado = await esc.crear().execute(contexto, esc.tender.id)

        assert creado.link.supplier_id == contexto.active_supplier_id
        assert creado.link.created_by == contexto.user_id

    async def test_la_licitacion_tiene_que_existir(self, esc):
        with pytest.raises(TenderNotFound):
            await esc.crear().execute(_contexto(), uuid4())

    async def test_sin_permiso_de_ver_licitaciones_no_puede_compartir(self, esc):
        with pytest.raises(ShareLinkForbidden):
            await esc.crear().execute(_contexto(permisos=[]), esc.tender.id)


class TestListar:
    async def test_solo_los_activos_de_esa_licitacion_y_empresa(self, esc):
        contexto = _contexto()
        vigente = await esc.crear().execute(contexto, esc.tender.id)
        revocado = await esc.crear().execute(contexto, esc.tender.id)
        await esc.revocar().execute(contexto, esc.tender.id, revocado.link.id)
        await esc.crear().execute(_contexto(supplier_id=uuid4()), esc.tender.id)

        enlaces = await esc.listar().execute(contexto, esc.tender.id)

        assert [e.id for e in enlaces] == [vigente.link.id]

    async def test_no_muestra_los_caducados(self, esc):
        contexto = _contexto()
        await esc.crear().execute(contexto, esc.tender.id)
        esc.ahora = AHORA + timedelta(days=7)

        assert await esc.listar().execute(contexto, esc.tender.id) == []


class TestRevocar:
    async def test_quien_lo_creo_puede_revocarlo(self, esc):
        contexto = _contexto()
        creado = await esc.crear().execute(contexto, esc.tender.id)

        await esc.revocar().execute(contexto, esc.tender.id, creado.link.id)

        assert esc.links.links[creado.link.id].revoked_at == AHORA

    async def test_un_admin_de_la_empresa_puede_revocar_el_de_otro(self, esc):
        creado = await esc.crear().execute(_contexto(), esc.tender.id)

        await esc.revocar().execute(
            _contexto(rol=MemberRole.ADMIN), esc.tender.id, creado.link.id
        )

        assert esc.links.links[creado.link.id].revoked_at == AHORA

    async def test_otro_miembro_no_puede_y_no_se_entera_de_que_existe(self, esc):
        creado = await esc.crear().execute(_contexto(), esc.tender.id)

        with pytest.raises(ShareLinkNotFound):
            await esc.revocar().execute(_contexto(), esc.tender.id, creado.link.id)
        assert esc.links.links[creado.link.id].revoked_at is None

    async def test_un_admin_de_otra_empresa_no_puede(self, esc):
        creado = await esc.crear().execute(_contexto(), esc.tender.id)
        ajeno = _contexto(rol=MemberRole.ADMIN, supplier_id=uuid4())

        with pytest.raises(ShareLinkNotFound):
            await esc.revocar().execute(ajeno, esc.tender.id, creado.link.id)

    async def test_el_enlace_tiene_que_ser_de_la_licitacion_de_la_ruta(self, esc):
        contexto = _contexto()
        creado = await esc.crear().execute(contexto, esc.tender.id)

        with pytest.raises(ShareLinkNotFound):
            await esc.revocar().execute(contexto, uuid4(), creado.link.id)


class TestAbrirSinSesion:
    async def _compartir(self, esc: Escenario) -> str:
        creado = await esc.crear().execute(_contexto(), esc.tender.id)
        return _token(creado.url)

    async def test_muestra_la_licitacion_con_el_puntaje_y_el_analisis(self, esc):
        # Criterio 2: quien abre el enlace no inicia sesión.
        await esc.matching.save_on_demand(
            MatchingResult(
                supplier_id=EMPRESA,
                tender_id=esc.tender.id,
                final_score=0.84,
                model_version="test",
                source="on_demand",
            )
        )
        await esc.tenders.save_deep_analysis(
            DeepAnalysis(
                tender_id=esc.tender.id,
                supplier_id=EMPRESA,
                compatibility_score=84,
                recommendation="Postular",
                justification="El rubro coincide con la experiencia declarada.",
            )
        )
        token = await self._compartir(esc)

        compartido = await esc.abrir().execute(token)

        assert compartido.tender.id == esc.tender.id
        assert compartido.score_pct == 84
        assert compartido.analysis is not None
        assert compartido.analysis.recommendation == "Postular"
        assert compartido.expires_at == AHORA + timedelta(days=7)

    async def test_sin_puntaje_ni_analisis_igual_muestra_la_licitacion(self, esc):
        # Nunca se genera un análisis desde un enlace público: cuesta una
        # inferencia y la pagaría alguien que no la pidió.
        token = await self._compartir(esc)

        compartido = await esc.abrir().execute(token)

        assert compartido.score_pct is None
        assert compartido.analysis is None

    async def test_el_analisis_de_otra_empresa_no_se_filtra(self, esc):
        await esc.tenders.save_deep_analysis(
            DeepAnalysis(
                tender_id=esc.tender.id,
                supplier_id=uuid4(),
                compatibility_score=10,
                recommendation="No recomendado",
                justification="Análisis de otra empresa.",
            )
        )
        token = await self._compartir(esc)

        assert (await esc.abrir().execute(token)).analysis is None

    async def test_un_token_inventado_no_existe(self, esc):
        with pytest.raises(ShareLinkNotFound):
            await esc.abrir().execute("token-inventado")

    async def test_cumplidos_los_siete_dias_caduca(self, esc):
        # Criterio 6.
        token = await self._compartir(esc)
        esc.ahora = AHORA + timedelta(days=7)

        with pytest.raises(ShareLinkExpired):
            await esc.abrir().execute(token)

    async def test_revocado_deja_de_funcionar_al_instante(self, esc):
        # Criterio 7.
        contexto = _contexto()
        creado = await esc.crear().execute(contexto, esc.tender.id)
        await esc.revocar().execute(contexto, esc.tender.id, creado.link.id)

        with pytest.raises(ShareLinkRevoked):
            await esc.abrir().execute(_token(creado.url))

    async def test_si_la_licitacion_desaparecio_el_enlace_no_existe(self, esc):
        token = await self._compartir(esc)
        esc.tenders.tenders.clear()

        with pytest.raises(ShareLinkNotFound):
            await esc.abrir().execute(token)
