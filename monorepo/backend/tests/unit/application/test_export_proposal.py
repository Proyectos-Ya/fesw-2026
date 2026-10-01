"""Exportar el borrador a Word (HU-20, B6, CA3)."""

from io import BytesIO

import pytest
from docx import Document

from app.application.use_cases.proposals.export_proposal import (
    ExportProposalDocxUseCase,
)
from app.domain.errors.proposal_errors import (
    InvalidProposalTransition,
    ProposalDraftNotFound,
)
from app.infrastructure.services.docx_proposal_exporter import DocxProposalExporter
from app.shared.constants import TENDER_STATUSES
from tests.unit.application.test_generate_proposal import Escenario
from tests.unit.application.test_score_tender_on_demand import crear_licitacion


def _caso(e: Escenario) -> ExportProposalDocxUseCase:
    return ExportProposalDocxUseCase(
        e.suppliers, e.tenders, e.drafts, DocxProposalExporter()
    )


async def _exportar(e: Escenario):
    return await _caso(e).execute(
        user_id=e.user_id, supplier_id=e.empresa.id, tender_id=e.tender_id
    )


async def test_exporta_el_borrador_redactado_con_nombre_de_archivo():
    e = await Escenario().preparar()
    await e.redactar()

    archivo = await _exportar(e)

    assert archivo.filename == f"postulacion-COT-{e.tender_id}.docx"
    documento = Document(BytesIO(archivo.content))
    assert documento.paragraphs[0].text == "Capacitación PAC en Coyhaique"


async def test_un_borrador_sin_redactar_no_se_exporta():
    e = await Escenario().preparar()

    with pytest.raises(InvalidProposalTransition):
        await _exportar(e)


async def test_con_la_licitacion_cerrada_se_sigue_exportando():
    """Exportar es leer: lo redactado se puede descargar aunque ya no se postule."""
    e = await Escenario().preparar()
    await e.redactar()
    e.tenders.tenders[e.tender_id] = crear_licitacion(
        e.tender_id, status_code=TENDER_STATUSES["CLOSED"]
    )

    archivo = await _exportar(e)

    assert archivo.content


async def test_sin_borrador():
    e = await Escenario().preparar()
    e.drafts.filas.clear()

    with pytest.raises(ProposalDraftNotFound):
        await _exportar(e)


async def test_el_nombre_de_archivo_no_lleva_caracteres_peligrosos():
    e = await Escenario().preparar()
    await e.redactar()
    tender = e.tenders.tenders[e.tender_id]
    tender.code = 'a/b\\c"d 1057-COT26'

    archivo = await _exportar(e)

    assert archivo.filename == "postulacion-a-b-c-d-1057-COT26.docx"
