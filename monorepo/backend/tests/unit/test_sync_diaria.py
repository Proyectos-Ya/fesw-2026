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

from app.application.services.tender_ingestion_service import (
    ITenderIngestionService,
    ModoCola,
)
from app.domain.models.tender_ingestion_dto import DocumentoOficialDTO
from app.infrastructure.services.tenders.tender_ingestion_service import (
    ResultadoListado,
    ResultadoProceso,
)
from scripts.sync_diaria import (
    con_timeout,
    elegir_modo,
    partir_en_tramos,
    sincronizar,
    vaciar_frecuente,
    verificar_destino,
)


class ServicioFalso(ITenderIngestionService):
    def __init__(self, listado: ResultadoListado, pendientes: int = 0):
        self.listado = listado
        self.pendientes = pendientes
        self.cierre: dict | None = None
        self.ventana_pedida: tuple | None = None
        self.limite_pedido: int | None = None
        self.por_publicacion_pedido: bool | None = None
        self.cuota_agotada = False
        # `started_at` de las corridas que figuran en `running`.
        self.corridas_en_curso: list[datetime] = []
        self.inicio_registrado = False
        # Plan 305: cada corrida y cada tramo dejan su fila, con su tipo.
        self.inicios: list[tuple[str, datetime, datetime]] = []
        self.cierres: list[dict] = []
        self.ventanas_pedidas: list[tuple] = []
        self.pasadas: list[tuple[ModoCola, datetime | None]] = []
        # Si un tramo dado (por índice) vuelve incompleto.
        self.tramos_incompletos: set[int] = set()
        self._tipos: dict[UUID, str] = {}

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
        self.ventanas_pedidas.append((desde, hasta))
        self.limite_pedido = limite
        self.por_publicacion_pedido = por_publicacion
        if len(self.ventanas_pedidas) - 1 in self.tramos_incompletos:
            return ResultadoListado(nuevas=0, listadas=1, completo=False, documentos={})
        return self.listado

    async def process_unprocessed_tenders(
        self,
        limite: int | None = None,
        *,
        modo: ModoCola = ModoCola.TODAS,
        antes_de: datetime | None = None,
    ) -> ResultadoProceso:
        self.pasadas.append((modo, antes_de))
        if self.cuota_agotada:
            return ResultadoProceso(cuota_agotada=True)
        procesadas, self.pendientes = self.pendientes, 0
        return ResultadoProceso(procesadas=procesadas)

    async def ventana_a_sincronizar(self) -> tuple[datetime, datetime]:
        hasta = datetime(2026, 9, 10, tzinfo=UTC)
        return hasta - timedelta(days=1), hasta

    async def registrar_inicio(
        self, desde: datetime, hasta: datetime, *, kind: str = "tramo"
    ) -> UUID:
        self.inicio_registrado = True
        self.inicios.append((kind, desde, hasta))
        run_id = uuid4()
        self._tipos[run_id] = kind
        return run_id

    async def cerrar_corridas_colgadas(self, antes_de: datetime) -> int:
        viejas = [c for c in self.corridas_en_curso if c < antes_de]
        self.corridas_en_curso = [c for c in self.corridas_en_curso if c >= antes_de]
        return len(viejas)

    async def hay_corrida_en_curso(self) -> bool:
        return bool(self.corridas_en_curso)

    async def registrar_fin(
        self,
        run_id: UUID,
        *,
        status: str,
        listed: int = 0,
        processed: int = 0,
        failed: int = 0,
        requests: int | None = None,
        embedding_calls: int | None = None,
    ) -> None:
        self.cierre = {
            "status": status,
            "listed": listed,
            "processed": processed,
            "failed": failed,
            "requests": requests,
            "embedding_calls": embedding_calls,
            "kind": self._tipos.get(run_id),
        }
        self.cierres.append(self.cierre)

    def cierres_de(self, kind: str) -> list[dict]:
        return [c for c in self.cierres if c["kind"] == kind]


def _args(**extra) -> argparse.Namespace:
    # Un tramo más ancho que la ventana del doble: un solo tramo, como antes.
    base = {
        "limite": 5000,
        "estado": "publicada",
        "sin_marcar": False,
        "tramo_horas": 24 * 30,
    }
    base.update(extra)
    return argparse.Namespace(**base)


async def _correr(servicio: ServicioFalso, args=None) -> int:
    async def contar(*_) -> int:
        return servicio.pendientes

    return await sincronizar(args or _args(), servicio, contar=contar)


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


class TestElBarridoDeVencidasSeMudoAlCronDeEstados:
    """Marcar vencidas lo hace ahora `sync_estados`, **después** de corregir los
    cierres con el listado de cambios. Hecho acá, antes de esa corrección, una
    licitación con el plazo ampliado se cerraba con la fecha vieja."""

    @pytest.mark.asyncio
    async def test_la_corrida_ya_no_marca_vencidas(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True))

        await _correr(servicio, _args(sin_marcar=False))

        assert "Vencidas marcadas" not in capsys.readouterr().out

    @pytest.mark.asyncio
    async def test_sin_marcar_se_acepta_y_avisa_que_no_hace_nada(self, capsys):
        """Un `startCommand` del panel de Railway puede llevarla todavía."""
        servicio = ServicioFalso(ResultadoListado(completo=True))

        codigo = await _correr(servicio, _args(sin_marcar=True))

        assert codigo == 0
        assert "--sin-marcar ya no tiene efecto" in capsys.readouterr().out


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

        async def contar(*_) -> int:
            return servicio.pendientes

        await sincronizar(
            _args(),
            servicio,
            contar=contar,
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


class TestListaOficialDeAnexos:
    """La lista sale del mismo listado y se aplica **al final**.

    Si el tope de tiempo cancelara este paso antes de `registrar_fin`, la corrida
    quedaría en `running`, el cursor no avanzaría y la siguiente volvería a listar
    la ventana gastando cuota. Por eso va después de cerrar la corrida y aislado:
    si falla, el cursor avanza igual y solo cambia el código de salida.
    """

    DOC = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")

    async def _correr_con_anexos(self, servicio: ServicioFalso, aplicar_anexos) -> int:
        async def contar(*_) -> int:
            return servicio.pendientes

        return await sincronizar(
            _args(), servicio, contar=contar, aplicar_anexos=aplicar_anexos
        )

    async def test_aplica_la_lista_del_listado_despues_de_registrar_el_fin(self):
        servicio = ServicioFalso(
            ResultadoListado(
                nuevas=1, listadas=1, completo=True, documentos={"A": [self.DOC]}
            )
        )
        recibido: list = []
        cierre_al_llamar: list = []

        async def aplicar_anexos(listas) -> int:
            recibido.append(listas)
            cierre_al_llamar.append(servicio.cierre)
            return 1

        codigo = await self._correr_con_anexos(servicio, aplicar_anexos)

        assert recibido == [{"A": [self.DOC]}]
        assert cierre_al_llamar[0] is not None  # `registrar_fin` ya corrió
        assert codigo == 0

    async def test_si_falla_el_cursor_avanza_igual_sale_con_1_y_avisa(self, capsys):
        servicio = ServicioFalso(
            ResultadoListado(
                nuevas=1, listadas=1, completo=True, documentos={"A": [self.DOC]}
            )
        )

        async def aplicar_anexos(listas) -> int:
            raise RuntimeError("sin base")

        codigo = await self._correr_con_anexos(servicio, aplicar_anexos)

        assert servicio.cierre is not None
        assert servicio.cierre["status"] == "ok"
        assert codigo == 1
        assert "AVISO" in capsys.readouterr().out

    async def test_sin_documentos_no_se_llama(self):
        servicio = ServicioFalso(
            ResultadoListado(listadas=1, completo=True, documentos={})
        )
        llamadas: list = []

        async def aplicar_anexos(listas) -> int:
            llamadas.append(listas)
            return 0

        codigo = await self._correr_con_anexos(servicio, aplicar_anexos)

        assert llamadas == []
        assert codigo == 0

    async def test_sin_el_colaborador_el_comportamiento_es_el_de_siempre(self):
        servicio = ServicioFalso(
            ResultadoListado(
                nuevas=1, listadas=1, completo=True, documentos={"A": [self.DOC]}
            )
        )

        assert await _correr(servicio) == 0


class TestCodigoDeSalida:
    """En un cron de Railway el código de salida es la única señal visible."""

    async def test_cuota_agotada_sale_con_error_aunque_el_listado_este_completo(self):
        """El cursor avanza igual (se listó todo), pero hay que enterarse: si pasa
        seguido, el ticket no alcanza para el volumen del día."""
        servicio = ServicioFalso(
            ResultadoListado(nuevas=50, listadas=50, completo=True), pendientes=50
        )
        servicio.cuota_agotada = True

        codigo = await _correr(servicio)

        assert servicio.cierre is not None
        assert servicio.cierre["status"] == "ok"
        assert codigo == 1

    async def test_pendientes_por_errores_de_red_no_son_un_fallo(self):
        """La cola las retoma mañana; marcar la ejecución como fallida todos los
        días que Mercado Público tenga 504 volvería inútil el aviso."""
        servicio = ServicioFalso(
            ResultadoListado(nuevas=0, listadas=10, completo=True), pendientes=0
        )

        assert await _correr(servicio) == 0


class TestCorridasColgadasYSolapadas:
    """Un Remove en Railway o un proceso muerto dejan la fila en `running` para
    siempre (16-sep-2026). Y una corrida lanzada a mano puede solaparse con la
    programada: dos corridas sobre la misma cola gastan el doble de cuota."""

    async def test_cierra_las_colgadas_mas_viejas_que_el_timeout_y_corre(self):
        servicio = ServicioFalso(ResultadoListado(listadas=10, completo=True))
        servicio.corridas_en_curso = [_hace(horas=30)]

        codigo = await _correr(servicio, _args(timeout_minutos=360))

        assert servicio.corridas_en_curso == []
        assert servicio.inicio_registrado
        assert codigo == 0

    async def test_se_niega_si_hay_otra_corrida_reciente(self):
        servicio = ServicioFalso(ResultadoListado(listadas=10, completo=True))
        servicio.corridas_en_curso = [_hace(horas=1)]

        codigo = await _correr(servicio, _args(timeout_minutos=360))

        assert codigo == 1
        assert not servicio.inicio_registrado
        assert servicio.ventana_pedida is None

    async def test_con_forzar_cierra_la_reciente_y_corre(self):
        servicio = ServicioFalso(ResultadoListado(listadas=10, completo=True))
        servicio.corridas_en_curso = [_hace(horas=1)]

        codigo = await _correr(servicio, _args(timeout_minutos=360, forzar=True))

        assert servicio.corridas_en_curso == []
        assert servicio.inicio_registrado
        assert codigo == 0


def _hace(*, horas: float) -> datetime:
    from app.shared.datetime_utils import utc_now_naive

    return utc_now_naive() - timedelta(hours=horas)


class TestTramos:
    """Plan 305: la ventana nocturna se lista por tramos y cada uno mueve el cursor.

    Antes la ventana era una sola, y si la corrida vencía el tope al vaciar la
    cola, el cursor no avanzaba aunque el listado hubiera venido completo. Del
    2026-10-06 al 10-12 eso dejó el cursor detenido una semana.
    """

    def test_parte_la_ventana_en_tramos_contiguos(self):
        desde = datetime(2026, 10, 1)
        hasta = desde + timedelta(hours=15)

        tramos = partir_en_tramos(desde, hasta, timedelta(hours=6))

        assert tramos == [
            (desde, desde + timedelta(hours=6)),
            (desde + timedelta(hours=6), desde + timedelta(hours=12)),
            (desde + timedelta(hours=12), hasta),
        ]

    async def test_cada_tramo_completo_cierra_su_fila_en_ok(self):
        servicio = ServicioFalso(ResultadoListado(listadas=5, completo=True))

        codigo = await _correr(servicio, _args(tramo_horas=6))

        tramos = servicio.cierres_de("tramo")
        assert len(tramos) == 4  # la ventana del doble es de 24 h
        assert all(c["status"] == "ok" for c in tramos)
        assert codigo == 0

    async def test_un_tramo_incompleto_corta_los_siguientes(self):
        servicio = ServicioFalso(ResultadoListado(listadas=5, completo=True))
        servicio.tramos_incompletos = {1}

        codigo = await _correr(servicio, _args(tramo_horas=6))

        assert len(servicio.ventanas_pedidas) == 2
        assert [c["status"] for c in servicio.cierres_de("tramo")] == [
            "ok",
            "partial",
        ]
        assert servicio.cierre["kind"] == "nocturna"
        assert servicio.cierre["status"] == "partial"
        assert codigo == 1

    async def test_la_corrida_entera_tiene_su_fila_y_se_cierra_al_final(self):
        servicio = ServicioFalso(ResultadoListado(listadas=5, completo=True))

        await _correr(servicio, _args(tramo_horas=6))

        assert servicio.inicios[0][0] == "nocturna"
        assert servicio.cierres[-1]["kind"] == "nocturna"
        assert servicio.cierres[-1]["listed"] == 20

    async def test_los_anexos_se_aplican_despues_de_cerrar_cada_tramo(self):
        doc = DocumentoOficialDTO(mp_document_id=1, nombre="Bases.pdf")
        servicio = ServicioFalso(
            ResultadoListado(listadas=1, completo=True, documentos={"A": [doc]})
        )
        cierres_al_llamar: list[int] = []

        async def aplicar_anexos(listas) -> int:
            cierres_al_llamar.append(len(servicio.cierres_de("tramo")))
            return 1

        async def contar(*_) -> int:
            return 0

        await sincronizar(
            _args(tramo_horas=12),
            servicio,
            contar=contar,
            aplicar_anexos=aplicar_anexos,
        )

        assert cierres_al_llamar == [1, 2]


class TestVaciadoNocturno:
    async def test_vacia_las_nuevas_y_despues_reintenta_lo_que_fallo_antes(self):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=3)
        intentos: list[int] = []
        # Una fila que falló antes de la corrida, que la pasada de reintentos
        # resuelve en la primera ronda.
        por_reintentar = [1]

        async def contar(modo=ModoCola.TODAS, antes_de=None) -> int:
            if modo is ModoCola.REINTENTOS:
                return por_reintentar.pop() if por_reintentar else 0
            return servicio.pendientes

        await sincronizar(
            _args(),
            servicio,
            contar=contar,
            fijar_intentos=intentos.append,
        )

        modos = [m for m, _ in servicio.pasadas]
        assert modos[0] is ModoCola.NUEVAS
        assert ModoCola.REINTENTOS in modos
        antes_de = next(a for m, a in servicio.pasadas if m is ModoCola.REINTENTOS)
        assert antes_de is not None
        # 3 intentos HTTP al vaciar, 1 en la pasada de reintentos.
        assert intentos == [3, 1]

    async def test_guarda_las_peticiones_de_la_corrida(self):
        servicio = ServicioFalso(ResultadoListado(completo=True))

        async def contar(modo=ModoCola.TODAS, antes_de=None) -> int:
            return 0

        await sincronizar(_args(), servicio, contar=contar, peticiones=lambda: 77)

        assert servicio.cierre["requests"] == 77


class TestModoFrecuente:
    """Cada 2 h: solo vacía las nuevas, sin listar ni tocar el cursor."""

    async def _frecuente(self, servicio: ServicioFalso, **extra) -> int:
        async def contar(modo=ModoCola.TODAS, antes_de=None) -> int:
            return servicio.pendientes

        return await vaciar_frecuente(_args(), servicio, contar=contar, **extra)

    async def test_no_lista_y_registra_una_corrida_frecuente(self):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=4)

        codigo = await self._frecuente(servicio, peticiones=lambda: 9)

        assert servicio.ventanas_pedidas == []
        assert servicio.inicios[0][0] == "frecuente"
        # No `ok`: la versión anterior lee el cursor de cualquier `ok` sin mirar
        # el tipo, y esta fila tiene la ventana en "ahora".
        assert servicio.cierre["status"] == "vaciada"
        assert servicio.cierre["processed"] == 4
        assert servicio.cierre["requests"] == 9
        assert [m for m, _ in servicio.pasadas] == [ModoCola.NUEVAS]
        assert codigo == 0

    async def test_usa_dos_intentos_por_detalle(self):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=1)
        intentos: list[int] = []

        await self._frecuente(servicio, fijar_intentos=intentos.append)

        assert intentos == [2]

    async def test_si_la_nocturna_sigue_corriendo_sale_con_0_sin_hacer_nada(
        self, capsys
    ):
        """Es esperable: la nocturna puede seguir vaciando la cola a las 08:00."""
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=4)
        servicio.corridas_en_curso = [_hace(horas=2)]

        codigo = await self._frecuente(servicio)

        assert codigo == 0
        assert servicio.pasadas == []
        assert "otra corrida" in capsys.readouterr().out

    async def test_no_cierra_como_colgada_una_nocturna_de_hace_dos_horas(self):
        """El corte de colgadas es el tope de la nocturna, no el de la frecuente."""
        servicio = ServicioFalso(ResultadoListado(completo=True))
        servicio.corridas_en_curso = [_hace(horas=2)]

        await self._frecuente(servicio)

        assert servicio.corridas_en_curso == [servicio.corridas_en_curso[0]]

    async def test_cuota_agotada_sale_con_1(self):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=4)
        servicio.cuota_agotada = True

        assert await self._frecuente(servicio) == 1

    async def test_si_vence_el_tope_cierra_su_fila(self):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=4)

        async def colgada(*args, **kwargs):
            await asyncio.sleep(10)

        servicio.process_unprocessed_tenders = colgada  # type: ignore[method-assign]

        codigo = await con_timeout(
            self._frecuente(servicio), segundos=0.05, codigo_al_vencer=0
        )

        assert codigo == 0
        assert servicio.cierre["kind"] == "frecuente"
        assert servicio.cierre["status"] == "failed"


class TestElegirModo:
    def test_la_corrida_de_las_seis_utc_es_la_nocturna(self):
        assert elegir_modo(datetime(2026, 10, 13, 6, 3), hora_nocturna=6) == "nocturna"

    def test_el_resto_son_frecuentes(self):
        assert elegir_modo(datetime(2026, 10, 13, 8, 1), hora_nocturna=6) == "frecuente"
        assert elegir_modo(datetime(2026, 10, 13, 4, 0), hora_nocturna=6) == "frecuente"


class TestRetencion:
    """La nocturna poda la cola una vez por semana, al final y aislado."""

    async def _correr_con_purga(self, servicio: ServicioFalso, purgar) -> int:
        async def contar(*_) -> int:
            return 0

        return await sincronizar(_args(), servicio, contar=contar, purgar=purgar)

    async def test_poda_despues_de_cerrar_la_corrida(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True))
        cierres_al_podar: list[int] = []

        async def purgar() -> int:
            cierres_al_podar.append(len(servicio.cierres_de("nocturna")))
            return 12

        codigo = await self._correr_con_purga(servicio, purgar)

        assert cierres_al_podar == [1]
        assert "12 filas viejas" in capsys.readouterr().out
        assert codigo == 0

    async def test_si_falla_la_corrida_sale_igual(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True))

        async def purgar() -> int:
            raise RuntimeError("sin base")

        codigo = await self._correr_con_purga(servicio, purgar)

        assert codigo == 0
        assert "AVISO" in capsys.readouterr().out


class TestLlamadasDeEmbeddings:
    async def test_la_nocturna_guarda_las_llamadas_de_embeddings(self):
        servicio = ServicioFalso(ResultadoListado(completo=True))

        async def contar(*_) -> int:
            return 0

        await sincronizar(_args(), servicio, contar=contar, embeddings=lambda: 31)

        assert servicio.cierre["embedding_calls"] == 31

    async def test_la_frecuente_tambien(self):
        servicio = ServicioFalso(ResultadoListado(completo=True))

        async def contar(*_) -> int:
            return 0

        await vaciar_frecuente(_args(), servicio, contar=contar, embeddings=lambda: 5)

        assert servicio.cierre["embedding_calls"] == 5


def _resumen(salida: str) -> dict:
    import json

    [linea] = [x for x in salida.splitlines() if x.startswith("RESUMEN ")]
    return json.loads(linea.removeprefix("RESUMEN "))


class TestLineaDeResumen:
    async def test_la_nocturna_resume_tramos_vaciado_y_api(self, capsys):
        servicio = ServicioFalso(
            ResultadoListado(listadas=5, completo=True), pendientes=2
        )

        async def contar(*_) -> int:
            return servicio.pendientes

        codigo = await sincronizar(
            _args(tramo_horas=12),
            servicio,
            contar=contar,
            metricas=lambda: {"detalle": {"peticiones": 9}},
            embeddings=lambda: 4,
        )

        resumen = _resumen(capsys.readouterr().out)
        assert resumen["cron"] == "ingesta"
        assert resumen["modo"] == "nocturna"
        assert resumen["tramos"] == {"ok": 2, "partial": 0}
        assert resumen["listadas"] == 10
        assert resumen["procesadas"] == 2
        assert resumen["embeddings"] == 4
        assert resumen["api"] == {"detalle": {"peticiones": 9}}
        assert resumen["codigo"] == codigo

    async def test_la_frecuente_tambien(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=3)

        async def contar(*_) -> int:
            return servicio.pendientes

        await vaciar_frecuente(_args(), servicio, contar=contar, metricas=lambda: {})

        resumen = _resumen(capsys.readouterr().out)
        assert (resumen["modo"], resumen["procesadas"]) == ("frecuente", 3)

    async def test_si_vence_el_tope_tambien_resume(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=4)

        async def colgada(*args, **kwargs):
            await asyncio.sleep(10)

        servicio.process_unprocessed_tenders = colgada  # type: ignore[method-assign]

        async def contar(*_) -> int:
            return servicio.pendientes

        await con_timeout(
            vaciar_frecuente(_args(), servicio, contar=contar, metricas=lambda: {}),
            segundos=0.05,
            codigo_al_vencer=0,
        )

        assert _resumen(capsys.readouterr().out)["cancelada"] is True


class TestCuentaParcialAlVencerElTope:
    """Si vence el tope, la corrida registra lo que alcanzó a procesar.

    El 2026-10-14 la frecuente de las 16:06 procesó ~2.300 licitaciones antes
    de vencer el tope, y tanto su fila como su RESUMEN decían 0.
    """

    async def test_la_frecuente_registra_lo_procesado_antes_del_tope(self, capsys):
        servicio = ServicioFalso(ResultadoListado(completo=True), pendientes=5)
        llamadas = {"n": 0}

        async def procesa_y_se_cuelga(*args, **kwargs):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                servicio.pendientes = 2
                return ResultadoProceso(procesadas=3)
            await asyncio.sleep(10)

        servicio.process_unprocessed_tenders = procesa_y_se_cuelga  # type: ignore[method-assign]

        async def contar(*_) -> int:
            return servicio.pendientes

        await con_timeout(
            vaciar_frecuente(_args(), servicio, contar=contar, metricas=lambda: {}),
            segundos=0.1,
            codigo_al_vencer=0,
        )

        assert servicio.cierre["status"] == "failed"
        assert servicio.cierre["processed"] == 3
        assert _resumen(capsys.readouterr().out)["procesadas"] == 3
