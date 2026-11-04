"""Refrescar la lista oficial de anexos con lo que los crons ya listaron.

No gasta cuota: la lista sale del mismo listado que los crons piden de todos
modos. Lo que hay que proteger es qué se escribe y qué no: solo las licitaciones
que ya tenemos (la clave foránea no deja guardar las demás), y una lista vacía es
una respuesta ("Mercado Público no informa anexos"), no una ausencia.
"""

from datetime import datetime, timedelta
from uuid import uuid4

from app.application.use_cases.tender_attachments.sync_official_attachments import (
    SyncOfficialAttachmentsUseCase,
    listas_desde_cambios,
)
from app.domain.models.cambio_estado import CambioDeEstado
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from tests.unit.application.attachment_fakes import InMemoryTenderAttachmentRepository

DOC1 = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")
DOC2 = DocumentoOficialDTO(mp_document_id=2, nombre="Anexo 1.docx")


class TestSyncOfficialAttachmentsUseCase:
    async def test_solo_aplica_las_conocidas(self):
        id_a = uuid4()
        repo = InMemoryTenderAttachmentRepository({"A": id_a})

        aplicadas = await SyncOfficialAttachmentsUseCase(repo).execute(
            {"A": [DOC1], "X": [DOC2]}
        )

        assert aplicadas == 1
        assert repo.llamadas[0][0] == {id_a: [DOC1]}
        # Naive en UTC, como todo lo que se persiste.
        assert repo.llamadas[0][1].tzinfo is None

    async def test_sin_listas_no_hace_nada(self):
        repo = InMemoryTenderAttachmentRepository({"A": uuid4()})

        assert await SyncOfficialAttachmentsUseCase(repo).execute({}) == 0
        assert repo.llamadas == []

    async def test_ninguna_conocida_no_escribe(self):
        repo = InMemoryTenderAttachmentRepository({"A": uuid4()})

        assert await SyncOfficialAttachmentsUseCase(repo).execute({"X": [DOC1]}) == 0
        assert repo.llamadas == []

    async def test_una_lista_vacia_retira_lo_que_habia(self):
        id_a = uuid4()
        repo = InMemoryTenderAttachmentRepository({"A": id_a})
        caso = SyncOfficialAttachmentsUseCase(repo)

        await caso.execute({"A": [DOC1]})
        await caso.execute({"A": []})

        lista = await repo.get_official_list(id_a)
        assert lista is not None
        assert lista.attachments == []
        assert lista.synced_at is not None


def _cambio(code: str, documentos, changed_at: datetime | None = None) -> CambioDeEstado:
    return CambioDeEstado(
        code=code,
        status_id=2,
        status_code="publicada",
        closing_at=datetime(2026, 10, 1, 12, 0),
        changed_at=changed_at,
        documentos=documentos,
    )


class TestListasDesdeCambios:
    def test_ignora_los_cambios_sin_lista(self):
        listas = listas_desde_cambios([_cambio("A", None), _cambio("B", (DOC1,))])

        assert listas == {"B": [DOC1]}

    def test_un_codigo_repetido_se_queda_con_el_cambio_mas_reciente(self):
        t0 = datetime(2026, 10, 1, 10, 0)
        listas = listas_desde_cambios(
            [
                _cambio("A", (DOC1,), t0),
                _cambio("A", (DOC2,), t0 + timedelta(minutes=5)),
                _cambio("A", (DOC1,), t0 - timedelta(minutes=5)),
            ]
        )

        assert listas == {"A": [DOC2]}

    def test_sin_fecha_de_cambio_cuenta_como_el_mas_viejo(self):
        listas = listas_desde_cambios(
            [
                _cambio("A", (DOC1,), datetime(2026, 10, 1, 10, 0)),
                _cambio("A", (DOC2,), None),
            ]
        )

        assert listas == {"A": [DOC1]}

    def test_con_empate_gana_el_primero(self):
        t0 = datetime(2026, 10, 1, 10, 0)
        listas = listas_desde_cambios(
            [_cambio("A", (DOC1,), t0), _cambio("A", (DOC2,), t0)]
        )

        assert listas == {"A": [DOC1]}

    def test_sin_fechas_tambien_gana_el_primero(self):
        listas = listas_desde_cambios([_cambio("A", (DOC1,)), _cambio("A", (DOC2,))])

        assert listas == {"A": [DOC1]}

    def test_convierte_la_tupla_en_lista_y_conserva_la_vacia(self):
        listas = listas_desde_cambios([_cambio("A", (DOC1, DOC2)), _cambio("B", ())])

        assert listas == {"A": [DOC1, DOC2], "B": []}
        assert isinstance(listas["A"], list)
