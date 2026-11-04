import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from app.infrastructure.services.tender_analysis_background import (
    AsyncioTenderAnalysisBackground,
)

EMPRESA, LICITACION = uuid4(), uuid4()


class AnalizarFalso:
    """Registra cada pasada; puede tardar o fallar para simular a Gemini."""

    def __init__(self, demora: float = 0.0, errores: list[Exception] | None = None) -> None:
        self.llamadas: list[tuple] = []
        self.demora = demora
        self.errores = list(errores or [])

    async def execute(self, workspace_id, tender_id):
        await asyncio.sleep(self.demora)
        self.llamadas.append((workspace_id, tender_id))
        if self.errores:
            raise self.errores.pop(0)


def _fondo(analizar: AnalizarFalso, sesiones: list[str] | None = None):
    sesiones = sesiones if sesiones is not None else []

    @asynccontextmanager
    async def abrir():
        # Cada pasada abre su propia sesión: la de la subida ya se cerró.
        sesiones.append("abierta")
        yield analizar
        sesiones.append("cerrada")

    return AsyncioTenderAnalysisBackground(abrir)


async def test_analiza_en_segundo_plano_con_una_sesion_propia():
    analizar, sesiones = AnalizarFalso(), []
    fondo = _fondo(analizar, sesiones)

    fondo.schedule(EMPRESA, LICITACION)
    await fondo.wait_idle()

    assert analizar.llamadas == [(EMPRESA, LICITACION)]
    assert sesiones == ["abierta", "cerrada"]
    assert not fondo.is_running(EMPRESA, LICITACION)


async def test_mientras_corre_informa_que_esta_en_curso():
    fondo = _fondo(AnalizarFalso(demora=0.05))

    fondo.schedule(EMPRESA, LICITACION)

    assert fondo.is_running(EMPRESA, LICITACION)
    await fondo.wait_idle()
    assert not fondo.is_running(EMPRESA, LICITACION)


async def test_varias_subidas_seguidas_hacen_como_mucho_una_pasada_mas():
    # Subir tres anexos seguidos no cuesta tres llamadas a Gemini: la pasada en
    # curso termina y se hace una más, que ve todos los anexos.
    analizar = AnalizarFalso(demora=0.02)
    fondo = _fondo(analizar)

    fondo.schedule(EMPRESA, LICITACION)
    await asyncio.sleep(0.005)
    fondo.schedule(EMPRESA, LICITACION)
    fondo.schedule(EMPRESA, LICITACION)
    await fondo.wait_idle()
    await fondo.wait_idle()

    assert len(analizar.llamadas) == 2


async def test_un_error_no_se_propaga_y_no_frena_la_siguiente():
    analizar = AnalizarFalso(errores=[RuntimeError("Gemini caído")])
    fondo = _fondo(analizar)

    fondo.schedule(EMPRESA, LICITACION)
    await fondo.wait_idle()
    fondo.schedule(EMPRESA, LICITACION)
    await fondo.wait_idle()

    assert len(analizar.llamadas) == 2


async def test_empresas_distintas_no_se_esperan_entre_si():
    analizar = AnalizarFalso(demora=0.02)
    fondo = _fondo(analizar)
    otra = uuid4()

    fondo.schedule(EMPRESA, LICITACION)
    fondo.schedule(otra, LICITACION)
    await fondo.wait_idle()

    assert sorted(analizar.llamadas) == sorted([(EMPRESA, LICITACION), (otra, LICITACION)])


async def test_al_apagar_cancela_lo_pendiente():
    fondo = _fondo(AnalizarFalso(demora=1))

    fondo.schedule(EMPRESA, LICITACION)
    await fondo.shutdown()

    assert not fondo.is_running(EMPRESA, LICITACION)
