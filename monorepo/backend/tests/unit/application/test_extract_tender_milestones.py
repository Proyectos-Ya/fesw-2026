from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.application.services.milestone_extraction_ai_service import ExtractedMilestone
from app.application.use_cases.milestones.extract_tender_milestones import (
    ExtractTenderMilestonesUseCase,
)
from app.application.use_cases.milestones.get_tender_milestones import (
    GetTenderMilestonesUseCase,
)
from app.domain.entities.calendar import CalendarEventLink, CalendarProvider
from app.domain.entities.tender import Tender
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.domain.errors.milestone_errors import MilestoneExtractionUnavailable
from app.domain.errors.tender_errors import TenderNotFound
from tests.unit.application.fakes import (
    InMemoryTenderChatRepository,
    InMemoryTenderRepository,
)
from tests.unit.application.milestone_fakes import (
    FakeMilestoneExtractionAIService,
    InMemoryCalendarEventLinkRepository,
    InMemoryMilestoneDocumentRepository,
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
    def __init__(
        self,
        hitos_ia: list[ExtractedMilestone] | None = None,
        falla_ia: bool = False,
        por_documento: dict[str, list[ExtractedMilestone]] | None = None,
        fallan: set[str] | None = None,
    ):
        self.tender = _licitacion()
        self.tenders = InMemoryTenderRepository()
        self.tenders.tenders[self.tender.id] = self.tender
        self.chat = InMemoryTenderChatRepository()
        self.hitos = InMemoryTenderMilestoneRepository()
        self.enlaces = InMemoryCalendarEventLinkRepository(self.hitos)
        self.procesados = InMemoryMilestoneDocumentRepository()
        self.ia = FakeMilestoneExtractionAIService(
            hitos_ia, falla=falla_ia, por_documento=por_documento, fallan=fallan
        )
        self.use_case = ExtractTenderMilestonesUseCase(
            tenders=self.tenders,
            milestones=self.hitos,
            event_links=self.enlaces,
            chat=self.chat,
            ai=self.ia,
            processed=self.procesados,
            now=lambda: AHORA,
        )
        self.consulta = GetTenderMilestonesUseCase(
            tenders=self.tenders,
            milestones=self.hitos,
            event_links=self.enlaces,
            chat=self.chat,
            processed=self.procesados,
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

    async def guardados(self) -> list[TenderMilestone]:
        return await self.hitos.list_for_tender(USUARIO, self.tender.id)

    async def sincronizar(self, hito: TenderMilestone) -> None:
        await self.enlaces.save(
            CalendarEventLink(
                user_id=USUARIO,
                milestone_id=hito.id,
                provider=CalendarProvider.GOOGLE,
                external_event_id=f"evento-{hito.id}",
                synced_due_at=hito.due_at,
            )
        )


def _de_ia(hitos: list[TenderMilestone]) -> list[TenderMilestone]:
    return [h for h in hitos if h.source is MilestoneSource.IA_DOCUMENTO]


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

    async def test_guarda_los_hitos_de_la_ia_normalizados_y_con_su_documento(self):
        escenario = Escenario([_hito_ia()])
        documento_id = escenario.subir("bases.pdf")

        resultado = await escenario.extraer()

        visita = next(v.milestone for v in resultado.milestones if v.milestone.kind is MilestoneKind.VISITA_TECNICA)
        assert visita.source is MilestoneSource.IA_DOCUMENTO
        assert visita.due_at == datetime(2026, 10, 10, 13, 0)  # 10:00 Chile = 13:00 UTC
        assert visita.has_time is True
        assert visita.source_excerpt == "La visita será el día 10 a las 10:00 horas."
        assert visita.source_document_id == documento_id
        assert len(await escenario.guardados()) == 3

    async def test_cada_documento_se_envia_por_separado(self):
        # Una petición por archivo: más corta, y si uno falla no arrastra al resto.
        escenario = Escenario([_hito_ia()])
        escenario.subir("bases.pdf")
        escenario.subir("anexo.pdf")

        await escenario.extraer()

        assert [[d.document_name for d in docs] for docs, _ in escenario.ia.llamadas] == [
            ["bases.pdf"],
            ["anexo.pdf"],
        ]

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
        # Se informa para que el usuario sepa que tiene que volver a subirlo: en
        # producción el disco del contenedor se borra en cada despliegue.
        assert resultado.unavailable_documents_count == 1
        assert resultado.pending_documents_count == 1

    async def test_con_algunos_archivos_perdidos_extrae_de_los_que_quedan(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir("bases.pdf")
        escenario.subir("anexo-perdido.pdf", contenido=None)

        resultado = await escenario.extraer()

        assert [[d.document_name for d in docs] for docs, _ in escenario.ia.llamadas] == [["bases.pdf"]]
        assert resultado.unavailable_documents_count == 1
        assert len(_de_ia(await escenario.guardados())) == 1

    async def test_si_la_ia_falla_igual_quedan_los_hitos_de_mercado_publico(self):
        escenario = Escenario(falla_ia=True)
        escenario.subir()

        with pytest.raises(MilestoneExtractionUnavailable):
            await escenario.extraer()

        guardados = await escenario.guardados()
        assert {h.kind for h in guardados} == {MilestoneKind.PUBLICACION, MilestoneKind.CIERRE_POSTULACION}

    async def test_si_un_documento_falla_se_procesan_los_otros(self):
        escenario = Escenario([_hito_ia()], fallan={"anexo.pdf"})
        escenario.subir("bases.pdf")
        escenario.subir("anexo.pdf")

        resultado = await escenario.extraer()

        assert resultado.failed_documents_count == 1
        assert resultado.pending_documents_count == 1
        assert len(_de_ia(await escenario.guardados())) == 1

    async def test_un_documento_que_fallo_se_reintenta_en_la_proxima_extraccion(self):
        escenario = Escenario([_hito_ia()], fallan={"bases.pdf"})
        escenario.subir("bases.pdf")
        with pytest.raises(MilestoneExtractionUnavailable):
            await escenario.extraer()

        escenario.ia.fallan = set()
        resultado = await escenario.extraer()

        assert resultado.pending_documents_count == 0
        assert len(_de_ia(await escenario.guardados())) == 1


class TestSinMezclarConLosOficiales:
    async def test_la_ia_no_agrega_publicacion_ni_cierre(self):
        # Ya vienen de Mercado Público: el de la IA aparecía duplicado.
        escenario = Escenario(
            [
                _hito_ia(),
                _hito_ia(kind="cierre_postulacion", title="Cierre de recepción de ofertas", fecha="2026-10-20"),
                _hito_ia(kind="publicacion", title="Publicación", fecha="2026-09-28"),
            ]
        )
        escenario.subir()

        await escenario.extraer()

        guardados = await escenario.guardados()
        assert sorted(h.kind for h in guardados) == sorted(
            [MilestoneKind.PUBLICACION, MilestoneKind.CIERRE_POSTULACION, MilestoneKind.VISITA_TECNICA]
        )
        assert [h.source for h in guardados if h.kind is MilestoneKind.CIERRE_POSTULACION] == [
            MilestoneSource.MERCADO_PUBLICO
        ]

    async def test_consultar_despues_de_extraer_no_cambia_el_origen_de_ninguna_fila(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir()
        await escenario.extraer()
        antes = {h.id: (h.source, h.due_at) for h in await escenario.guardados()}

        await escenario.consulta.execute(USUARIO, escenario.tender.id)
        await escenario.consulta.execute(USUARIO, escenario.tender.id)

        assert {h.id: (h.source, h.due_at) for h in await escenario.guardados()} == antes

    async def test_un_hito_de_ia_con_el_titulo_del_cierre_no_pisa_al_oficial(self):
        # El bug: la fusión no miraba el origen, y un hito de la IA llamado
        # igual que el cierre se quedaba con su id.
        escenario = Escenario()
        oficial = (await escenario.consulta.execute(USUARIO, escenario.tender.id)).milestones[1].milestone
        de_ia = TenderMilestone(
            user_id=USUARIO,
            tender_id=escenario.tender.id,
            kind=MilestoneKind.CIERRE_POSTULACION,
            title="Cierre de recepción de ofertas",
            source=MilestoneSource.IA_DOCUMENTO,
            due_at=datetime(2026, 10, 21, 18, 0),
            has_time=True,
        )
        await escenario.hitos.save_many([de_ia])
        # Sincronizado: no se limpia, así se ve que tampoco se mezcla.
        await escenario.sincronizar(de_ia)

        await escenario.consulta.execute(USUARIO, escenario.tender.id)

        assert escenario.hitos.items[oficial.id].source is MilestoneSource.MERCADO_PUBLICO
        assert escenario.hitos.items[oficial.id].due_at == escenario.tender.closing_at
        assert escenario.hitos.items[de_ia.id].source is MilestoneSource.IA_DOCUMENTO


class TestReextraccion:
    async def test_un_documento_ya_procesado_no_se_vuelve_a_enviar(self):
        escenario = Escenario([_hito_ia()])
        escenario.subir()
        await escenario.extraer()

        resultado = await escenario.extraer()

        assert len(escenario.ia.llamadas) == 1
        assert resultado.pending_documents_count == 0

    async def test_volver_a_extraer_no_duplica_ni_borra(self):
        escenario = Escenario([_hito_ia(), _hito_ia(kind="entrega", title="Entrega de muestras", fecha="2026-10-25")])
        escenario.subir()
        await escenario.extraer()
        antes = sorted(h.id for h in await escenario.guardados())

        # Aunque la IA respondiera otra cosa, el documento ya no se vuelve a leer.
        escenario.ia.hitos = [_hito_ia(title="Visita a terreno")]
        await escenario.extraer()

        assert sorted(h.id for h in await escenario.guardados()) == antes

    async def test_al_subir_otra_base_solo_se_agregan_sus_hitos(self):
        escenario = Escenario(
            por_documento={
                "bases.pdf": [_hito_ia()],
                "aclaracion.pdf": [_hito_ia(kind="consultas", title="Cierre de consultas", fecha="2026-10-05")],
            }
        )
        escenario.subir("bases.pdf")
        await escenario.extraer()
        visita = _de_ia(await escenario.guardados())[0]

        escenario.subir("aclaracion.pdf")
        await escenario.extraer()

        de_ia = _de_ia(await escenario.guardados())
        assert sorted(h.kind for h in de_ia) == sorted([MilestoneKind.VISITA_TECNICA, MilestoneKind.CONSULTAS])
        assert visita in de_ia
        assert [[d.document_name for d in docs] for docs, _ in escenario.ia.llamadas][-1] == ["aclaracion.pdf"]

    async def test_la_ia_repite_un_hito_en_el_mismo_documento_y_queda_uno(self):
        escenario = Escenario([_hito_ia(), _hito_ia(title="Visita a terreno obligatoria", hora="11:00")])
        escenario.subir()

        await escenario.extraer()

        assert len(_de_ia(await escenario.guardados())) == 1

    async def test_un_titulo_distinto_el_mismo_dia_actualiza_la_fila_existente(self):
        # Hitos guardados antes de este cambio: el documento no figura como
        # procesado y se vuelve a leer una vez; no debe duplicar.
        escenario = Escenario([_hito_ia(title="Visita a terreno")])
        documento_id = escenario.subir()
        previo = TenderMilestone(
            user_id=USUARIO,
            tender_id=escenario.tender.id,
            kind=MilestoneKind.VISITA_TECNICA,
            title="Visita técnica obligatoria",
            source=MilestoneSource.IA_DOCUMENTO,
            source_document_id=documento_id,
            due_at=datetime(2026, 10, 10, 13, 0),
            has_time=True,
        )
        await escenario.hitos.save_many([previo])

        await escenario.extraer()

        de_ia = _de_ia(await escenario.guardados())
        assert [h.id for h in de_ia] == [previo.id]
        assert de_ia[0].title == "Visita a terreno"

    async def test_al_borrar_un_documento_se_van_sus_hitos_salvo_los_sincronizados(self):
        escenario = Escenario(
            por_documento={
                "bases.pdf": [_hito_ia()],
                "anexo.pdf": [
                    _hito_ia(kind="entrega", title="Entrega", fecha="2026-10-25"),
                    _hito_ia(kind="consultas", title="Consultas", fecha="2026-10-05"),
                ],
            }
        )
        escenario.subir("bases.pdf")
        anexo = escenario.subir("anexo.pdf")
        await escenario.extraer()
        entrega = next(h for h in await escenario.guardados() if h.kind is MilestoneKind.ENTREGA)
        await escenario.sincronizar(entrega)

        del escenario.chat.documents[anexo]
        await escenario.consulta.execute(USUARIO, escenario.tender.id)

        tipos = sorted(h.kind for h in _de_ia(await escenario.guardados()))
        assert tipos == sorted([MilestoneKind.VISITA_TECNICA, MilestoneKind.ENTREGA])


class TestReparacionDeDatosPrevios:
    async def test_borra_filas_oficiales_duplicadas_por_el_bug(self):
        escenario = Escenario()
        await escenario.consulta.execute(USUARIO, escenario.tender.id)
        cierre = next(h for h in await escenario.guardados() if h.kind is MilestoneKind.CIERRE_POSTULACION)
        await escenario.hitos.save_many([cierre.model_copy(update={"id": uuid4()})])

        await escenario.consulta.execute(USUARIO, escenario.tender.id)

        cierres = [h for h in await escenario.guardados() if h.kind is MilestoneKind.CIERRE_POSTULACION]
        assert len(cierres) == 1

    async def test_conserva_la_fila_oficial_sincronizada_al_reparar(self):
        escenario = Escenario()
        await escenario.consulta.execute(USUARIO, escenario.tender.id)
        cierre = next(h for h in await escenario.guardados() if h.kind is MilestoneKind.CIERRE_POSTULACION)
        copia = cierre.model_copy(update={"id": uuid4()})
        await escenario.hitos.save_many([copia])
        await escenario.sincronizar(copia)

        await escenario.consulta.execute(USUARIO, escenario.tender.id)

        cierres = [h for h in await escenario.guardados() if h.kind is MilestoneKind.CIERRE_POSTULACION]
        assert [h.id for h in cierres] == [copia.id]

    async def test_borra_cierres_o_publicaciones_que_la_ia_habia_agregado(self):
        escenario = Escenario()
        documento_id = escenario.subir()
        await escenario.hitos.save_many(
            [
                TenderMilestone(
                    user_id=USUARIO,
                    tender_id=escenario.tender.id,
                    kind=MilestoneKind.CIERRE_POSTULACION,
                    title="Cierre de ofertas",
                    source=MilestoneSource.IA_DOCUMENTO,
                    source_document_id=documento_id,
                    due_at=datetime(2026, 10, 20, 18, 0),
                    has_time=True,
                )
            ]
        )

        await escenario.consulta.execute(USUARIO, escenario.tender.id)

        assert _de_ia(await escenario.guardados()) == []
