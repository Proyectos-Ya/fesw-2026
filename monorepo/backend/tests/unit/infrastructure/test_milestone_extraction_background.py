import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from app.application.services.milestone_extraction_background import (
    MilestoneExtractionStatus,
)
from app.domain.errors.milestone_errors import MilestoneExtractionUnavailable
from app.infrastructure.services.milestone_extraction_background import (
    AsyncioMilestoneExtractionBackground,
)

USUARIO, LICITACION = uuid4(), uuid4()


class ExtraerFalso:
    """Registra cada pasada; puede tardar o fallar para simular a Gemini."""

    def __init__(self, demora: float = 0.0, errores: list[Exception] | None = None) -> None:
        self.llamadas: list[tuple] = []
        self.demora = demora
        self.errores = list(errores or [])
        self.en_curso = 0
        self.max_en_curso = 0

    async def execute(self, user_id, tender_id):
        self.en_curso += 1
        self.max_en_curso = max(self.max_en_curso, self.en_curso)
        try:
            await asyncio.sleep(self.demora)
            self.llamadas.append((user_id, tender_id))
            if self.errores:
                raise self.errores.pop(0)
            return "resultado"
        finally:
            self.en_curso -= 1


def _fondo(extraer: ExtraerFalso, sesiones: list[str] | None = None):
    sesiones = sesiones if sesiones is not None else []

    @asynccontextmanager
    async def abrir():
        # Cada pasada abre su propia sesión: la de la subida ya se cerró.
        sesiones.append("abierta")
        yield extraer
        sesiones.append("cerrada")

    return AsyncioMilestoneExtractionBackground(abrir)


async def test_extrae_en_segundo_plano_con_una_sesion_propia():
    extraer, sesiones = ExtraerFalso(), []
    fondo = _fondo(extraer, sesiones)

    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    assert extraer.llamadas == [(USUARIO, LICITACION)]
    assert sesiones == ["abierta", "cerrada"]
    assert fondo.status(USUARIO, LICITACION) is MilestoneExtractionStatus.IDLE


async def test_mientras_corre_el_estado_es_en_curso():
    fondo = _fondo(ExtraerFalso(demora=0.05))

    fondo.schedule(USUARIO, LICITACION)

    assert fondo.status(USUARIO, LICITACION) is MilestoneExtractionStatus.RUNNING
    assert fondo.status(USUARIO, uuid4()) is MilestoneExtractionStatus.IDLE
    await fondo.wait_idle()
    assert fondo.status(USUARIO, LICITACION) is MilestoneExtractionStatus.IDLE


async def test_varias_subidas_seguidas_se_agrupan_en_una_pasada_mas():
    # Subir tres archivos seguidos no lanza tres llamadas a Gemini: la segunda
    # pasada lee los tres.
    extraer = ExtraerFalso(demora=0.05)
    fondo = _fondo(extraer)

    fondo.schedule(USUARIO, LICITACION)
    await asyncio.sleep(0.01)  # la primera pasada ya está leyendo
    fondo.schedule(USUARIO, LICITACION)
    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    assert len(extraer.llamadas) == 2
    assert extraer.max_en_curso == 1


async def test_subidas_antes_de_que_empiece_la_pasada_no_agregan_otra():
    # La pasada todavía no leyó nada: cuando lo haga, verá todos los archivos.
    extraer = ExtraerFalso(demora=0.05)
    fondo = _fondo(extraer)

    fondo.schedule(USUARIO, LICITACION)
    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    assert len(extraer.llamadas) == 1


async def test_licitaciones_distintas_no_se_esperan_entre_si():
    extraer = ExtraerFalso(demora=0.05)
    fondo = _fondo(extraer)
    otra = uuid4()

    fondo.schedule(USUARIO, LICITACION)
    fondo.schedule(USUARIO, otra)
    await fondo.wait_idle()

    assert sorted(extraer.llamadas, key=str) == sorted([(USUARIO, LICITACION), (USUARIO, otra)], key=str)
    assert extraer.max_en_curso == 2


async def test_si_la_ia_falla_queda_marcada_como_fallida_y_no_se_propaga():
    fondo = _fondo(ExtraerFalso(errores=[MilestoneExtractionUnavailable()]))

    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    assert fondo.status(USUARIO, LICITACION) is MilestoneExtractionStatus.FAILED


async def test_un_error_inesperado_tambien_queda_como_fallida():
    fondo = _fondo(ExtraerFalso(errores=[RuntimeError("base caída")]))

    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    assert fondo.status(USUARIO, LICITACION) is MilestoneExtractionStatus.FAILED


async def test_una_pasada_exitosa_limpia_la_falla_anterior():
    fondo = _fondo(ExtraerFalso(errores=[MilestoneExtractionUnavailable()]))
    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    assert fondo.status(USUARIO, LICITACION) is MilestoneExtractionStatus.IDLE


async def test_la_extraccion_manual_espera_a_la_automatica():
    # Dos extracciones a la vez sobre la misma licitación duplicarían hitos.
    automatica = ExtraerFalso(demora=0.05)
    manual = ExtraerFalso()
    fondo = _fondo(automatica)
    fondo.schedule(USUARIO, LICITACION)
    await asyncio.sleep(0)

    resultado = await fondo.run_now(USUARIO, LICITACION, manual)

    assert resultado == "resultado"
    assert automatica.llamadas == [(USUARIO, LICITACION)]
    assert manual.llamadas == [(USUARIO, LICITACION)]


async def test_la_extraccion_manual_exitosa_limpia_la_falla():
    fondo = _fondo(ExtraerFalso(errores=[MilestoneExtractionUnavailable()]))
    fondo.schedule(USUARIO, LICITACION)
    await fondo.wait_idle()

    await fondo.run_now(USUARIO, LICITACION, ExtraerFalso())

    assert fondo.status(USUARIO, LICITACION) is MilestoneExtractionStatus.IDLE


async def test_la_extraccion_manual_propaga_su_error():
    fondo = _fondo(ExtraerFalso())

    with pytest.raises(MilestoneExtractionUnavailable):
        await fondo.run_now(
            USUARIO, LICITACION, ExtraerFalso(errores=[MilestoneExtractionUnavailable()])
        )


async def test_al_apagar_cancela_lo_pendiente():
    extraer = ExtraerFalso(demora=10)
    fondo = _fondo(extraer)

    fondo.schedule(USUARIO, LICITACION)
    await asyncio.sleep(0)
    await fondo.shutdown()

    assert fondo.pending == 0
    assert extraer.llamadas == []
