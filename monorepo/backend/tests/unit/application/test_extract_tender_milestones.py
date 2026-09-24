from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.application.services.milestone_extraction_ai_service import ExtractedMilestone
from app.application.use_cases.milestones.extract_tender_milestones import (
    ExtractTenderMilestonesUseCase,
)
from app.domain.entities.calendar import CalendarEventLink, CalendarProvider
from app.domain.entities.tender import Tender
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.entities.tender_milestone import MilestoneKind, MilestoneSource
from app.domain.errors.milestone_errors import MilestoneExtractionUnavailable
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import (
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.milestone_fakes import (
    FakeMilestoneExtractionAIService,
    InMemoryCalendarEventLinkRepository,
    InMemoryTenderMilestoneRepository,
)

AHORA = datetime(2026, 10, 1, 12, 0)
USUARIO = uuid4()


def _licitacion() -> Tender:
    return Tender(
        code="1057539-228-COT26",
        name="Reparación de techumbre",
        status_id=1,
        published_at=datetime(2026, 9, 28, 13, 0),
        closing_at=datetime(2026, 10, 20, 18, 0),
        last_change_at=datetime(2026, 9, 28, 13, 0),
        buyer_rut="12.345.678-9",
        buyer_unit="Operaciones",
    )


def _hito_ia(**cambios: object) -> ExtractedMilestone:
    datos: dict[str, object] = {
        "kind": "visita_tecnica",
        "title": "Visita técnica obligatoria",
        "fecha": "2026-10-10",
        "hora": "10:00",
        "texto_original": "La visita será el día 10 a las 10:00 horas.",
        "documento": "bases.pdf",
    }
    datos.update(cambios)
    return ExtractedMilestone.model_validate(datos)


class Escenario:
    def __init__(self, hitos_ia: list[ExtractedMilestone] | None = None, falla_ia: bool = False):
        self.tender = _licitacion()
        self.tenders = InMemoryTenderRepository()
        self.tenders.tenders[self.tender.id] = self.tender
        self.chat = InMemoryTenderChatRepository()
        self.hitos = InMemoryTenderMilestoneRepository()
        self.enlaces = InMemoryCalendarEventLinkRepository()
        self.ia = FakeMilestoneExtractionAIService(hitos_ia, falla=falla_ia)
        self.use_case = ExtractTenderMilestonesUseCase(
            tenders=self.tenders,
            milestones=self.hitos,
            event_links=self.enlaces,
            chat=self.chat,
            ai=self.ia,
            now=lambda: AHORA,
        )

    def subir(self, nombre: str = "bases.pdf", contenido: bytes | None = b"%PDF", user_id: UUID = USUARIO) -> UUID:
        documento = TenderChatDocument(
            tender_id=self.tender.id,
            user_id=user_id,
            file_name=nombre,
            file_type="pdf",
            file_size_bytes=10,
            storage_path=f"/tmp/{nombre}",
        )
        self.chat.documents[documento.id] = (documento, contenido)
        return documento.id

    async def extraer(self):
        return await self.use_case.execute(USUARIO, self.tender.id)


class TestHitosDeMercadoPublico:
    async def test_sin_documentos_solo_entrega_publicacion_y_cierre(self):
        escenario = Escenario()

        resultado = await escenario.extraer()

        tipos = [v.milestone.kind for v in resultado.milestones]
        assert tipos == [MilestoneKind.PUBLICACION, MilestoneKind.CIERRE_POSTULACION]
        assert all(v.milestone.source is MilestoneSource.MERCADO_PUBLICO for v in resultado.milestones)
        assert resultado.milestones[1].milestone.due_at == escenario.tender.closing_at
        assert resultado.documents_count == 0
        assert escenario.ia.llamadas == []

    async def test_licitacion_inexistente(self):
        escenario = Escenario()

        with pytest.raises(TenderNotFound):
            await escenario.use_case.execute(USUARIO, uuid4())


class TestExtraccionConIA:
    async def test_envia_los_documentos_del_usuario_y_el_contexto_de_la_licitacion(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir("bases.pdf")
        escenario.subir("ajeno.pdf", user_id=uuid4())

        resultado = await escenario.extraer()

        documentos, contexto = escenario.ia.llamadas[0]
        assert [d.document_name for d in documentos] == ["bases.pdf"]
        assert "Reparación de techumbre" in contexto
        assert "2026-10-20 15:00" in contexto  # cierre en hora de Chile
        assert resultado.documents_count == 1

    async def test_guarda_los_hitos_de_la_ia_normalizados_y_con_su_fuente(self):
        escenario = Escenario([_hito_ia()])
        documento_id = escenario.subir("bases.pdf")

        resultado = await escenario.extraer()

        visita = next(v.milestone for v in resultado.milestones if v.milestone.kind is MilestoneKind.VISITA_TECNICA)
        assert visita.source is MilestoneSource.IA_DOCUMENTO
        assert visita.due_at == datetime(2026, 10, 10, 13, 0)  # 10:00 Chile = 13:00 UTC
        assert visita.has_time is True
        assert visita.source_excerpt == "La visita será el día 10 a las 10:00 horas."
        assert visita.source_document_id == documento_id
        assert len(await escenario.hitos.list_for_tender(USUARIO, escenario.tender.id)) == 3

    async def test_descarta_fechas_invalidas_y_las_cuenta(self):
        escenario = Escenario([_hito_ia(), _hito_ia(title="Consultas", kind="consultas", fecha="2026-02-30")])
        escenario.subir()

        resultado = await escenario.extraer()

        assert resultado.discarded_count == 1
        assert all(v.milestone.title != "Consultas" for v in resultado.milestones)

    async def test_un_tipo_desconocido_queda_como_otro(self):
        escenario = Escenario([_hito_ia(kind="reunion_informativa", title="Reunión informativa")])
        escenario.subir()

        resultado = await escenario.extraer()

        reunion = next(v.milestone for v in resultado.milestones if v.milestone.title == "Reunión informativa")
        assert reunion.kind is MilestoneKind.OTRO

    async def test_un_documento_sin_contenido_no_se_envia(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir("perdido.pdf", contenido=None)

        resultado = await escenario.extraer()

        assert escenario.ia.llamadas == []
        assert resultado.documents_count == 0

    async def test_si_la_ia_falla_igual_quedan_los_hitos_de_mercado_publico(self):
        escenario = Escenario(falla_ia=True)
        escenario.subir()

        with pytest.raises(MilestoneExtractionUnavailable):
            await escenario.extraer()

        guardados = await escenario.hitos.list_for_tender(USUARIO, escenario.tender.id)
        assert {h.kind for h in guardados} == {MilestoneKind.PUBLICACION, MilestoneKind.CIERRE_POSTULACION}


class TestReextraccion:
    async def test_conserva_el_id_del_mismo_hito_y_actualiza_su_fecha(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir()
        primero = await escenario.extraer()
        visita_id = next(v.milestone.id for v in primero.milestones if v.milestone.kind is MilestoneKind.VISITA_TECNICA)

        escenario.ia.hitos = [_hito_ia(title="  VISITA técnica   obligatoria ", fecha="2026-10-11")]
        segundo = await escenario.extraer()

        visitas = [v.milestone for v in segundo.milestones if v.milestone.kind is MilestoneKind.VISITA_TECNICA]
        assert [v.id for v in visitas] == [visita_id]
        assert visitas[0].due_at == datetime(2026, 10, 11, 13, 0)

    async def test_borra_hitos_de_ia_que_ya_no_aparecen_si_no_estan_sincronizados(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir()
        await escenario.extraer()

        escenario.ia.hitos = []
        resultado = await escenario.extraer()

        assert all(v.milestone.source is MilestoneSource.MERCADO_PUBLICO for v in resultado.milestones)

    async def test_conserva_hitos_de_ia_ya_sincronizados_aunque_no_aparezcan(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir()
        primero = await escenario.extraer()
        visita = next(v.milestone for v in primero.milestones if v.milestone.kind is MilestoneKind.VISITA_TECNICA)
        await escenario.enlaces.save(
            CalendarEventLink(
                user_id=USUARIO,
                milestone_id=visita.id,
                provider=CalendarProvider.GOOGLE,
                external_event_id="evento",
                synced_due_at=visita.due_at,
            )
        )

        escenario.ia.hitos = []
        resultado = await escenario.extraer()

        conservada = next(v for v in resultado.milestones if v.milestone.id == visita.id)
        assert conservada.synced_providers == [CalendarProvider.GOOGLE]
