from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.milestone_extraction_background import (
    MilestoneExtractionStatus,
)
from app.application.use_cases.milestones.get_tender_milestones import (
    GetTenderMilestonesUseCase,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
)
from app.domain.entities.calendar import CalendarEventLink, CalendarProvider
from app.domain.entities.tender import Tender
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    MilestoneUrgency,
    TenderMilestone,
)
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository
from tests.unit.application.attachment_file_fakes import (
    InMemoryAttachmentFileRepository,
)
from tests.unit.application.fakes import (
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.milestone_fakes import (
    InMemoryCalendarEventLinkRepository,
    InMemoryMilestoneAttachmentRepository,
    InMemoryTenderMilestoneRepository,
)

AHORA = datetime(2026, 10, 1, 12, 0)
USUARIO = uuid4()
EMPRESA = uuid4()


class Anexos:
    """Los anexos guardados que ve la empresa (plan 233)."""

    def __init__(self) -> None:
        self.archivos = InMemoryAttachmentFileRepository()
        self.oficiales = InMemoryTenderAttachmentRepository()

    async def agregar(self, tender_id: UUID, nombre: str = "bases.pdf") -> UUID:
        oficial = await self.oficiales.create_attachment(tender_id, uuid4(), nombre)
        archivo = AttachmentFile(
            id=uuid4(),
            tender_attachment_id=oficial.id,
            tender_id=tender_id,
            sha256=uuid4().hex * 2,
            size_bytes=10,
            storage_key=f"anexos/{uuid4()}",
            source=AttachmentFileSource.MANUAL,
            uploader_user_id=uuid4(),
            workspace_id=EMPRESA,
            status=AttachmentFileStatus.STORED,
            created_at=AHORA,
        )
        self.archivos.filas[archivo.id] = archivo
        return archivo.id


def _consulta(tenders, hitos, enlaces, anexos: Anexos, extraction=None) -> GetTenderMilestonesUseCase:
    return GetTenderMilestonesUseCase(
        tenders=tenders,
        milestones=hitos,
        event_links=enlaces,
        files=anexos.archivos,
        attachments=anexos.oficiales,
        processed=InMemoryMilestoneAttachmentRepository(),
        suppliers=InMemorySupplierRepository(),
        extraction=extraction,
        now=lambda: AHORA,
    )


@pytest.fixture
def escenario():
    tender = Tender(
        code="COT-1",
        name="Reparación de techumbre",
        status_id=1,
        published_at=AHORA - timedelta(days=3),
        closing_at=AHORA + timedelta(days=2),
        last_change_at=AHORA,
        buyer_rut="12.345.678-9",
        buyer_unit="Operaciones",
    )
    tenders = InMemoryTenderRepository()
    tenders.tenders[tender.id] = tender
    hitos = InMemoryTenderMilestoneRepository()
    enlaces = InMemoryCalendarEventLinkRepository()
    anexos = Anexos()
    use_case = _consulta(tenders, hitos, enlaces, anexos)
    return tender, hitos, enlaces, anexos, use_case


async def test_la_primera_consulta_materializa_los_hitos_de_mercado_publico(escenario):
    tender, hitos, _, _, use_case = escenario

    resultado = await use_case.execute(USUARIO, tender.id)

    assert [v.milestone.kind for v in resultado.milestones] == [
        MilestoneKind.PUBLICACION,
        MilestoneKind.CIERRE_POSTULACION,
    ]
    # Quedan guardados para poder seleccionarlos y sincronizarlos.
    assert len(await hitos.list_for_tender(USUARIO, tender.id)) == 2


async def test_no_duplica_los_hitos_en_consultas_siguientes(escenario):
    tender, hitos, _, _, use_case = escenario

    await use_case.execute(USUARIO, tender.id)
    await use_case.execute(USUARIO, tender.id)

    assert len(await hitos.list_for_tender(USUARIO, tender.id)) == 2


async def test_informa_urgencia_y_proveedores_sincronizados(escenario):
    tender, hitos, enlaces, _, use_case = escenario
    visita = TenderMilestone(
        user_id=USUARIO,
        tender_id=tender.id,
        kind=MilestoneKind.VISITA_TECNICA,
        title="Visita técnica",
        source=MilestoneSource.IA_DOCUMENTO,
        # 4 días: dentro de los "5 días o menos" que el criterio 9 manda destacar.
        due_at=AHORA + timedelta(days=4),
        has_time=True,
    )
    await hitos.save_many([visita])
    await enlaces.save(
        CalendarEventLink(
            user_id=USUARIO,
            milestone_id=visita.id,
            provider=CalendarProvider.GOOGLE,
            external_event_id="evento",
            synced_due_at=visita.due_at,
        )
    )

    resultado = await use_case.execute(USUARIO, tender.id)

    por_tipo = {v.milestone.kind: v for v in resultado.milestones}
    assert por_tipo[MilestoneKind.PUBLICACION].urgency is MilestoneUrgency.VENCIDO
    assert por_tipo[MilestoneKind.CIERRE_POSTULACION].urgency is MilestoneUrgency.CRITICO
    assert por_tipo[MilestoneKind.VISITA_TECNICA].urgency is MilestoneUrgency.CRITICO
    assert por_tipo[MilestoneKind.VISITA_TECNICA].synced_providers == [CalendarProvider.GOOGLE]
    assert por_tipo[MilestoneKind.CIERRE_POSTULACION].synced_providers == []


async def test_cuenta_los_anexos_que_ve_la_empresa(escenario):
    tender, _, _, anexos, use_case = escenario
    await anexos.agregar(tender.id)

    resultado = await use_case.execute(USUARIO, tender.id, EMPRESA)

    assert resultado.documents_count == 1


async def test_licitacion_inexistente(escenario):
    *_, use_case = escenario

    with pytest.raises(TenderNotFound):
        await use_case.execute(USUARIO, uuid4())


def _escenario_con(**llamado: object):
    """Como el fixture `escenario`, con campos del llamado en la licitación.

    Devuelve también `tenders`: el fixture no lo expone y hace falta para
    cambiar la licitación entre dos consultas.
    """
    datos: dict[str, object] = {
        "code": "COT-2",
        "name": "Reparación de techumbre",
        "status_id": 1,
        "published_at": AHORA - timedelta(days=3),
        "closing_at": AHORA + timedelta(days=2),
        "last_change_at": AHORA,
        "buyer_rut": "12.345.678-9",
        "buyer_unit": "Operaciones",
    }
    datos.update(llamado)
    tender = Tender.model_validate(datos)
    tenders = InMemoryTenderRepository()
    tenders.tenders[tender.id] = tender
    hitos = InMemoryTenderMilestoneRepository()
    use_case = _consulta(tenders, hitos, InMemoryCalendarEventLinkRepository(), Anexos())
    return tender, tenders, hitos, use_case


def _hito_del_segundo_llamado(resultado) -> TenderMilestone:
    return next(
        v.milestone
        for v in resultado.milestones
        if v.milestone.kind is MilestoneKind.CIERRE_SEGUNDO_LLAMADO
    )


async def test_con_fecha_de_segundo_llamado_agrega_su_hito():
    segundo = AHORA + timedelta(days=3)
    tender, _, hitos, use_case = _escenario_con(call_number=1, second_call_closing_at=segundo)

    resultado = await use_case.execute(USUARIO, tender.id)

    assert [v.milestone.kind for v in resultado.milestones] == [
        MilestoneKind.PUBLICACION,
        MilestoneKind.CIERRE_POSTULACION,
        MilestoneKind.CIERRE_SEGUNDO_LLAMADO,
    ]
    hito = resultado.milestones[2].milestone
    assert hito.title == "Cierre del segundo llamado"
    assert hito.source is MilestoneSource.MERCADO_PUBLICO
    assert hito.has_time is True
    assert hito.due_at == segundo
    assert (hito.description or "").startswith("Fecha posible")
    assert len(await hitos.list_for_tender(USUARIO, tender.id)) == 3


async def test_en_segundo_llamado_el_hito_se_describe_como_vigente():
    segundo = AHORA + timedelta(days=3)
    tender, _, _, use_case = _escenario_con(
        call_number=2, closing_at=segundo, second_call_closing_at=segundo
    )

    resultado = await use_case.execute(USUARIO, tender.id)

    assert (
        _hito_del_segundo_llamado(resultado).description
        == "Llamado vigente: coincide con el cierre de recepción de ofertas."
    )


async def test_al_pasar_al_segundo_llamado_actualiza_el_mismo_hito():
    segundo = AHORA + timedelta(days=3)
    tender, tenders, hitos, use_case = _escenario_con(call_number=1, second_call_closing_at=segundo)
    antes = _hito_del_segundo_llamado(await use_case.execute(USUARIO, tender.id))

    tenders.tenders[tender.id] = tender.model_copy(
        update={"call_number": 2, "closing_at": segundo}
    )
    despues = await use_case.execute(USUARIO, tender.id)

    guardados = await hitos.list_for_tender(USUARIO, tender.id)
    assert len(guardados) == 3
    hito = _hito_del_segundo_llamado(despues)
    assert hito.id == antes.id
    assert hito.description != antes.description


async def test_sin_fecha_de_segundo_llamado_no_hay_hito_extra():
    tender, _, hitos, use_case = _escenario_con(call_number=1)

    await use_case.execute(USUARIO, tender.id)

    assert len(await hitos.list_for_tender(USUARIO, tender.id)) == 2


class EstadoFijo:
    def __init__(self, estado: MilestoneExtractionStatus) -> None:
        self.estado = estado
        self.consultas: list[tuple] = []
        self.agendadas: list[tuple] = []

    def status(self, user_id, tender_id) -> MilestoneExtractionStatus:
        self.consultas.append((user_id, tender_id))
        return self.estado

    def schedule(self, user_id, tender_id, workspace_id=None) -> None:
        self.agendadas.append((user_id, tender_id, workspace_id))


async def test_sin_extraccion_en_segundo_plano_el_estado_es_inactivo(escenario):
    tender, *_, use_case = escenario

    resultado = await use_case.execute(USUARIO, tender.id)

    assert resultado.extraction_status is MilestoneExtractionStatus.IDLE


async def test_informa_si_la_ia_esta_leyendo_las_bases(escenario):
    # Así la ficha puede mostrar "leyendo…" y recargar hasta que termine.
    tender, hitos, enlaces, anexos, _ = escenario
    tenders = InMemoryTenderRepository()
    tenders.tenders[tender.id] = tender
    extraccion = EstadoFijo(MilestoneExtractionStatus.RUNNING)
    use_case = _consulta(tenders, hitos, enlaces, anexos, extraccion)

    resultado = await use_case.execute(USUARIO, tender.id)

    assert resultado.extraction_status is MilestoneExtractionStatus.RUNNING
    assert extraccion.consultas == [(USUARIO, tender.id)]


async def test_informa_cuantas_bases_faltan_por_leer(escenario):
    # Habilita el botón solo si hay algo que leer: volver a leer lo mismo
    # duplicaba o borraba hitos.
    tender, _, _, anexos, use_case = escenario
    archivo_id = await anexos.agregar(tender.id)

    pendiente = await use_case.execute(USUARIO, tender.id, EMPRESA)
    await use_case.processed.mark_processed(USUARIO, tender.id, archivo_id, 2, AHORA)
    procesada = await use_case.execute(USUARIO, tender.id, EMPRESA)

    assert pendiente.pending_documents_count == 1
    assert procesada.pending_documents_count == 0


def _con_extraccion(escenario, estado: MilestoneExtractionStatus):
    tender, hitos, enlaces, anexos, _ = escenario
    tenders = InMemoryTenderRepository()
    tenders.tenders[tender.id] = tender
    extraccion = EstadoFijo(estado)
    return extraccion, _consulta(tenders, hitos, enlaces, anexos, extraccion)


async def test_agenda_la_extraccion_si_hay_anexos_sin_leer(escenario):
    # Otro miembro de la empresa subió las bases: al abrir la ficha, las lee para él.
    tender, *_ = escenario
    await escenario[3].agregar(tender.id)
    extraccion, use_case = _con_extraccion(escenario, MilestoneExtractionStatus.IDLE)

    await use_case.execute(USUARIO, tender.id, EMPRESA)

    assert extraccion.agendadas == [(USUARIO, tender.id, EMPRESA)]


@pytest.mark.parametrize(
    "estado", [MilestoneExtractionStatus.RUNNING, MilestoneExtractionStatus.FAILED]
)
async def test_no_agenda_si_ya_corre_o_si_la_ultima_fallo(escenario, estado):
    # Si falló, reintenta el usuario con el botón: agendar en cada consulta
    # repetiría la llamada a Gemini cada 4 s.
    tender, *_ = escenario
    await escenario[3].agregar(tender.id)
    extraccion, use_case = _con_extraccion(escenario, estado)

    await use_case.execute(USUARIO, tender.id, EMPRESA)

    assert extraccion.agendadas == []


async def test_un_anexo_que_la_ia_no_lee_no_queda_pendiente(escenario):
    tender, _, _, anexos, use_case = escenario
    await anexos.agregar(tender.id, "formulario.docx")

    resultado = await use_case.execute(USUARIO, tender.id, EMPRESA)

    assert resultado.pending_documents_count == 0
