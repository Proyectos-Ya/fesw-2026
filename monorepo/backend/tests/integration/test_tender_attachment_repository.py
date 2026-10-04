"""La lista oficial de anexos contra una base real (plan 233, decisión 1).

Lo que hay que proteger:

- el upsert conserva el `id` y `first_seen_at` de lo que ya existía, porque la
  subida (decisión 2) colgará archivos de esas filas;
- lo que Mercado Público retira se **marca**, no se borra, y reaparece con su id;
- `tender.updated_at` no se mueve nunca: dispara la regeneración del análisis de
  Gemini. Solo se escribe `attachments_synced_at`.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.infrastructure.repositories.sql_tender_attachment_repository import (
    SqlTenderAttachmentRepository,
)
from app.infrastructure.repositories.tender_attachment_model import (
    TenderAttachmentModel,
)
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderModel,
    TenderStatusModel,
)
from app.shared.regions import CHILE_REGIONS

pytestmark = pytest.mark.asyncio

PUBLICADA = 2
ANTES = datetime(2026, 9, 1, 12, 0)
CIERRE = datetime(2026, 10, 5, 16, 0)
T1 = datetime(2026, 9, 28, 16, 0)
T2 = T1 + timedelta(hours=1)
T3 = T1 + timedelta(hours=2)

BASES = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")
ANEXO = DocumentoOficialDTO(mp_document_id=2, nombre="Anexo 1.docx")


async def _base(session: AsyncSession) -> None:
    session.add(RegionModel(id=13, name=CHILE_REGIONS[13]))
    session.add(TenderStatusModel(id=PUBLICADA, code="publicada", name="Publicada"))
    session.add(
        BuyerInstitutionModel(
            rut="61.000.000-0",
            name="Municipalidad",
            region_id=13,
            created_at=ANTES,
            updated_at=ANTES,
        )
    )
    await session.commit()


async def _tender(session: AsyncSession, code: str) -> UUID:
    tender_id = uuid4()
    session.add(
        TenderModel(
            id=tender_id,
            code=code,
            name=f"Licitación {code}",
            description=None,
            status_id=PUBLICADA,
            published_at=ANTES,
            closing_at=CIERRE,
            last_change_at=ANTES,
            buyer_rut="61.000.000-0",
            buyer_unit="Abastecimiento",
            available_amount_clp=100.0,
            created_at=ANTES,
            updated_at=ANTES,
        )
    )
    await session.commit()
    return tender_id


async def _filas(session: AsyncSession, tender_id: UUID) -> list[TenderAttachmentModel]:
    """Todas las filas de la licitación, incluidas las retiradas."""
    session.expire_all()
    resultado = await session.exec(
        select(TenderAttachmentModel)
        .where(col(TenderAttachmentModel.tender_id) == tender_id)
        .order_by(col(TenderAttachmentModel.mp_document_id))
    )
    return list(resultado.all())


async def test_inserta_la_lista_y_marca_la_sincronizacion(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    sincronizadas = await repo.sync_official_lists(
        {
            tender_id: [
                BASES,
                DocumentoOficialDTO(
                    mp_document_id=2, nombre="Anexo 3 Composición personalidad.XLSX"
                ),
            ]
        },
        visto_en=T1,
    )

    lista = await repo.get_official_list(tender_id)
    assert sincronizadas == 1
    assert lista is not None
    assert lista.synced_at == T1
    assert [a.mp_document_id for a in lista.attachments] == [1, 2]
    primero, segundo = lista.attachments
    assert (primero.name, primero.ext, primero.name_normalized) == (
        "Bases.pdf",
        "pdf",
        "bases.pdf",
    )
    assert (segundo.ext, segundo.name_normalized) == (
        "xlsx",
        "anexo 3 composicion personalidad.xlsx",
    )
    assert primero.first_seen_at == primero.last_seen_at == T1
    assert primero.removed_at is None


async def test_repetir_la_misma_lista_es_idempotente(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T1)
    ids = {f.mp_document_id: f.id for f in await _filas(db_session, tender_id)}
    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T2)

    filas = await _filas(db_session, tender_id)
    assert len(filas) == 2
    assert {f.mp_document_id: f.id for f in filas} == ids
    assert all(f.first_seen_at == T1 and f.last_seen_at == T2 for f in filas)


async def test_un_nombre_nuevo_actualiza_la_fila_sin_cambiar_su_id(
    db_session: AsyncSession,
):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists({tender_id: [BASES]}, visto_en=T1)
    id_original = (await _filas(db_session, tender_id))[0].id
    renombrado = DocumentoOficialDTO(mp_document_id=1, nombre="Bases definitivas.docx")
    await repo.sync_official_lists({tender_id: [renombrado]}, visto_en=T2)

    (fila,) = await _filas(db_session, tender_id)
    assert fila.id == id_original
    assert (fila.name, fila.ext, fila.name_normalized) == (
        "Bases definitivas.docx",
        "docx",
        "bases definitivas.docx",
    )


async def test_el_que_no_viene_queda_retirado_sin_borrarse(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T1)
    await repo.sync_official_lists({tender_id: [BASES]}, visto_en=T2)

    lista = await repo.get_official_list(tender_id)
    assert lista is not None
    assert [a.mp_document_id for a in lista.attachments] == [1]
    retirada = (await _filas(db_session, tender_id))[1]
    assert retirada.mp_document_id == 2
    assert retirada.removed_at == T2


async def test_el_retirado_que_reaparece_revive_con_su_id(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T1)
    id_anexo = (await _filas(db_session, tender_id))[1].id
    await repo.sync_official_lists({tender_id: [BASES]}, visto_en=T2)
    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T3)

    anexo = (await _filas(db_session, tender_id))[1]
    assert anexo.removed_at is None
    assert anexo.id == id_anexo
    assert anexo.first_seen_at == T1
    assert anexo.last_seen_at == T3


async def test_una_lista_vacia_retira_todo_y_marca_sincronizada(
    db_session: AsyncSession,
):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T1)
    await repo.sync_official_lists({tender_id: []}, visto_en=T2)

    lista = await repo.get_official_list(tender_id)
    assert lista is not None
    assert lista.attachments == []
    assert lista.synced_at == T2
    assert all(f.removed_at == T2 for f in await _filas(db_session, tender_id))


async def test_no_mueve_updated_at_de_la_licitacion(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists({tender_id: [BASES]}, visto_en=T1)

    db_session.expire_all()
    tender = await db_session.get(TenderModel, tender_id)
    assert tender is not None
    assert tender.updated_at == ANTES
    assert tender.attachments_synced_at == T1


async def test_la_lista_de_una_licitacion_no_retira_las_de_otra(
    db_session: AsyncSession,
):
    await _base(db_session)
    id_a = await _tender(db_session, "A")
    id_b = await _tender(db_session, "B")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists({id_a: [BASES]}, visto_en=T1)
    await repo.sync_official_lists({id_b: [ANEXO]}, visto_en=T2)

    (fila_a,) = await _filas(db_session, id_a)
    assert fila_a.removed_at is None


async def test_ids_por_codigo(db_session: AsyncSession):
    await _base(db_session)
    id_a = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    assert await repo.get_tender_ids_by_codes(["A", "X"]) == {"A": id_a}
    assert await repo.get_tender_ids_by_codes([]) == {}


async def test_licitacion_inexistente_devuelve_none(db_session: AsyncSession):
    await _base(db_session)

    repo = SqlTenderAttachmentRepository(db_session)

    assert await repo.get_official_list(uuid4()) is None


async def test_licitacion_sin_sincronizar_devuelve_lista_vacia_sin_fecha(
    db_session: AsyncSession,
):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")

    lista = await SqlTenderAttachmentRepository(db_session).get_official_list(tender_id)

    assert lista is not None
    assert lista.attachments == []
    assert lista.synced_at is None


async def test_un_id_repetido_en_la_misma_lista_no_falla(db_session: AsyncSession):
    """Dos filas con la misma clave harían fallar el ON CONFLICT entero
    (`CardinalityViolation`)."""
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)

    await repo.sync_official_lists(
        {
            tender_id: [
                DocumentoOficialDTO(mp_document_id=1, nombre="a.pdf"),
                DocumentoOficialDTO(mp_document_id=1, nombre="b.pdf"),
            ]
        },
        visto_en=T1,
    )

    assert len(await _filas(db_session, tender_id)) == 1


async def test_get_official_attachment_devuelve_la_fila_vigente(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)
    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T1)
    lista = await repo.get_official_list(tender_id)
    assert lista is not None
    anexo = lista.attachments[1]

    encontrado = await repo.get_official_attachment(tender_id, anexo.id)

    assert encontrado == anexo


async def test_get_official_attachment_de_otra_licitacion_es_none(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    otra = await _tender(db_session, "B")
    repo = SqlTenderAttachmentRepository(db_session)
    await repo.sync_official_lists({tender_id: [BASES]}, visto_en=T1)
    lista = await repo.get_official_list(tender_id)
    assert lista is not None

    assert await repo.get_official_attachment(otra, lista.attachments[0].id) is None
    assert await repo.get_official_attachment(tender_id, uuid4()) is None


async def test_get_official_attachment_retirado_es_none(db_session: AsyncSession):
    await _base(db_session)
    tender_id = await _tender(db_session, "A")
    repo = SqlTenderAttachmentRepository(db_session)
    await repo.sync_official_lists({tender_id: [BASES, ANEXO]}, visto_en=T1)
    lista = await repo.get_official_list(tender_id)
    assert lista is not None
    anexo = lista.attachments[1]
    await repo.sync_official_lists({tender_id: [BASES]}, visto_en=T2)

    assert await repo.get_official_attachment(tender_id, anexo.id) is None
