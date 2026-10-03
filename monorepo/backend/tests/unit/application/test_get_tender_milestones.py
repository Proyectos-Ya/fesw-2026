from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.milestones.get_tender_milestones import (
    GetTenderMilestonesUseCase,
)
from app.domain.entities.calendar import CalendarEventLink, CalendarProvider
from app.domain.entities.tender import Tender
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    MilestoneUrgency,
    TenderMilestone,
)
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import (
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.milestone_fakes import (
    InMemoryCalendarEventLinkRepository,
    InMemoryTenderMilestoneRepository,
)

AHORA = datetime(2026, 10, 1, 12, 0)
USUARIO = uuid4()


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
    chat = InMemoryTenderChatRepository()
    use_case = GetTenderMilestonesUseCase(
        tenders=tenders, milestones=hitos, event_links=enlaces, chat=chat, now=lambda: AHORA
    )
    return tender, hitos, enlaces, chat, use_case


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
    assert por_tipo[MilestoneKind.VISITA_TECNICA].urgency is MilestoneUrgency.PROXIMO
    assert por_tipo[MilestoneKind.VISITA_TECNICA].synced_providers == [CalendarProvider.GOOGLE]
    assert por_tipo[MilestoneKind.CIERRE_POSTULACION].synced_providers == []


async def test_cuenta_los_documentos_subidos_por_el_usuario(escenario):
    tender, _, _, chat, use_case = escenario
    documento = TenderChatDocument(
        tender_id=tender.id,
        user_id=USUARIO,
        file_name="bases.pdf",
        file_type="pdf",
        file_size_bytes=10,
        storage_path="/tmp/bases.pdf",
    )
    chat.documents[documento.id] = (documento, b"%PDF")

    resultado = await use_case.execute(USUARIO, tender.id)

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
    use_case = GetTenderMilestonesUseCase(
        tenders=tenders,
        milestones=hitos,
        event_links=InMemoryCalendarEventLinkRepository(),
        chat=InMemoryTenderChatRepository(),
        now=lambda: AHORA,
    )
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
