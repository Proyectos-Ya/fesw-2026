from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.milestones.set_milestone_reminder import (
    SetMilestoneReminderUseCase,
)
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.domain.errors.milestone_errors import MilestoneNotFound
from tests.unit.application.milestone_fakes import InMemoryTenderMilestoneRepository

AHORA = datetime(2026, 10, 1, 12, 0)
USUARIO = uuid4()
LICITACION = uuid4()


def _hito(**cambios: object) -> TenderMilestone:
    datos: dict[str, object] = {
        "user_id": USUARIO,
        "tender_id": LICITACION,
        "kind": MilestoneKind.VISITA_TECNICA,
        "title": "Visita técnica",
        "source": MilestoneSource.IA_DOCUMENTO,
        "due_at": AHORA + timedelta(days=10),
        "has_time": True,
    }
    datos.update(cambios)
    return TenderMilestone.model_validate(datos)


@pytest.fixture
def escenario():
    hitos = InMemoryTenderMilestoneRepository()
    return hitos, SetMilestoneReminderUseCase(milestones=hitos)


async def test_activa_el_recordatorio_con_la_anticipacion_pedida(escenario):
    hitos, use_case = escenario
    hito = _hito()
    await hitos.save_many([hito])

    guardado = await use_case.execute(USUARIO, LICITACION, hito.id, 3)

    assert guardado.reminder_days_before == 3


async def test_apagarlo_deja_la_anticipacion_en_nulo(escenario):
    hitos, use_case = escenario
    hito = _hito(reminder_days_before=7)
    await hitos.save_many([hito])

    guardado = await use_case.execute(USUARIO, LICITACION, hito.id, None)

    assert guardado.reminder_days_before is None


async def test_reactivarlo_permite_volver_a_avisar(escenario):
    hitos, use_case = escenario
    # Ya se avisó con 1 día de anticipación; el usuario cambia a 7.
    hito = _hito(reminder_days_before=1, reminder_sent_at=AHORA)
    await hitos.save_many([hito])

    guardado = await use_case.execute(USUARIO, LICITACION, hito.id, 7)

    assert guardado.reminder_sent_at is None
    assert await hitos.list_pending_reminders(AHORA + timedelta(days=4)) == [guardado]


async def test_un_hito_de_otro_usuario_no_existe(escenario):
    hitos, use_case = escenario
    ajeno = _hito(user_id=uuid4())
    await hitos.save_many([ajeno])

    with pytest.raises(MilestoneNotFound):
        await use_case.execute(USUARIO, LICITACION, ajeno.id, 3)


async def test_un_hito_de_otra_licitacion_no_se_toca(escenario):
    hitos, use_case = escenario
    # El hito es del usuario, pero la ruta apunta a otra licitación: no basta
    # con filtrar por usuario, y no hay que escribir para descubrirlo.
    otro = _hito(tender_id=uuid4())
    await hitos.save_many([otro])

    with pytest.raises(MilestoneNotFound):
        await use_case.execute(USUARIO, LICITACION, otro.id, 3)

    assert (await hitos.list_by_ids(USUARIO, [otro.id]))[0].reminder_days_before is None


async def test_un_hito_inexistente(escenario):
    _, use_case = escenario

    with pytest.raises(MilestoneNotFound):
        await use_case.execute(USUARIO, LICITACION, uuid4(), 3)
