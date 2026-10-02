"""El cron de estados sobrescribe estado y cierre desde el listado de cambios.

Reglas que protege:

- Qdrant guarda solo activas: la que deja de estar activa pierde su punto; la
  que sigue activa recibe el estado y el cierre en el payload.
- La que **vuelve** a estar activa no tiene punto al que escribirle. No se toca
  en SQL: se reencola para que el ingest la reindexe entera (si se la marcara
  activa acá, el ingest vería "sin cambios" y nunca recrearía el punto).
- Qdrant antes que SQL, como en el resto de la ingesta.
- Las publicadas que cambiaron después de la última bajada de su detalle se
  reencolan, para que `_actualizar` decida si cambió el texto.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.application.repositories.tender_status_sync_repository import (
    ITenderStatusSyncRepository,
)
from app.application.services.tender_ingestion_queue import ITenderIngestionQueue
from app.application.use_cases.sync_tender_statuses import SyncTenderStatusesUseCase
from app.domain.models.cambio_estado import CambioDeEstado, LicitacionConocida
from app.shared.datetime_utils import to_utc_epoch
from tests.unit.application.fakes import FakeTenderVectorRepository

PUBLICADA, CERRADA, CANCELADA, DESIERTA = 2, 3, 5, 6
BAJADA = datetime(2026, 9, 28, 10, 0)  # cuándo el ingest bajó el detalle
CIERRE = datetime(2026, 10, 5, 16, 0)


class RepoFalso(ITenderStatusSyncRepository):
    def __init__(self, conocidas: list[LicitacionConocida], log: list[str]) -> None:
        self.conocidas = {c.code: c for c in conocidas}
        self.log = log
        self.estados_creados: list[tuple[int, str]] = []
        self.sobrescritos: list[CambioDeEstado] = []

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
        self.reencolados: list[str] = []

    async def reencolar(self, codigos: list[str]) -> int:
        self.reencolados.extend(codigos)
        return len(codigos)


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
) -> CambioDeEstado:
    return CambioDeEstado(
        code=code,
        status_id=status_id,
        status_code=status_code,
        closing_at=closing_at,
        changed_at=changed_at,
    )


def _armar(conocidas: list[LicitacionConocida]):
    log: list[str] = []
    repo, vector, cola = RepoFalso(conocidas, log), VectorFalso(log), ColaFalsa()
    caso = SyncTenderStatusesUseCase(
        repository=repo, tender_vector_repo=vector, cola=cola
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


class TestReencolado:
    async def test_publicada_con_cambio_posterior_a_la_bajada_se_reencola(self):
        caso, _, _, cola, _ = _armar([_conocida("A", PUBLICADA)])

        await caso.execute(
            [
                _cambio(
                    "A", PUBLICADA, "publicada", changed_at=BAJADA + timedelta(hours=1)
                )
            ]
        )

        assert cola.reencolados == ["A"]

    async def test_cambio_anterior_a_la_bajada_no_se_reencola(self):
        """Ya se bajó el detalle después de ese cambio (o es el mismo)."""
        caso, _, _, cola, _ = _armar([_conocida("A", PUBLICADA)])

        await caso.execute([_cambio("A", PUBLICADA, "publicada", changed_at=BAJADA)])

        assert cola.reencolados == []

    async def test_sin_fecha_de_cambio_no_se_reencola(self):
        caso, _, _, cola, _ = _armar([_conocida("A", PUBLICADA)])

        await caso.execute([_cambio("A", PUBLICADA, "publicada", changed_at=None)])

        assert cola.reencolados == []

    async def test_las_no_activas_no_se_reencolan(self):
        """Su contenido ya no se muestra ni se recomienda: no vale una petición."""
        caso, _, _, cola, _ = _armar([_conocida("A", PUBLICADA)])

        await caso.execute(
            [_cambio("A", DESIERTA, "desierta", changed_at=BAJADA + timedelta(hours=1))]
        )

        assert cola.reencolados == []


class TestBordes:
    async def test_los_codigos_que_no_tenemos_se_ignoran(self):
        caso, repo, vector, cola, _ = _armar([])

        resultado = await caso.execute([_cambio("NUEVA", PUBLICADA, "publicada")])

        assert repo.sobrescritos == [] and cola.reencolados == []
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
