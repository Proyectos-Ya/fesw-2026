"""Repositorio de borradores de postulación contra Postgres real (HU-20, B1)."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.proposal import (
    AnalysisDocument,
    DraftContent,
    DraftParagraph,
    DraftSection,
    DraftSource,
    ProposalDraft,
    Requirement,
)
from app.infrastructure.repositories.proposal_model import ProposalDraftModel
from app.infrastructure.repositories.sql_proposal_repository import (
    SqlProposalDraftRepository,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    TenderModel,
)
from app.infrastructure.seeder import seed_database_metadata
from app.shared.datetime_utils import utc_now_naive

pytestmark = pytest.mark.integration

SEC_Q = uuid4()


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


BUYER_RUT = "60.000.000-0"
# "publicada" en la numeración de la API de Compra Ágil (seeder).
PUBLICADA_ID = 2


async def _licitacion(session: AsyncSession) -> UUID:
    """Una licitación con sus FK: regiones, estados y organismo comprador."""
    now = utc_now_naive()
    if await session.get(BuyerInstitutionModel, BUYER_RUT) is None:
        await seed_database_metadata(session)
        session.add(
            BuyerInstitutionModel(
                rut=BUYER_RUT,
                name="Municipalidad de prueba",
                region_id=13,
                created_at=now,
                updated_at=now,
            )
        )
    tender_id = uuid4()
    session.add(
        TenderModel(
            id=tender_id,
            code=f"{uuid4().hex[:8]}-COT26",
            name="Instalación eléctrica",
            status_id=PUBLICADA_ID,
            published_at=now,
            closing_at=now,
            last_change_at=now,
            buyer_rut=BUYER_RUT,
            buyer_unit="Compras",
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    return tender_id


def _borrador(supplier_id: UUID, tender_id: UUID) -> ProposalDraft:
    borrador = ProposalDraft(supplier_id=supplier_id, tender_id=tender_id)
    borrador.load_requirements(
        [
            Requirement(
                id="req-sec",
                text="Deberá contar con certificación SEC.",
                kind="certificacion",
                mandatory=True,
                origin="Descripción",
                capability_question_id=SEC_Q,
            )
        ]
    )
    return borrador


async def test_guarda_y_recupera_el_borrador_de_la_empresa(db_session):
    repo = SqlProposalDraftRepository(db_session)
    supplier_id = await _empresa(db_session)
    tender_id = await _licitacion(db_session)
    borrador = _borrador(supplier_id, tender_id)

    await repo.save(borrador)
    leido = await repo.get(supplier_id, tender_id)

    assert leido == borrador
    assert await repo.get(await _empresa(db_session), tender_id) is None


async def test_save_actualiza_el_mismo_borrador(db_session):
    """Estados, decisiones, advertencias y contenido sobreviven al viaje por JSONB."""
    repo = SqlProposalDraftRepository(db_session)
    supplier_id = await _empresa(db_session)
    tender_id = await _licitacion(db_session)
    borrador = await repo.save(_borrador(supplier_id, tender_id))

    borrador.record_answer(SEC_Q, "negativa")
    borrador.decide("continue", uuid4())
    borrador.mark_ready(
        DraftContent(
            offer_name=DraftSection(
                paragraphs=[
                    DraftParagraph.from_ai_text(
                        "Oferta con [[INSERTAR: plazo]] días.",
                        sources=[DraftSource(id="perfil:descripcion", label="Perfil")],
                    )
                ]
            ),
            offer_description=DraftSection(),
            required_documents=DraftSection(),
        ),
        instructions="Más formal",
    )
    await repo.save(borrador)

    db_session.expunge_all()
    leido = await repo.get(supplier_id, tender_id)
    assert leido is not None
    assert leido.status == "READY"
    assert leido.discrepancy_decisions == borrador.discrepancy_decisions
    assert leido.warnings == borrador.warnings
    assert leido.content == borrador.content
    assert leido.last_instructions == "Más formal"
    assert isinstance(leido.updated_at, datetime)


async def test_un_solo_borrador_por_empresa_y_licitacion(db_session):
    repo = SqlProposalDraftRepository(db_session)
    supplier_id = await _empresa(db_session)
    tender_id = await _licitacion(db_session)
    await repo.save(_borrador(supplier_id, tender_id))

    with pytest.raises(IntegrityError):
        await repo.save(_borrador(supplier_id, tender_id))


async def test_la_base_rechaza_un_estado_desconocido(db_session):
    supplier_id = await _empresa(db_session)
    tender_id = await _licitacion(db_session)
    now = utc_now_naive()
    db_session.add(
        ProposalDraftModel(
            id=uuid4(),
            supplier_id=supplier_id,
            tender_id=tender_id,
            status="EXPIRED",
            requirements=[],
            warnings=[],
            discrepancy_decisions=[],
            created_at=now,
            updated_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_sin_contenido_se_guarda_como_null_de_sql(db_session):
    """Un JSON `null` no lo encuentra `WHERE content IS NULL`."""
    from sqlalchemy import text

    repo = SqlProposalDraftRepository(db_session)
    supplier_id = await _empresa(db_session)
    tender_id = await _licitacion(db_session)
    borrador = await repo.save(_borrador(supplier_id, tender_id))

    fila = (
        await db_session.exec(
            text(
                "SELECT content IS NULL FROM proposal_drafts WHERE id = :id"
            ).bindparams(id=borrador.id)
        )
    ).one()

    assert fila[0] is True


async def test_guarda_y_lee_con_que_adjuntos_se_analizo(db_session):
    """`analysis_documents` y `mentions_attachments` (plan 292, §2.3)."""
    repo = SqlProposalDraftRepository(db_session)
    supplier_id = await _empresa(db_session)
    tender_id = await _licitacion(db_session)
    borrador = _borrador(supplier_id, tender_id)
    borrador.analysis_documents = [
        AnalysisDocument(name="bases.pdf", corrupted=False),
        AnalysisDocument(name="anexo.pdf", corrupted=True),
    ]
    borrador.mentions_attachments = True

    await repo.save(borrador)
    db_session.expunge_all()
    leido = await repo.get(supplier_id, tender_id)

    assert leido is not None
    assert leido.analysis_documents == borrador.analysis_documents
    assert leido.mentions_attachments is True


async def test_un_borrador_anterior_guarda_null_de_sql(db_session):
    """Sin `none_as_null`, None quedaría como el JSON `null`."""
    from sqlalchemy import text

    repo = SqlProposalDraftRepository(db_session)
    supplier_id = await _empresa(db_session)
    tender_id = await _licitacion(db_session)
    borrador = await repo.save(_borrador(supplier_id, tender_id))

    fila = (
        await db_session.exec(
            text(
                "SELECT analysis_documents IS NULL, mentions_attachments IS NULL "
                "FROM proposal_drafts WHERE id = :id"
            ).bindparams(id=borrador.id)
        )
    ).one()

    assert tuple(fila) == (True, True)
