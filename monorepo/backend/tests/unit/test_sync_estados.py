"""El cron de estados: orquesta listar → aplicar → marcar vencidas.

Decisiones que protege:

- **Cada página se aplica apenas llega** (plan 305). Antes se aplicaba todo al
  terminar el listado, y una corrida que vencía el tope en hora punta perdía lo
  que ya había listado. Los anexos también van por página, aislados.
- **La corrida se registra al empezar y se cierra al terminar.** Si vence el
  tope, queda cerrada como incompleta con lo que alcanzó a listar, y cuenta
  para la racha. Antes no quedaba ninguna fila.
- **Marcar vencidas va después de aplicar.** Así una licitación con el plazo
  ampliado se cierra (o no) con la fecha nueva, no con la que había.
- **Un listado incompleto sale con 0 mientras sea pasajero.** En hora punta la
  API responde 504 casi cada hora (medido 2026-10-05: once corridas seguidas
  entre 10:00 y 18:00), y salir con 1 hacía que Railway mandara un correo de
  "crashed" por cada una. La ventana de 2 h cubre a la corrida siguiente, así
  que una incompleta suelta no pierde nada. Recién cuando se juntan
  `--incompletas-toleradas` seguidas sale con 1: ahí sí hay horas sin mirar.
- **Tocar el techo sí sale con 1 siempre**: no es la API fallando, es la
  configuración quedándose corta, y la corrida siguiente tampoco lo arregla.
- **La ventana no pasa de 6 h.** `ttl_cambio_ms` no admite cursor y la API corta
  el listado en 10.000; con ~1.600 cambios por hora en hora punta (medido el
  2026-09-29), una ventana más ancha se truncaría en silencio.
"""

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.domain.models.cambio_estado import CambioDeEstado, ResultadoSyncEstados
from app.infrastructure.services.tenders.tender_ingestion_service import ListadoCambios
from scripts.sync_estados import con_tope, sincronizar_estados, validar_ventana


def _cambio(code: str) -> CambioDeEstado:
    return CambioDeEstado(
        code=code,
        status_id=6,
        status_code="desierta",
        closing_at=datetime(2026, 10, 1, 12, 0),
    )


CAMBIO = _cambio("A")


def _args(**extra) -> argparse.Namespace:
    base = {
        "ventana_horas": 6.0,
        "limite": 9000,
        "sin_marcar": False,
        "incompletas_toleradas": 3,
    }
    base.update(extra)
    return argparse.Namespace(**base)


AlRecibir = Callable[[list[CambioDeEstado]], Awaitable[None]]


class Piezas:
    """Dobles de las etapas, que anotan en qué orden se llamaron.

    `paginas` son las páginas que entrega el listado, en orden. `colgar_despues`
    hace que el listado se quede esperando después de entregar esa cantidad de
    páginas, para probar el tope. `incompletas_antes` son las incompletas
    seguidas que ya había en el historial; `cerrar` le suma esta si vino
    incompleta.
    """

    def __init__(
        self,
        paginas: list[list[CambioDeEstado]] | None = None,
        *,
        completo: bool = True,
        listadas: int | None = None,
        incompletas_antes: int = 0,
        colgar_despues: int | None = None,
        anexos_falla_con: Exception | None = None,
    ) -> None:
        self.paginas = [[CAMBIO]] if paginas is None else paginas
        self.completo = completo
        self.listadas = listadas
        self.incompletas_antes = incompletas_antes
        self.colgar_despues = colgar_despues
        self.anexos_falla_con = anexos_falla_con
        self.orden: list[str] = []
        self.listar_con: tuple[timedelta, int] | None = None
        self.aplicados: list[list[CambioDeEstado]] = []
        self.anexos_recibidos: list[list[CambioDeEstado]] = []
        self.corrida = uuid4()
        self.cerradas: list[tuple[UUID, bool, int, int | None]] = []

    async def listar(
        self, ventana: timedelta, limite: int, al_recibir: AlRecibir
    ) -> ListadoCambios:
        self.orden.append("listar")
        self.listar_con = (ventana, limite)
        for numero, pagina in enumerate(self.paginas):
            if self.colgar_despues is not None and numero >= self.colgar_despues:
                await asyncio.sleep(10)
            await al_recibir(pagina)
        todos = [c for pagina in self.paginas for c in pagina]
        return ListadoCambios(
            cambios=todos,
            listadas=len(todos) if self.listadas is None else self.listadas,
            ilegibles=0,
            completo=self.completo,
        )

    async def aplicar(self, cambios: list[CambioDeEstado]) -> ResultadoSyncEstados:
        self.orden.append("aplicar")
        self.aplicados.append(cambios)
        return ResultadoSyncEstados(
            conocidas=len(cambios),
            actualizadas=len(cambios),
            llamados_actualizados=2,
            nuevas=1,
        )

    async def aplicar_anexos(self, cambios: list[CambioDeEstado]) -> int:
        self.orden.append("anexos")
        self.anexos_recibidos.append(cambios)
        if self.anexos_falla_con is not None:
            raise self.anexos_falla_con
        return 2

    async def marcar_vencidas(self) -> int:
        self.orden.append("marcar")
        return 3

    async def abrir(self) -> UUID:
        self.orden.append("abrir")
        return self.corrida

    async def cerrar(
        self, corrida: UUID, completo: bool, listadas: int, peticiones: int | None
    ) -> int:
        self.orden.append("cerrar")
        self.cerradas.append((corrida, completo, listadas, peticiones))
        return 0 if completo else self.incompletas_antes + 1

    async def correr(self, args: argparse.Namespace, *, con_anexos: bool = False):
        return await sincronizar_estados(
            args,
            listar=self.listar,
            aplicar=self.aplicar,
            marcar_vencidas=self.marcar_vencidas,
            aplicar_anexos=self.aplicar_anexos if con_anexos else None,
            abrir_corrida=self.abrir,
            cerrar_corrida=self.cerrar,
            peticiones=lambda: 42,
        )


class TestCorridaBuena:
    async def test_aplica_lo_listado_y_sale_con_0(self):
        piezas = Piezas()

        codigo = await piezas.correr(_args())

        assert codigo == 0
        assert piezas.aplicados == [[CAMBIO]]

    async def test_pide_la_ventana_y_el_limite_de_los_argumentos(self):
        piezas = Piezas()

        await piezas.correr(_args(ventana_horas=4.0, limite=500))

        assert piezas.listar_con == (timedelta(hours=4), 500)

    async def test_abre_la_corrida_antes_y_la_cierra_al_final(self):
        piezas = Piezas()

        await piezas.correr(_args())

        assert piezas.orden == ["abrir", "listar", "aplicar", "marcar", "cerrar"]

    async def test_cierra_con_lo_listado_y_las_peticiones(self):
        piezas = Piezas([[_cambio("A")], [_cambio("B")]])

        await piezas.correr(_args())

        assert piezas.cerradas == [(piezas.corrida, True, 2, 42)]

    async def test_sin_marcar_lo_omite(self):
        piezas = Piezas()

        await piezas.correr(_args(sin_marcar=True))

        assert "marcar" not in piezas.orden

    async def test_imprime_el_resumen_de_todas_las_paginas(self, capsys):
        await Piezas([[_cambio("A")], [_cambio("B")]]).correr(_args())

        salida = capsys.readouterr().out
        assert "2 cambios listados" in salida
        assert "2 conocidas" in salida
        assert "4 con llamado actualizado" in salida
        assert "2 nuevas" in salida
        assert "Vencidas marcadas como cerradas: 3" in salida


class TestPorPagina:
    async def test_aplica_cada_pagina_por_separado_y_en_orden(self):
        a, b = _cambio("A"), _cambio("B")
        piezas = Piezas([[a], [b]])

        await piezas.correr(_args())

        assert piezas.aplicados == [[a], [b]]

    async def test_una_pagina_vacia_no_se_aplica(self):
        piezas = Piezas([[], [CAMBIO]])

        await piezas.correr(_args())

        assert piezas.aplicados == [[CAMBIO]]

    async def test_si_vence_el_tope_lo_aplicado_queda_y_la_corrida_se_cierra(self):
        """El caso de hora punta: el listado se arrastra con 504 y vence el tope."""
        a, b = _cambio("A"), _cambio("B")
        piezas = Piezas([[a], [b]], colgar_despues=1)

        codigo = await con_tope(piezas.correr(_args()), segundos=0.05)

        assert codigo == 1
        assert piezas.aplicados == [[a]]
        assert piezas.cerradas == [(piezas.corrida, False, 1, 42)]


class TestCorridaIncompleta:
    async def test_una_incompleta_suelta_sale_con_0_y_aplica_lo_que_llego(self):
        """El caso de hora punta: la API cortó la paginación con un 504."""
        piezas = Piezas(completo=False)

        codigo = await piezas.correr(_args())

        assert codigo == 0
        assert piezas.aplicados == [[CAMBIO]]
        assert "marcar" in piezas.orden

    async def test_avisa_cuantas_seguidas_van_de_las_toleradas(self, capsys):
        piezas = Piezas(completo=False, incompletas_antes=1)

        codigo = await piezas.correr(_args(incompletas_toleradas=3))

        salida = capsys.readouterr().out
        assert codigo == 0
        assert "AVISO" in salida
        assert "2 de 3" in salida

    async def test_al_llegar_a_las_toleradas_sale_con_1(self, capsys):
        piezas = Piezas(completo=False, incompletas_antes=2)

        codigo = await piezas.correr(_args(incompletas_toleradas=3))

        assert codigo == 1
        assert "ERROR" in capsys.readouterr().out

    async def test_una_completa_corta_la_racha(self):
        """Con historial de incompletas, una completa vuelve a salir con 0."""
        piezas = Piezas(incompletas_antes=10)

        assert await piezas.correr(_args()) == 0

    async def test_cierra_si_vino_completa_y_cuantas_listo(self):
        incompleta = Piezas(completo=False, listadas=7)
        completa = Piezas(listadas=4)

        await incompleta.correr(_args())
        await completa.correr(_args())

        assert incompleta.cerradas[0][1:3] == (False, 7)
        assert completa.cerradas[0][1:3] == (True, 4)

    async def test_tocar_el_techo_sale_con_1_y_avisa(self, capsys):
        """No es la API fallando: esperar a la corrida siguiente no lo arregla."""
        piezas = Piezas(listadas=500)

        codigo = await piezas.correr(_args(limite=500))

        assert codigo == 1
        assert "techo" in capsys.readouterr().out

    async def test_sin_historial_se_comporta_como_antes(self):
        """El historial es opcional: sin él, incompleta sigue siendo 1."""
        piezas = Piezas(completo=False)

        codigo = await sincronizar_estados(
            _args(),
            listar=piezas.listar,
            aplicar=piezas.aplicar,
            marcar_vencidas=piezas.marcar_vencidas,
        )

        assert codigo == 1


class TestListaOficialDeAnexos:
    """Los anexos reutilizan el listado: no cuestan peticiones a la API.

    Van con cada página, después de aplicarla y dentro de un try/except: si
    fallan, estados y cierres ya quedaron aplicados y la corrida siguiente lo
    reintenta. No cambian el código de salida: Railway manda un correo por cada
    salida distinta de 0, y una falla pasajera no pide que alguien mire.
    """

    async def test_refresca_los_anexos_de_cada_pagina_despues_de_aplicarla(self):
        a, b = _cambio("A"), _cambio("B")
        piezas = Piezas([[a], [b]])

        codigo = await piezas.correr(_args(), con_anexos=True)

        assert piezas.orden == [
            "abrir",
            "listar",
            "aplicar",
            "anexos",
            "aplicar",
            "anexos",
            "marcar",
            "cerrar",
        ]
        assert piezas.anexos_recibidos == [[a], [b]]
        assert codigo == 0

    async def test_imprime_cuantas_listas_refresco(self, capsys):
        await Piezas([[_cambio("A")], [_cambio("B")]]).correr(_args(), con_anexos=True)

        assert "Listas de anexos refrescadas: 4" in capsys.readouterr().out

    async def test_si_falla_sigue_con_las_paginas_sale_con_0_y_avisa(self, capsys):
        piezas = Piezas(
            [[_cambio("A")], [_cambio("B")]], anexos_falla_con=RuntimeError("sin base")
        )

        codigo = await piezas.correr(_args(), con_anexos=True)

        assert codigo == 0
        assert len(piezas.aplicados) == 2
        assert "marcar" in piezas.orden
        salida = capsys.readouterr().out
        assert "AVISO" in salida
        assert "RuntimeError" in salida

    async def test_sin_el_colaborador_no_los_toca(self):
        piezas = Piezas()

        assert await piezas.correr(_args()) == 0
        assert "anexos" not in piezas.orden


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
        monkeypatch.setattr(settings, "sync_estados_incompletas_toleradas", 5)

        args = construir_parser().parse_args([])

        assert args.ventana_horas == 3.0
        assert args.limite == 4000
        assert args.timeout_minutos == 20.0
        assert args.incompletas_toleradas == 5

    def test_un_argumento_explicito_manda(self, monkeypatch):
        from app.config import settings
        from scripts.sync_estados import construir_parser

        monkeypatch.setattr(settings, "sync_estados_ventana_horas", 3.0)

        args = construir_parser().parse_args(["--ventana-horas", "1"])

        assert args.ventana_horas == 1.0
