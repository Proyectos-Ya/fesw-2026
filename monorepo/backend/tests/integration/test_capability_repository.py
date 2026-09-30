"""Repositorios del banco de capacidades contra Postgres real."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityEvidence,
    CapabilityOption,
    CapabilityQuestion,
)
from app.domain.errors.capability_errors import DuplicateCapabilityQuestion
from app.infrastructure.repositories.capability_model import (
    CapabilityAnswerModel,
    CapabilityEvidenceModel,
    CapabilityQuestionModel,
)
from app.infrastructure.repositories.sql_capability_repository import (
    SqlCapabilityAnswerRepository,
    SqlCapabilityEvidenceRepository,
    SqlCapabilityQuestionRepository,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.user_model import UserModel
from app.shared.datetime_utils import utc_now_naive

pytestmark = pytest.mark.integration


def _pregunta(**kwargs) -> CapabilityQuestion:
    datos = dict(
        question="¿Cuenta con inscripción en el Registro de Contratistas del MOP?",
        target_field="mop_registration",
        category="construccion",
        options=[
            CapabilityOption(label="No", polarity="negativa"),
            CapabilityOption(label="Sí", polarity="afirmativa"),
        ],
    )
    datos.update(kwargs)
    return CapabilityQuestion(**datos)


async def _empresa(session: AsyncSession) -> UUID:
    supplier_id = uuid4()
    now = utc_now_naive()
    session.add(
        SupplierModel(
            id=supplier_id,
            rut=f"{uuid4().int % 10**8}-1",
            legal_name="Empresa de prueba",
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    return supplier_id


async def test_guarda_y_recupera_una_pregunta_con_sus_opciones(db_session):
    repo = SqlCapabilityQuestionRepository(db_session)
    pregunta = await repo.add(
        _pregunta(kind="experiencia_proyecto", work_type="obras viales")
    )

    leida = await repo.get(pregunta.id)

    assert leida is not None
    assert leida.options == pregunta.options
    assert leida.work_type == "obras viales"
    assert await repo.get_by_key("construccion", "mop_registration") == leida


async def test_un_duplicado_de_categoria_y_campo_devuelve_la_existente(db_session):
    repo = SqlCapabilityQuestionRepository(db_session)
    existente = await repo.add(_pregunta())

    with pytest.raises(DuplicateCapabilityQuestion) as error:
        await repo.add(_pregunta(question="Otra redacción de lo mismo"))

    assert error.value.existing.id == existente.id


async def test_lista_solo_activas_de_las_categorias_pedidas(db_session):
    repo = SqlCapabilityQuestionRepository(db_session)
    activa = await repo.add(_pregunta(target_field="a"))
    await repo.add(_pregunta(target_field="b", active=False))
    await repo.add(_pregunta(target_field="c", category="ti"))

    assert [q.id for q in await repo.list_active({"construccion"})] == [activa.id]
    assert await repo.list_active(set()) == []


async def test_list_by_ids_incluye_las_inactivas(db_session):
    repo = SqlCapabilityQuestionRepository(db_session)
    inactiva = await repo.add(_pregunta(active=False))

    assert [q.id for q in await repo.list_by_ids([inactiva.id])] == [inactiva.id]
    assert await repo.list_by_ids([]) == []


async def test_save_reemplaza_la_respuesta_de_la_misma_empresa_y_pregunta(db_session):
    preguntas = SqlCapabilityQuestionRepository(db_session)
    respuestas = SqlCapabilityAnswerRepository(db_session)
    pregunta = await preguntas.add(_pregunta())
    supplier_id = await _empresa(db_session)

    primera = await respuestas.save(
        CapabilityAnswer(
            supplier_id=supplier_id,
            question_id=pregunta.id,
            answered=True,
            answer="No",
            answered_at=utc_now_naive(),
        )
    )
    await respuestas.save(primera.model_copy(update={"answer": "Sí"}))

    todas = await respuestas.list_by_supplier(supplier_id)
    assert len(todas) == 1
    assert todas[0].answer == "Sí"
    assert await respuestas.get(supplier_id, pregunta.id) == todas[0]


async def test_la_base_rechaza_respondida_y_omitida_a_la_vez(db_session):
    """La entidad ya lo impide; la restricción protege de escrituras que la salten."""
    preguntas = SqlCapabilityQuestionRepository(db_session)
    pregunta = await preguntas.add(_pregunta())
    supplier_id = await _empresa(db_session)

    db_session.add(
        CapabilityAnswerModel(
            id=uuid4(),
            supplier_id=supplier_id,
            question_id=pregunta.id,
            answer="Sí",
            answered=True,
            omitted=True,
            generated_at=utc_now_naive(),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def _usuario(session: AsyncSession) -> UUID:
    user_id = uuid4()
    now = utc_now_naive()
    session.add(
        UserModel(
            id=user_id,
            email=f"{user_id}@example.com",
            full_name="Miembro de prueba",
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    return user_id


async def test_save_guarda_quien_respondio_y_la_vigencia(db_session):
    preguntas = SqlCapabilityQuestionRepository(db_session)
    respuestas = SqlCapabilityAnswerRepository(db_session)
    pregunta = await preguntas.add(_pregunta(kind="certificacion"))
    supplier_id = await _empresa(db_session)
    autor = await _usuario(db_session)
    vence = utc_now_naive().replace(microsecond=0) + timedelta(days=365)

    await respuestas.save(
        CapabilityAnswer(
            supplier_id=supplier_id,
            question_id=pregunta.id,
            answered=True,
            answer="Sí",
            answered_at=utc_now_naive(),
            answered_by_user_id=autor,
            valid_until=vence,
        )
    )

    leida = await respuestas.get(supplier_id, pregunta.id)
    assert leida is not None
    assert leida.answered_by_user_id == autor
    assert leida.valid_until == vence


async def test_save_acepta_una_vigencia_con_zona(db_session):
    """Regresión: una fecha con zona llegaba a asyncpg tal cual y la API daba 500."""
    preguntas = SqlCapabilityQuestionRepository(db_session)
    respuestas = SqlCapabilityAnswerRepository(db_session)
    pregunta = await preguntas.add(_pregunta(kind="certificacion"))
    supplier_id = await _empresa(db_session)
    santiago = timezone(timedelta(hours=-3))

    await respuestas.save(
        CapabilityAnswer(
            supplier_id=supplier_id,
            question_id=pregunta.id,
            answered=True,
            answer="Sí",
            valid_until=datetime(2027, 6, 30, 0, 0, tzinfo=santiago),
        )
    )

    leida = await respuestas.get(supplier_id, pregunta.id)
    assert leida is not None
    assert leida.valid_until == datetime(2027, 6, 30, 3, 0)


async def test_save_reemplaza_tambien_quien_respondio_y_la_vigencia(db_session):
    """Otro miembro que corrige la respuesta queda como su autor."""
    preguntas = SqlCapabilityQuestionRepository(db_session)
    respuestas = SqlCapabilityAnswerRepository(db_session)
    pregunta = await preguntas.add(_pregunta(kind="certificacion"))
    supplier_id = await _empresa(db_session)
    primero, segundo = await _usuario(db_session), await _usuario(db_session)

    original = await respuestas.save(
        CapabilityAnswer(
            supplier_id=supplier_id,
            question_id=pregunta.id,
            answered=True,
            answer="Sí",
            answered_by_user_id=primero,
            valid_until=utc_now_naive() + timedelta(days=1),
        )
    )
    await respuestas.save(
        original.model_copy(
            update={"answer": "No", "answered_by_user_id": segundo, "valid_until": None}
        )
    )

    leida = await respuestas.get(supplier_id, pregunta.id)
    assert leida is not None
    assert leida.answer == "No"
    assert leida.answered_by_user_id == segundo
    assert leida.valid_until is None


async def test_la_base_rechaza_un_tipo_de_pregunta_desconocido(db_session):
    now = utc_now_naive()
    db_session.add(
        CapabilityQuestionModel(
            id=uuid4(),
            question="¿Algo?",
            target_field="algo",
            category="general",
            kind="habilidad",
            options=[],
            origin="semilla",
            created_at=now,
            updated_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


def _evidencia(supplier_id: UUID, **kwargs) -> CapabilityEvidence:
    datos = dict(
        supplier_id=supplier_id,
        work_type="obras viales",
        title="Pavimentación calle Los Aromos",
        buyer="Municipalidad de Quilpué",
        year=2024,
        amount_clp=45_000_000,
    )
    datos.update(kwargs)
    return CapabilityEvidence(**datos)


async def test_guarda_y_lista_las_evidencias_de_una_empresa(db_session):
    evidencias = SqlCapabilityEvidenceRepository(db_session)
    supplier_id = await _empresa(db_session)
    otra = await _empresa(db_session)

    guardada = await evidencias.add(_evidencia(supplier_id))
    await evidencias.add(_evidencia(otra, title="Proyecto de otra empresa"))

    assert await evidencias.list_by_supplier(supplier_id) == [guardada]


async def test_una_evidencia_importada_existe_sin_respuesta(db_session):
    evidencias = SqlCapabilityEvidenceRepository(db_session)
    supplier_id = await _empresa(db_session)

    guardada = await evidencias.add(
        _evidencia(supplier_id, origin="mercado_publico", created_by_user_id=None)
    )

    leida = await evidencias.list_by_supplier(supplier_id)
    assert leida == [guardada]
    assert leida[0].answer_id is None
    assert leida[0].origin == "mercado_publico"


async def test_borrar_la_respuesta_deja_la_evidencia_sin_vinculo(db_session):
    """La evidencia es experiencia de la empresa aunque se borre la respuesta."""
    preguntas = SqlCapabilityQuestionRepository(db_session)
    respuestas = SqlCapabilityAnswerRepository(db_session)
    evidencias = SqlCapabilityEvidenceRepository(db_session)
    pregunta = await preguntas.add(
        _pregunta(kind="experiencia_proyecto", work_type="obras viales")
    )
    supplier_id = await _empresa(db_session)
    respuesta = await respuestas.save(
        CapabilityAnswer(
            supplier_id=supplier_id,
            question_id=pregunta.id,
            answered=True,
            answer="Sí",
        )
    )
    await evidencias.add(_evidencia(supplier_id, answer_id=respuesta.id))

    fila = await db_session.get(CapabilityAnswerModel, respuesta.id)
    await db_session.delete(fila)
    await db_session.commit()
    db_session.expunge_all()

    [leida] = await evidencias.list_by_supplier(supplier_id)
    assert leida.answer_id is None
    assert leida.work_type == "obras viales"


async def test_la_base_rechaza_un_origen_de_evidencia_desconocido(db_session):
    supplier_id = await _empresa(db_session)
    db_session.add(
        CapabilityEvidenceModel(
            **_evidencia(supplier_id).model_dump() | {"origin": "linkedin"}
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_la_base_rechaza_un_monto_negativo(db_session):
    supplier_id = await _empresa(db_session)
    db_session.add(
        CapabilityEvidenceModel(
            **_evidencia(supplier_id).model_dump() | {"amount_clp": -1}
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
