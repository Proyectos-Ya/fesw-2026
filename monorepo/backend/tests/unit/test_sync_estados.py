"""El cron de estados: orquesta listar → aplicar → marcar vencidas.

Decisiones que protege:

- **Marcar vencidas va después de aplicar.** Así una licitación con el plazo
  ampliado se cierra (o no) con la fecha nueva, no con la que había.
- **Un listado incompleto o que toca el techo sale con código 1**, pero lo que
  sí llegó se aplica igual: es información correcta, solo falta el resto.
- **La ventana no pasa de 6 h.** `ttl_cambio_ms` no admite cursor y la API corta
  el listado en 10.000; con ~1.600 cambios por hora en hora punta (medido el
  2026-09-29), una ventana más ancha se truncaría en silencio.
"""

import argparse
import asyncio
from datetime import datetime, timedelta

from app.domain.models.cambio_estado import CambioDeEstado, ResultadoSyncEstados
from app.infrastructure.services.tenders.tender_ingestion_service import ListadoCambios
from scripts.sync_estados import con_tope, sincronizar_estados, validar_ventana

CAMBIO = CambioDeEstado(
    code="A",
    status_id=6,
    status_code="desierta",
    closing_at=datetime(2026, 10, 1, 12, 0),
)


def _args(**extra) -> argparse.Namespace:
    base = {"ventana_horas": 6.0, "limite": 9000, "sin_marcar": False}
    base.update(extra)
    return argparse.Namespace(**base)


class Piezas:
    """Dobles de las tres etapas, que anotan en qué orden se llamaron."""

    def __init__(self, listado: ListadoCambios) -> None:
        self.listado = listado
        self.orden: list[str] = []
        self.listar_con: tuple[timedelta, int] | None = None
        self.aplicados: list[CambioDeEstado] = []

    async def listar(self, ventana: timedelta, limite: int) -> ListadoCambios:
        self.orden.append("listar")
        self.listar_con = (ventana, limite)
        return self.listado

    async def aplicar(self, cambios: list[CambioDeEstado]) -> ResultadoSyncEstados:
        self.orden.append("aplicar")
        self.aplicados = cambios
        return ResultadoSyncEstados(
            conocidas=len(cambios),
            actualizadas=len(cambios),
            llamados_actualizados=2,
        )

    async def marcar_vencidas(self) -> int:
        self.orden.append("marcar")
        return 3

    async def correr(self, args: argparse.Namespace) -> int:
        return await sincronizar_estados(
            args,
            listar=self.listar,
            aplicar=self.aplicar,
            marcar_vencidas=self.marcar_vencidas,
        )


def _listado(completo: bool = True, listadas: int = 1) -> ListadoCambios:
    return ListadoCambios(
        cambios=[CAMBIO], listadas=listadas, ilegibles=0, completo=completo
    )


class TestCorridaBuena:
    async def test_aplica_lo_listado_y_sale_con_0(self):
        piezas = Piezas(_listado())

        codigo = await piezas.correr(_args())

        assert codigo == 0
        assert piezas.aplicados == [CAMBIO]

    async def test_pide_la_ventana_y_el_limite_de_los_argumentos(self):
        piezas = Piezas(_listado())

        await piezas.correr(_args(ventana_horas=4.0, limite=500))

        assert piezas.listar_con == (timedelta(hours=4), 500)

    async def test_marca_vencidas_despues_de_aplicar(self):
        piezas = Piezas(_listado())

        await piezas.correr(_args())

        assert piezas.orden == ["listar", "aplicar", "marcar"]

    async def test_sin_marcar_lo_omite(self):
        piezas = Piezas(_listado())

        await piezas.correr(_args(sin_marcar=True))

        assert "marcar" not in piezas.orden

    async def test_imprime_el_resumen(self, capsys):
        await Piezas(_listado()).correr(_args())

        salida = capsys.readouterr().out
        assert "1 cambios listados" in salida
        assert "2 con llamado actualizado" in salida
        assert "Vencidas marcadas como cerradas: 3" in salida


class TestCorridaIncompleta:
    async def test_un_listado_cortado_sale_con_1_pero_aplica_lo_que_llego(self):
        piezas = Piezas(_listado(completo=False))

        codigo = await piezas.correr(_args())

        assert codigo == 1
        assert piezas.aplicados == [CAMBIO]
        assert "marcar" in piezas.orden

    async def test_tocar_el_techo_sale_con_1_y_avisa(self, capsys):
        piezas = Piezas(_listado(listadas=500))

        codigo = await piezas.correr(_args(limite=500))

        assert codigo == 1
        assert "techo" in capsys.readouterr().out


class PiezasConAnexos(Piezas):
    """Suma el cuarto paso: refrescar la lista oficial de anexos."""

    def __init__(self, listado: ListadoCambios, falla_con: Exception | None = None) -> None:
        super().__init__(listado)
        self.falla_con = falla_con
        self.anexos_recibidos: list[CambioDeEstado] = []

    async def aplicar_anexos(self, cambios: list[CambioDeEstado]) -> int:
        self.orden.append("anexos")
        self.anexos_recibidos = cambios
        if self.falla_con is not None:
            raise self.falla_con
        return 2

    async def correr(self, args: argparse.Namespace) -> int:
        return await sincronizar_estados(
            args,
            listar=self.listar,
            aplicar=self.aplicar,
            marcar_vencidas=self.marcar_vencidas,
            aplicar_anexos=self.aplicar_anexos,
        )


class TestListaOficialDeAnexos:
    """El cuarto paso reutiliza el listado: no cuesta peticiones a la API.

    Va al final y dentro de un try/except: si falla, estados y cierres ya
    quedaron aplicados y solo cambia el código de salida.
    """

    async def test_refresca_los_anexos_despues_de_marcar_vencidas(self):
        piezas = PiezasConAnexos(_listado())

        codigo = await piezas.correr(_args())

        assert piezas.orden == ["listar", "aplicar", "marcar", "anexos"]
        assert piezas.anexos_recibidos == [CAMBIO]
        assert codigo == 0

    async def test_con_sin_marcar_queda_listar_aplicar_anexos(self):
        piezas = PiezasConAnexos(_listado())

        await piezas.correr(_args(sin_marcar=True))

        assert piezas.orden == ["listar", "aplicar", "anexos"]

    async def test_imprime_cuantas_listas_refresco(self, capsys):
        await PiezasConAnexos(_listado()).correr(_args())

        assert "Listas de anexos refrescadas: 2" in capsys.readouterr().out

    async def test_si_falla_marca_las_vencidas_sale_con_1_y_avisa(self, capsys):
        piezas = PiezasConAnexos(_listado(), falla_con=RuntimeError("sin base"))

        codigo = await piezas.correr(_args())

        assert codigo == 1
        assert "marcar" in piezas.orden
        salida = capsys.readouterr().out
        assert "AVISO" in salida
        assert "RuntimeError" in salida

    async def test_sin_el_colaborador_el_comportamiento_es_el_de_siempre(self):
        piezas = Piezas(_listado())

        assert await piezas.correr(_args()) == 0
        assert piezas.orden == ["listar", "aplicar", "marcar"]


class TestValidarVentana:
    def test_acepta_hasta_6_horas(self):
        assert validar_ventana(2) is None
        assert validar_ventana(6) is None

    def test_rechaza_mas_de_6_horas(self):
        mensaje = validar_ventana(8)
        assert mensaje is not None and "10.000" in mensaje

    def test_rechaza_ventanas_vacias(self):
        assert validar_ventana(0) is not None


class TestTope:
    async def test_una_corrida_colgada_termina_con_codigo_1(self):
        async def colgada() -> int:
            await asyncio.sleep(10)
            return 0

        assert await con_tope(colgada(), segundos=0.01) == 1

    async def test_una_corrida_a_tiempo_conserva_su_codigo(self):
        async def rapida() -> int:
            return 0

        assert await con_tope(rapida(), segundos=5) == 0


class TestDefaultsDesdeElEntorno:
    """Las variables `SYNC_ESTADOS_*` fijan los valores por defecto; un argumento
    explícito en el `startCommand` sigue mandando sobre ellas."""

    def test_los_defaults_salen_de_la_configuracion(self, monkeypatch):
        from app.config import settings
        from scripts.sync_estados import construir_parser

        monkeypatch.setattr(settings, "sync_estados_ventana_horas", 3.0)
        monkeypatch.setattr(settings, "sync_estados_limite", 4000)
        monkeypatch.setattr(settings, "sync_estados_timeout_minutos", 20.0)

        args = construir_parser().parse_args([])

        assert args.ventana_horas == 3.0
        assert args.limite == 4000
        assert args.timeout_minutos == 20.0

    def test_un_argumento_explicito_manda(self, monkeypatch):
        from app.config import settings
        from scripts.sync_estados import construir_parser

        monkeypatch.setattr(settings, "sync_estados_ventana_horas", 3.0)

        args = construir_parser().parse_args(["--ventana-horas", "1"])

        assert args.ventana_horas == 1.0
