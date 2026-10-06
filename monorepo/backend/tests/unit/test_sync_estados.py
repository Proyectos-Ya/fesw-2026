"""El cron de estados: orquesta listar → aplicar → marcar vencidas.

Decisiones que protege:

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
- Lo que sí llegó se aplica igual en todos los casos.
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
    base = {
        "ventana_horas": 6.0,
        "limite": 9000,
        "sin_marcar": False,
        "incompletas_toleradas": 3,
    }
    base.update(extra)
    return argparse.Namespace(**base)


class Piezas:
    """Dobles de las etapas, que anotan en qué orden se llamaron.

    `incompletas_antes` son las corridas incompletas seguidas que ya había en el
    historial antes de esta; `registrar` le suma esta si vino incompleta.
    """

    def __init__(self, listado: ListadoCambios, incompletas_antes: int = 0) -> None:
        self.listado = listado
        self.incompletas_antes = incompletas_antes
        self.orden: list[str] = []
        self.listar_con: tuple[timedelta, int] | None = None
        self.aplicados: list[CambioDeEstado] = []
        self.registradas: list[tuple[bool, int]] = []

    async def listar(self, ventana: timedelta, limite: int) -> ListadoCambios:
        self.orden.append("listar")
        self.listar_con = (ventana, limite)
        return self.listado

    async def aplicar(self, cambios: list[CambioDeEstado]) -> ResultadoSyncEstados:
        self.orden.append("aplicar")
        self.aplicados = cambios
        return ResultadoSyncEstados(conocidas=len(cambios), actualizadas=len(cambios))

    async def marcar_vencidas(self) -> int:
        self.orden.append("marcar")
        return 3

    async def registrar(self, completo: bool, listadas: int) -> int:
        self.orden.append("registrar")
        self.registradas.append((completo, listadas))
        return 0 if completo else self.incompletas_antes + 1

    async def correr(self, args: argparse.Namespace) -> int:
        return await sincronizar_estados(
            args,
            listar=self.listar,
            aplicar=self.aplicar,
            marcar_vencidas=self.marcar_vencidas,
            registrar_corrida=self.registrar,
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

        assert piezas.orden == ["listar", "aplicar", "marcar", "registrar"]

    async def test_sin_marcar_lo_omite(self):
        piezas = Piezas(_listado())

        await piezas.correr(_args(sin_marcar=True))

        assert "marcar" not in piezas.orden

    async def test_imprime_el_resumen(self, capsys):
        await Piezas(_listado()).correr(_args())

        salida = capsys.readouterr().out
        assert "1 cambios listados" in salida
        assert "Vencidas marcadas como cerradas: 3" in salida


class TestCorridaIncompleta:
    async def test_una_incompleta_suelta_sale_con_0_y_aplica_lo_que_llego(self):
        """El caso de hora punta: la API cortó la paginación con un 504."""
        piezas = Piezas(_listado(completo=False))

        codigo = await piezas.correr(_args())

        assert codigo == 0
        assert piezas.aplicados == [CAMBIO]
        assert "marcar" in piezas.orden

    async def test_avisa_cuantas_seguidas_van_de_las_toleradas(self, capsys):
        piezas = Piezas(_listado(completo=False), incompletas_antes=1)

        codigo = await piezas.correr(_args(incompletas_toleradas=3))

        salida = capsys.readouterr().out
        assert codigo == 0
        assert "AVISO" in salida
        assert "2 de 3" in salida

    async def test_al_llegar_a_las_toleradas_sale_con_1(self, capsys):
        piezas = Piezas(_listado(completo=False), incompletas_antes=2)

        codigo = await piezas.correr(_args(incompletas_toleradas=3))

        assert codigo == 1
        assert "ERROR" in capsys.readouterr().out

    async def test_una_completa_corta_la_racha(self):
        """Con historial de incompletas, una completa vuelve a salir con 0."""
        piezas = Piezas(_listado(), incompletas_antes=10)

        assert await piezas.correr(_args()) == 0

    async def test_registra_si_vino_completa_y_cuantas_listo(self):
        incompleta = Piezas(_listado(completo=False, listadas=7))
        completa = Piezas(_listado(listadas=4))

        await incompleta.correr(_args())
        await completa.correr(_args())

        assert incompleta.registradas == [(False, 7)]
        assert completa.registradas == [(True, 4)]

    async def test_tocar_el_techo_sale_con_1_y_avisa(self, capsys):
        """No es la API fallando: esperar a la corrida siguiente no lo arregla."""
        piezas = Piezas(_listado(listadas=500))

        codigo = await piezas.correr(_args(limite=500))

        assert codigo == 1
        assert "techo" in capsys.readouterr().out

    async def test_sin_historial_se_comporta_como_antes(self):
        """`registrar_corrida` es opcional: sin él, incompleta sigue siendo 1."""
        piezas = Piezas(_listado(completo=False))

        codigo = await sincronizar_estados(
            _args(),
            listar=piezas.listar,
            aplicar=piezas.aplicar,
            marcar_vencidas=piezas.marcar_vencidas,
        )

        assert codigo == 1


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
