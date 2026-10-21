"""La conexión que arman los scripts de ingesta.

En Railway la base se alcanza por el pooler de Supabase en modo transacción, que
no soporta sentencias preparadas. La API lo resuelve en `app/infrastructure/db.py`
con `DB_DISABLE_PREPARED_STATEMENTS`; el cron armaba su propio engine sin esos
ajustes y fallaba de forma intermitente con `prepared statement ... does not
exist` (primera corrida en `dev test`, 16-sep-2026). En local no se ve porque
ahí la conexión es directa.
"""

import app.bootstrap.builders
import app.infrastructure.db as db
from app.config import settings
from scripts.ingesta_compartida import construir_servicio


def _capturar_engine(monkeypatch) -> list[dict]:
    llamadas: list[dict] = []
    original = db.create_async_engine

    def espia(url, **kwargs):
        llamadas.append(kwargs)
        return original(url, **kwargs)

    monkeypatch.setattr(db, "create_async_engine", espia)
    monkeypatch.setattr(
        app.bootstrap.builders, "build_embedding_service", lambda: object()
    )
    return llamadas


def test_detras_del_pooler_el_cron_no_usa_sentencias_preparadas(monkeypatch):
    monkeypatch.setattr(settings, "db_disable_prepared_statements", True)
    llamadas = _capturar_engine(monkeypatch)

    construir_servicio()

    assert len(llamadas) == 1
    assert llamadas[0]["connect_args"] == {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }


def test_con_conexion_directa_se_dejan_las_de_asyncpg(monkeypatch):
    monkeypatch.setattr(settings, "db_disable_prepared_statements", False)
    llamadas = _capturar_engine(monkeypatch)

    construir_servicio()

    assert llamadas[0]["connect_args"] == {}


class _ColaFalsa:
    """Servicio que procesa, en cada pasada, lo que dicta el guion."""

    def __init__(self, pendientes: int, guion: list[tuple[int, int]]) -> None:
        self.pendientes = pendientes
        self.guion = list(guion)
        self.pasadas = 0

    async def process_unprocessed_tenders(self, limite=None, **_):
        from app.infrastructure.services.tenders.tender_ingestion_service import (
            ResultadoProceso,
        )

        procesadas, fallidas = self.guion[min(self.pasadas, len(self.guion) - 1)]
        self.pasadas += 1
        self.pendientes -= procesadas
        return ResultadoProceso(procesadas=procesadas, fallidas=fallidas)

    async def contar(self) -> int:
        return self.pendientes


class TestVaciarCola:
    """Con Mercado Público caído, alguna licitación entra de vez en cuando.

    Segunda corrida en `dev test` (17-sep-2026): 19 pendientes en 504, y cada
    tanto entraban 1 o 2. Como cualquier avance reiniciaba el contador de rondas
    sin avance, el vaciado insistió ~45 minutos sin sacar casi nada.
    """

    async def test_un_goteo_cuenta_como_ronda_sin_avance(self):
        from scripts.ingesta_compartida import RONDAS_SIN_AVANCE_MAX, vaciar_cola

        cola = _ColaFalsa(pendientes=19, guion=[(1, 18)])

        resultado = await vaciar_cola(cola, cola.contar, verboso=False)  # type: ignore[arg-type]

        assert resultado.sin_avance is True
        assert cola.pasadas == RONDAS_SIN_AVANCE_MAX
        assert resultado.procesadas == RONDAS_SIN_AVANCE_MAX
        assert resultado.pendientes == 19 - RONDAS_SIN_AVANCE_MAX

    async def test_una_cola_grande_que_avanza_no_se_corta(self):
        from scripts.ingesta_compartida import vaciar_cola

        # Lotes de 200 con 180 éxitos: avanza un 4 % de la cola por ronda, pero
        # el 90 % de lo que intenta.
        cola = _ColaFalsa(pendientes=900, guion=[(180, 20)] * 5)

        resultado = await vaciar_cola(cola, cola.contar, verboso=False)  # type: ignore[arg-type]

        assert resultado.sin_avance is False
        assert resultado.pendientes == 0
        assert resultado.procesadas == 900


class TestEmbeddingsContados:
    """Plan 305: cada corrida guarda cuántas veces llamó a la API de embeddings.

    Con los vectores por partida, cada licitación nueva cuesta dos llamadas y
    unos cuatro textos en vez de uno. Sin contarlo no se ve cuánto suma.
    """

    async def test_cuenta_llamadas_y_textos_y_delega(self):
        from scripts.ingesta_compartida import EmbeddingsContados

        class Interno:
            async def embed(self, textos):
                return [[0.0] for _ in textos]

        contados = EmbeddingsContados(Interno())  # type: ignore[arg-type]

        await contados.embed(["a", "b"])
        vectores = await contados.embed(["c"])

        assert (contados.llamadas, contados.textos) == (2, 3)
        assert vectores == [[0.0]]


class TestConcurrenciaDelListado:
    """Los crons piden el listado de a 6 páginas (plan 305), configurable."""

    def test_por_defecto_es_6(self):
        from app.config import Settings

        assert Settings.model_fields["mercadopublico_listing_concurrency"].default == 6

    def test_construir_servicio_la_pasa_al_cliente(self, monkeypatch):
        from app.config import settings
        from scripts import ingesta_compartida

        monkeypatch.setattr(settings, "mercadopublico_listing_concurrency", 4)
        monkeypatch.setattr(ingesta_compartida, "crear_engine", lambda: None)

        servicio, _, qdrant = ingesta_compartida.construir_servicio(
            con_embeddings=False
        )

        assert servicio.client.concurrencia_listado == 4


class TestSalir:
    """Los crons terminan el proceso aunque quede un hilo vivo (plan 305).

    El 2026-10-21 la corrida de sync-estados de las 12:03 imprimió su resumen a
    las 12:33 y el contenedor siguió vivo, sin CPU. Railway no arranca un cron
    mientras el anterior siga corriendo, así que se saltó la de las 13:00.
    `sys.exit` espera a los hilos que no son daemon; `os._exit` no.
    """

    def test_vacia_la_salida_y_termina_con_el_codigo(self, monkeypatch):
        import os
        import sys

        from scripts.ingesta_compartida import salir

        llamadas: list[str | int] = []
        monkeypatch.setattr(sys.stdout, "flush", lambda: llamadas.append("stdout"))
        monkeypatch.setattr(sys.stderr, "flush", lambda: llamadas.append("stderr"))
        monkeypatch.setattr(os, "_exit", lambda codigo: llamadas.append(codigo))

        salir(3)

        assert llamadas == ["stdout", "stderr", 3]
