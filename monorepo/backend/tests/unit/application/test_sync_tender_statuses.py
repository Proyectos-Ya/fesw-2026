"""El cron de estados sobrescribe estado y cierre desde el listado de cambios.

Reglas que protege:

- Qdrant guarda solo activas: la que deja de estar activa pierde su punto; la
  que sigue activa recibe el estado y el cierre en el payload.
- La que **vuelve** a estar activa no tiene punto al que escribirle. No se toca
  en SQL: se reencola para que el ingest la reindexe entera (si se la marcara
  activa acá, el ingest vería "sin cambios" y nunca recrearía el punto).
- Qdrant antes que SQL, como en el resto de la ingesta.
- Cada código listado deja un puntero en la cola (plan 305): `nueva` si no lo
  tenemos y sigue abierto, `actualizar` si lo tenemos activo (el SQL decide si
  el cambio es posterior a la última bajada), `reabierta` si vuelve a estar
  activo e `inactiva` si ya no lo está.
- El llamado vigente y el cierre de cada llamado se registran en toda
  licitación conocida (también en una reapertura), en una escritura aparte que
  no mueve `updated_at` y va después de Qdrant y del estado.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.application.repositories.tender_status_sync_repository import (
    ITenderStatusSyncRepository,
)
from app.application.services.lexical_tokenizer import SparseTermVector
from app.application.services.tender_ingestion_queue import ITenderIngestionQueue
from app.application.use_cases.sync_tender_statuses import SyncTenderStatusesUseCase
from app.domain.models.cambio_estado import (
    CambioDeEstado,
    Intencion,
    LicitacionConocida,
    PunteroDeCambio,
    ResultadoPunteros,
)
from app.shared.datetime_utils import to_utc_epoch
from tests.unit.application.fakes import (
    FakeTenderVectorRepository,
    InMemoryLexicalTenderRepository,
    InMemoryTenderItemVectorRepository,
)

PUBLICADA, CERRADA, CANCELADA, DESIERTA = 2, 3, 5, 6
BAJADA = datetime(2026, 9, 28, 10, 0)  # cuándo el ingest bajó el detalle
CIERRE = datetime(2026, 10, 5, 16, 0)


class RepoFalso(ITenderStatusSyncRepository):
    def __init__(self, conocidas: list[LicitacionConocida], log: list[str]) -> None:
        self.conocidas = {c.code: c for c in conocidas}
        self.log = log
        self.estados_creados: list[tuple[int, str]] = []
        self.sobrescritos: list[CambioDeEstado] = []
        self.llamados: list[CambioDeEstado] = []

    async def get_known_by_codes(
        self, codes: list[str]
    ) -> dict[str, LicitacionConocida]:
        return {c: self.conocidas[c] for c in codes if c in self.conocidas}

    async def get_or_create_status(self, status_id: int, code: str) -> int:
        self.estados_creados.append((status_id, code))
        return status_id

    async def overwrite_statuses(self, cambios: list[CambioDeEstado]) -> int:
        self.log.append("sql")
        self.sobrescritos.extend(cambios)
        return len(cambios)

    async def overwrite_call_info(self, cambios: list[CambioDeEstado]) -> int:
        self.log.append("sql-llamado")
        self.llamados.extend(cambios)
        return len(cambios)


class VectorFalso(FakeTenderVectorRepository):
    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self.log = log

    async def delete_many(self, tender_ids: list[UUID]) -> None:
        if tender_ids:
            self.log.append("qdrant")
        await super().delete_many(tender_ids)

    async def set_payloads(self, payloads: dict[UUID, dict]) -> None:
        if payloads:
            self.log.append("qdrant")
        await super().set_payloads(payloads)


class ColaFalsa(ITenderIngestionQueue):
    def __init__(self) -> None:
        self.punteros: list[PunteroDeCambio] = []

    async def reencolar(self, codigos: list[str]) -> int:
        raise AssertionError("el caso de uso deja punteros, no reencola")

    async def registrar_punteros(
        self, punteros: list[PunteroDeCambio]
    ) -> ResultadoPunteros:
        self.punteros.extend(punteros)
        return ResultadoPunteros(
            nuevas=sum(p.intencion is Intencion.NUEVA for p in punteros),
            actualizar=sum(
                p.intencion in (Intencion.ACTUALIZAR_SI_CAMBIO, Intencion.REABIERTA)
                for p in punteros
            ),
            descartadas=sum(p.intencion is Intencion.INACTIVA for p in punteros),
        )

    def intencion(self, code: str) -> Intencion | None:
        return next((p.intencion for p in self.punteros if p.code == code), None)

    @property
    def reencolados(self) -> list[str]:
        """Lo que vuelve a la cola sin condición: las reaperturas."""
        return [p.code for p in self.punteros if p.intencion is Intencion.REABIERTA]


def _conocida(code: str, status_id: int) -> LicitacionConocida:
    return LicitacionConocida(
        id=uuid4(), code=code, status_id=status_id, last_change_at=BAJADA
    )


def _cambio(
    code: str,
    status_id: int,
    status_code: str,
    *,
    closing_at: datetime = CIERRE,
    changed_at: datetime | None = None,
    call_number: int | None = None,
    first_call_closing_at: datetime | None = None,
    second_call_closing_at: datetime | None = None,
) -> CambioDeEstado:
    return CambioDeEstado(
        code=code,
        status_id=status_id,
        status_code=status_code,
        closing_at=closing_at,
        changed_at=changed_at,
        call_number=call_number,
        first_call_closing_at=first_call_closing_at,
        second_call_closing_at=second_call_closing_at,
    )


AHORA = datetime(2026, 10, 1, 12, 0)  # antes de CIERRE: las publicadas siguen abiertas


def _armar(conocidas: list[LicitacionConocida]):
    log: list[str] = []
    repo, vector, cola = RepoFalso(conocidas, log), VectorFalso(log), ColaFalsa()
    caso = SyncTenderStatusesUseCase(
        repository=repo, tender_vector_repo=vector, cola=cola, reloj=lambda: AHORA
    )
    return caso, repo, vector, cola, log


class TestSiguePublicada:
    async def test_plazo_ampliado_actualiza_cierre_en_sql_y_payload(self):
        k = _conocida("A", PUBLICADA)
        caso, repo, vector, _, _ = _armar([k])
        nuevo_cierre = CIERRE + timedelta(days=3)

        resultado = await caso.execute(
            [_cambio("A", PUBLICADA, "publicada", closing_at=nuevo_cierre)]
        )

        assert repo.sobrescritos[0].closing_at == nuevo_cierre
        assert vector.payloads[k.id] == {
            "status_code": "publicada",
            "closing_at": to_utc_epoch(nuevo_cierre),
        }
        assert vector.deleted == []
        assert resultado.actualizadas == 1


class TestDejaDeEstarActiva:
    async def test_desierta_borra_el_punto_y_sobrescribe_sql(self):
        k = _conocida("A", PUBLICADA)
        caso, repo, vector, _, _ = _armar([k])

        resultado = await caso.execute([_cambio("A", DESIERTA, "desierta")])

        assert vector.deleted == [k.id]
        assert k.id not in vector.payloads
        assert [c.status_id for c in repo.sobrescritos] == [DESIERTA]
        assert resultado.sacadas_del_indice == 1

    async def test_cancelada_que_ya_estaba_cerrada_tambien_se_sobrescribe(self):
        k = _conocida("A", CERRADA)
        caso, repo, _, _, _ = _armar([k])

        await caso.execute([_cambio("A", CANCELADA, "cancelada")])

        assert [c.status_id for c in repo.sobrescritos] == [CANCELADA]

    async def test_qdrant_se_escribe_antes_que_sql(self):
        caso, _, _, _, log = _armar([_conocida("A", PUBLICADA)])

        await caso.execute([_cambio("A", CANCELADA, "cancelada")])

        assert log == ["qdrant", "sql"]


class TestVuelveAEstarActiva:
    async def test_no_se_toca_sql_y_se_reencola_para_reindexar(self):
        k = _conocida("A", CERRADA)
        caso, repo, vector, cola, _ = _armar([k])

        resultado = await caso.execute([_cambio("A", PUBLICADA, "publicada")])

        assert repo.sobrescritos == []
        assert vector.payloads == {} and vector.deleted == []
        assert cola.reencolados == ["A"]
        assert resultado.reabiertas == 1


class TestPuntero:
    async def test_una_conocida_activa_queda_para_actualizar_si_cambio(self):
        """Si el cambio es posterior a la última bajada lo decide el SQL."""
        caso, _, _, cola, _ = _armar([_conocida("A", PUBLICADA)])
        cambio = _cambio(
            "A", PUBLICADA, "publicada", changed_at=BAJADA + timedelta(hours=1)
        )

        await caso.execute([cambio])

        assert cola.punteros == [
            PunteroDeCambio(
                code="A",
                status_code="publicada",
                changed_at=BAJADA + timedelta(hours=1),
                intencion=Intencion.ACTUALIZAR_SI_CAMBIO,
            )
        ]

    async def test_una_reapertura_se_reencola_sin_condicion(self):
        caso, _, _, cola, _ = _armar([_conocida("A", CERRADA)])

        await caso.execute([_cambio("A", PUBLICADA, "publicada")])

        assert cola.intencion("A") is Intencion.REABIERTA

    async def test_una_que_deja_de_estar_activa_se_marca_inactiva(self):
        """Si seguía pendiente en la cola, pasa a terminal sin gastar intentos."""
        caso, _, _, cola, _ = _armar([_conocida("A", PUBLICADA)])

        await caso.execute([_cambio("A", DESIERTA, "desierta")])

        assert cola.intencion("A") is Intencion.INACTIVA

    async def test_una_publicada_que_no_tenemos_es_nueva(self):
        caso, repo, vector, cola, _ = _armar([])

        resultado = await caso.execute([_cambio("N", PUBLICADA, "publicada")])

        assert cola.intencion("N") is Intencion.NUEVA
        assert resultado.nuevas == 1
        # No se escribe nada en `tender` ni en Qdrant: la trae la ingesta.
        assert repo.sobrescritos == [] and vector.payloads == {}

    async def test_una_publicada_con_el_cierre_vencido_no_es_nueva(self):
        """Mismo filtro que el listado nocturno: no vale una petición."""
        caso, _, _, cola, _ = _armar([])

        await caso.execute(
            [
                _cambio(
                    "N", PUBLICADA, "publicada", closing_at=AHORA - timedelta(hours=1)
                )
            ]
        )

        assert cola.intencion("N") is Intencion.INACTIVA

    async def test_una_no_activa_que_no_tenemos_queda_inactiva(self):
        caso, _, _, cola, _ = _armar([])

        await caso.execute([_cambio("N", DESIERTA, "desierta")])

        assert cola.intencion("N") is Intencion.INACTIVA

    async def test_el_resultado_suma_lo_que_dejo_la_cola(self):
        caso, _, _, _, _ = _armar([_conocida("A", PUBLICADA), _conocida("B", CERRADA)])

        resultado = await caso.execute(
            [
                _cambio("A", DESIERTA, "desierta"),
                _cambio("B", PUBLICADA, "publicada"),
                _cambio("N", PUBLICADA, "publicada"),
            ]
        )

        assert (resultado.nuevas, resultado.reencoladas, resultado.descartadas) == (
            1,
            1,
            1,
        )


class TestBordes:
    async def test_los_codigos_que_no_tenemos_se_ignoran(self):
        caso, repo, vector, cola, _ = _armar([])

        resultado = await caso.execute([_cambio("NUEVA", PUBLICADA, "publicada")])

        assert repo.sobrescritos == [] and cola.reencolados == []
        assert cola.intencion("NUEVA") is Intencion.NUEVA
        assert vector.payloads == {} and vector.deleted == []
        assert resultado.conocidas == 0

    async def test_lista_vacia_no_escribe_nada(self):
        caso, _, _, _, log = _armar([])

        resultado = await caso.execute([])

        assert log == [] and resultado.conocidas == 0

    async def test_se_registra_cada_estado_una_sola_vez(self):
        """Para ids que el seeder no conoce, como `proveedor_seleccionado`."""
        caso, repo, _, _, _ = _armar(
            [_conocida("A", PUBLICADA), _conocida("B", PUBLICADA)]
        )

        await caso.execute(
            [
                _cambio("A", 9, "proveedor_seleccionado"),
                _cambio("B", 9, "proveedor_seleccionado"),
            ]
        )

        assert repo.estados_creados == [(9, "proveedor_seleccionado")]

    async def test_un_codigo_repetido_se_queda_con_el_cambio_mas_reciente(self):
        """El listado pagina mientras la API cambia: puede repetir un código."""
        caso, repo, _, _, _ = _armar([_conocida("A", PUBLICADA)])
        viejo = _cambio(
            "A", PUBLICADA, "publicada", changed_at=BAJADA + timedelta(hours=1)
        )
        nuevo = _cambio(
            "A", DESIERTA, "desierta", changed_at=BAJADA + timedelta(hours=2)
        )

        await caso.execute([nuevo, viejo])

        assert [c.status_id for c in repo.sobrescritos] == [DESIERTA]


class TestLlamado:
    """El llamado se registra aparte: no mueve `updated_at` y no toca Qdrant."""

    async def test_registra_el_llamado_de_una_que_sigue_publicada(self):
        k = _conocida("A", PUBLICADA)
        caso, repo, vector, _, _ = _armar([k])
        cambio = _cambio(
            "A",
            PUBLICADA,
            "publicada",
            call_number=2,
            second_call_closing_at=CIERRE,
        )

        resultado = await caso.execute([cambio])

        assert repo.llamados == [cambio]
        assert resultado.llamados_actualizados == 1
        # El payload de Qdrant no lleva el llamado: solo estado y cierre.
        assert vector.payloads[k.id] == {
            "status_code": "publicada",
            "closing_at": to_utc_epoch(CIERRE),
        }

    async def test_una_reapertura_registra_el_llamado_sin_tocar_el_estado(self):
        """La reapertura es el caso real del 2.º llamado: `marcar_vencidas` la cerró."""
        k = _conocida("A", CERRADA)
        caso, repo, _, cola, _ = _armar([k])
        cambio = _cambio(
            "A", PUBLICADA, "publicada", call_number=2, second_call_closing_at=CIERRE
        )

        await caso.execute([cambio])

        assert repo.sobrescritos == []
        assert repo.llamados == [cambio]
        assert cola.reencolados == ["A"]

    async def test_una_desierta_en_segundo_llamado_tambien_lo_registra(self):
        k = _conocida("A", PUBLICADA)
        caso, repo, _, _, _ = _armar([k])
        cambio = _cambio(
            "A",
            DESIERTA,
            "desierta",
            call_number=2,
            first_call_closing_at=CIERRE - timedelta(days=1),
            second_call_closing_at=CIERRE,
        )

        await caso.execute([cambio])

        assert repo.llamados == [cambio]
        assert [c.status_id for c in repo.sobrescritos] == [DESIERTA]

    async def test_sin_datos_de_llamado_no_llama_al_repositorio(self):
        caso, repo, _, _, log = _armar([_conocida("A", PUBLICADA)])

        resultado = await caso.execute([_cambio("A", PUBLICADA, "publicada")])

        assert "sql-llamado" not in log
        assert repo.llamados == []
        assert resultado.llamados_actualizados == 0

    async def test_las_desconocidas_no_registran_llamado(self):
        caso, repo, _, _, log = _armar([])

        await caso.execute([_cambio("NUEVA", PUBLICADA, "publicada", call_number=1)])

        assert repo.llamados == []
        assert "sql-llamado" not in log

    async def test_el_llamado_se_escribe_despues_de_qdrant_y_del_estado(self):
        caso, _, _, _, log = _armar([_conocida("A", PUBLICADA)])

        await caso.execute([_cambio("A", CANCELADA, "cancelada", call_number=1)])

        assert log == ["qdrant", "sql", "sql-llamado"]

    async def test_solo_registra_las_que_traen_llamado(self):
        caso, repo, _, _, _ = _armar(
            [_conocida("A", PUBLICADA), _conocida("B", PUBLICADA)]
        )
        con_llamado = _cambio("A", PUBLICADA, "publicada", call_number=1)
        sin_llamado = _cambio("B", PUBLICADA, "publicada")

        await caso.execute([con_llamado, sin_llamado])

        assert repo.llamados == [con_llamado]


class TestLasTresColecciones:
    """Plan 306: al dejar de estar activa, la licitación sale también de
    `tender_items` y `tender_lexical`, no solo de `tenders`."""

    async def test_desierta_sale_de_partidas_y_lexico(self):
        k, otra = _conocida("A", PUBLICADA), _conocida("B", PUBLICADA)
        partidas = InMemoryTenderItemVectorRepository()
        lexico = InMemoryLexicalTenderRepository()
        for i in (k.id, otra.id):
            await partidas.upsert(i, [[1.0, 0.0]], {"status_code": "publicada"})
            await lexico.upsert(i, SparseTermVector(indices=[1], values=[1.0]))
        log: list[str] = []
        caso = SyncTenderStatusesUseCase(
            repository=RepoFalso([k, otra], log),
            tender_vector_repo=VectorFalso(log),
            cola=ColaFalsa(),
            reloj=lambda: AHORA,
            item_vector_repo=partidas,
            lexical_tender_repo=lexico,
        )

        await caso.execute([_cambio("A", DESIERTA, "desierta")])

        assert set(partidas.vectors) == {otra.id}
        assert set(lexico.vectors) == {otra.id}
