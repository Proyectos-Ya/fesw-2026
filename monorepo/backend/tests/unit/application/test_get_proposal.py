"""Lectura del borrador con su vencimiento calculado al leer (HU-20, B2)."""

from uuid import uuid4

import pytest

from app.application.use_cases.proposals.get_proposal import GetProposalUseCase
from app.domain.entities.proposal import ProposalDraft
from app.domain.entities.supplier import Supplier
from app.domain.errors.proposal_errors import ProposalDraftNotFound
from app.domain.errors.tender_errors import TenderNotFound
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.fakes import (
    InMemoryProposalDraftRepository,
    InMemorySupplierRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.test_score_tender_on_demand import crear_licitacion


async def _escenario(status_code: str = TENDER_STATUSES["PUBLISHED"]):
    suppliers = InMemorySupplierRepository()
    tenders = InMemoryTenderRepository()
    drafts = InMemoryProposalDraftRepository()
    user_id, tender_id = uuid4(), uuid4()
    empresa = await suppliers.save(
        Supplier(user_id=user_id, rut="76086428-5", legal_name="Andes SpA")
    )
    tenders.tenders[tender_id] = crear_licitacion(tender_id, status_code=status_code)
    caso = GetProposalUseCase(suppliers, tenders, drafts)
    return caso, drafts, user_id, empresa, tender_id


async def test_devuelve_el_borrador_de_la_empresa_activa():
    caso, drafts, user_id, empresa, tender_id = await _escenario()
    borrador = await drafts.save(
        ProposalDraft(supplier_id=empresa.id, tender_id=tender_id)
    )

    vista = await caso.execute(user_id, empresa.id, tender_id)

    assert vista.id == borrador.id
    assert vista.is_expired is False


async def test_un_borrador_de_una_licitacion_cerrada_se_marca_vencido():
    caso, drafts, user_id, empresa, tender_id = await _escenario(
        TENDER_STATUSES["CLOSED"]
    )
    await drafts.save(ProposalDraft(supplier_id=empresa.id, tender_id=tender_id))

    vista = await caso.execute(user_id, empresa.id, tender_id)

    assert vista.is_expired is True
    assert vista.status == "FEASIBILITY"


async def test_sin_borrador_es_no_encontrado():
    caso, _, user_id, empresa, tender_id = await _escenario()

    with pytest.raises(ProposalDraftNotFound):
        await caso.execute(user_id, empresa.id, tender_id)


async def test_licitacion_inexistente():
    caso, _, user_id, empresa, _ = await _escenario()

    with pytest.raises(TenderNotFound):
        await caso.execute(user_id, empresa.id, uuid4())
