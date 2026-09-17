"""La sincronización diaria, la que corre como cron.

Lo que se prueba acá es una sola decisión, y es la que sostiene todo el diseño
del cursor: **cuándo una corrida se registra como `ok`**. Solo las `ok` mueven el
cursor, así que marcar como buena una corrida que no alcanzó a listar su ventana
entera deja un tramo sin pedir **para siempre** — el agujero que `ingestion_run`
existe para tapar.

El caso peligroso no es una caída de la API: es el techo de `--limite`. Medido el
2026-09-10, en un día hábil cambian ~5.600 licitaciones publicadas, contra un
`MERCADOPUBLICO_FETCHING_LIMIT` que vale 2.000 por defecto. Con ese valor la
corrida se corta cada día, y sin el aviso el único síntoma sería un catálogo que
deja de crecer.
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.tender_ingestion_service import ITenderIngestionService
from app.infrastructure.services.tenders.tender_ingestion_service import (
    ResultadoListado,
    ResultadoProceso,
)
from scripts.sync_diaria import con_timeout, sincronizar, verificar_destino


class ServicioFalso(ITenderIngestionService):
    def __init__(self, listado: ResultadoListado, pendientes: int = 0):
        self.listado = listado
        self.pendientes = pendientes
        self.cierre: dict | None = None
        self.ventana_pedida: tuple | None = None
        self.limite_pedido: int | None = None
        self.por_publicacion_pedido: bool | None = None

    async def fetch_tenders_metadata(
        self,
        *,
        dias: int | None = None,
        por_publicacion: bool = False,
        estado: str | None = None,
        limite: int | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> ResultadoListado:
        self.ventana_pedida = (desde, hasta)
        self.limite_pedido = limite
        self.por_publicacion_pedido = por_publicacion
        return self.listado

    async def process_unprocessed_tenders(
        self, limite: int | None = None
    ) -> ResultadoProceso:
        procesadas, self.pendientes = self.pendientes, 0
        return ResultadoProceso(procesadas=procesadas)

    async def ventana_a_sincronizar(self) -> tuple[datetime, datetime]:
        hasta = datetime(2026, 9, 10, tzinfo=UTC)
        return hasta - timedelta(days=1), hasta

    async def registrar_inicio(self, desde: datetime, hasta: datetime) -> UUID:
        return uuid4()

    async def registrar_fin(
        self,
        run_id: UUID,
        *,
        status: str,
        listed: int = 0,
        processed: int = 0,
        failed: int = 0,
    ) -> None:
        self.cierre = {
            "status": status,
            "listed": listed,
            "processed": processed,
            "failed": failed,
        }


def _args(**extra) -> argparse.Namespace:
    base = {"limite": 5000, "estado": "publicada", "sin_marcar": True}
    base.update(extra)
    return argparse.Namespace(**base)


async def _correr(servicio: ServicioFalso, args=None, marcadas: int = 0) -> int:
    async def contar() -> int:
        return servicio.pendientes

    async def marcar() -> int:
        return marcadas

    return await sincronizar(
        args or _args(), servicio, contar=contar, marcar_vencidas=marcar
    )


class TestCuandoLaCorridaEsBuena:
    @pytest.mark.asyncio
    async def test_una_ventana_listada_entera_se_registra_ok(self):
        servicio = ServicioFalso(
            ResultadoListado(nuevas=120, listadas=300, completo=True), pendientes=120
        )

        codigo = await _correr(servicio)

        assert servicio.cierre is not None
        assert servicio.cierre["status"] == "ok"
        assert codigo == 0

    @pytest.mark.asyncio
    async def test_los_contadores_van_al_historial(self):
        servicio = ServicioFalso(
            ResultadoListado(nuevas=120, listadas=300, completo=True), pendientes=120
        )

        await _correr(servicio)

        assert servicio.cierre is not None
        assert servicio.cierre["listed"] == 300
        assert servicio.cierre["processed"] == 120
        assert servicio.cierre["failed"] == 0

    @pytest.mark.asyncio
    async def test_descubre_por_fecha_de_publicacion(self):
        """Y no por ventana de cambios.

        `ttl_cambio_ms` **asume** que publicarse cuenta como un cambio. Si esa
        suposición fuera falsa, el cron no descubriría ninguna licitación nueva y
        nada fallaría: el catálogo simplemente dejaría de crecer. Preguntar por
        fecha de publicación es correcto por construcción.
        """
        servicio = ServicioFalso(ResultadoListado(completo=True))

        await _correr(servicio)

        assert servicio.por_publicacion_pedido is True

    @pytest.mark.asyncio
    async def test_la_ventana_sale_del_cursor_y_no_de_ahora(self):
        """Es la razón de ser de `ingestion_run`: una corrida que no ocurrió no
        puede dejar un hueco que nadie vuelva a mirar."""
        servicio = ServicioFalso(ResultadoListado(completo=True))

        await _correr(servicio)

        desde, hasta = servicio.ventana_pedida  # type: ignore[misc]
        assert (desde, hasta) == await servicio.ventana_a_sincronizar()


class TestCuandoLaVentanaNoSeListoEntera:
    """Ninguno de estos casos puede mover el cursor."""

    @pytest.mark.asyncio
    async def test_un_listado_incompleto_se_registra_partial(self):
        servicio = ServicioFalso(
            ResultadoListado(nuevas=10, listadas=40, completo=False)
        )

        await _correr(servicio)

        assert servicio.cierre is not None
        assert servicio.cierre["status"] == "partial"

    @pytest.mark.asyncio
    async def test_partial_sale_con_codigo_1(self):
        """En un cron de Railway, ese código es la única señal visible."""
        servicio = ServicioFalso(ResultadoListado(completo=False))

        assert await _correr(servicio) == 1

    @pytest.mark.asyncio
    async def test_las_pendientes_quedan_anotadas_como_failed(self):
        servicio = ServicioFalso(
            ResultadoListado(nuevas=5, listadas=40, completo=False), pendientes=0
        )

        await _correr(servicio)

        assert servicio.cierre is not None
        assert servicio.cierre["failed"] == 0


class TestElTechoDeLimite:
    """El fallo silencioso que más probable es que ocurra en producción."""

    @pytest.mark.asyncio
    async def test_avisa_cuando_el_listado_toca_el_techo(self, capsys):
        servicio = ServicioFalso(
            ResultadoListado(nuevas=2000, listadas=2000, completo=False)
        )

        await _correr(servicio, _args(limite=2000))

        salida = capsys.readouterr().out
        assert "MERCADOPUBLICO_FETCHING_LIMIT" in salida
        assert "el cursor NO avanza" in salida

    @pytest.mark.asyncio
    async def test_no_avisa_cuando_hay_margen(self, capsys):
        servicio = ServicioFalso(
            ResultadoListado(nuevas=100, listadas=300, completo=True)
        )

        await _correr(servicio, _args(limite=5000))

        assert "MERCADOPUBLICO_FETCHING_LIMIT" not in capsys.readouterr().out

    @pytest.mark.asyncio
    async def test_el_limite_pedido_viaja_al_servicio(self):
        servicio = ServicioFalso(ResultadoListado(completo=True))

        await _correr(servicio, _args(limite=9000))

        assert servicio.limite_pedido == 9000


class TestElBarridoDeVencidas:
    @pytest.mark.asyncio
    async def test_corre_antes_de_hablar_con_la_api(self, capsys):
        """Cuota cero, y conviene que ocurra aunque la API esté caída."""
        servicio = ServicioFalso(ResultadoListado(completo=True))

        await _correr(servicio, _args(sin_marcar=False), marcadas=37)

        salida = capsys.readouterr().out
        assert "Vencidas marcadas como cerradas: 37" in salida
        assert salida.index("Vencidas marcadas") < salida.index("Ventana:")

    @pytest.mark.asyncio
    async def test_sin_marcar_lo_omite(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True))

        await _correr(servicio, _args(sin_marcar=True), marcadas=37)

        assert "Vencidas marcadas" not in capsys.readouterr().out


class TestGuardaContraProduccion:
    """El cron corre contra producción a propósito; una prueba local, no.

    Hasta ahora el script solo imprimía a qué base apuntaba. Con un `.env` que
    quedó apuntando a producción, una "prueba local" escribía ahí sin avisar. Es
    el mismo criterio que ya tiene `bootstrap_corpus.py`: lo que toca producción
    tiene que pedirse explícitamente, no pasar por olvidar una variable.
    """

    def test_se_niega_contra_una_base_no_local_sin_confirmar(self):
        mensaje = verificar_destino(
            "postgresql://u:p@db.abcd.supabase.co:5432/postgres",
            confirmar_produccion=False,
        )

        assert mensaje is not None
        assert "db.abcd.supabase.co" in mensaje
        assert "--confirmar-produccion" in mensaje

    def test_corre_contra_una_base_local(self):
        assert (
            verificar_destino(
                "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
                confirmar_produccion=False,
            )
            is None
        )

    def test_corre_contra_produccion_si_se_confirma(self):
        """Es lo que lleva el `startCommand` del servicio de Railway."""
        assert (
            verificar_destino(
                "postgresql://u:p@db.abcd.supabase.co:5432/postgres",
                confirmar_produccion=True,
            )
            is None
        )


class TestPrepararDestino:
    """Contra una base recién creada, el primer `tender` falla por FK de región.

    Sembrar regiones y crear la colección hoy solo lo hace el arranque de la API.
    El cron no puede depender de que la API haya corrido alguna vez.
    """

    @pytest.mark.asyncio
    async def test_se_prepara_antes_de_pedir_la_ventana(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True))
        orden: list[str] = []

        async def preparar() -> None:
            orden.append("preparar")
            print("PREPARADO")

        async def contar() -> int:
            return servicio.pendientes

        async def marcar() -> int:
            return 0

        await sincronizar(
            _args(),
            servicio,
            contar=contar,
            marcar_vencidas=marcar,
            preparar_destino=preparar,
        )

        salida = capsys.readouterr().out
        assert orden == ["preparar"]
        assert salida.index("PREPARADO") < salida.index("Ventana:")


class TestTimeout:
    """Railway no termina una corrida colgada y **omite todas las siguientes**.

    Un cron que se queda esperando una respuesta que no llega deja de correr para
    siempre sin avisar. El timeout lo convierte en un fallo visible (código 1) y
    libera la ejecución del día siguiente. Dejar la fila en `running` es seguro:
    ese estado nunca mueve el cursor.
    """

    @pytest.mark.asyncio
    async def test_una_corrida_colgada_termina_con_codigo_1(self):
        async def colgada() -> int:
            await asyncio.sleep(10)
            return 0

        assert await con_timeout(colgada(), segundos=0.01) == 1

    @pytest.mark.asyncio
    async def test_una_corrida_a_tiempo_conserva_su_codigo(self):
        async def rapida() -> int:
            return 0

        assert await con_timeout(rapida(), segundos=5) == 0
