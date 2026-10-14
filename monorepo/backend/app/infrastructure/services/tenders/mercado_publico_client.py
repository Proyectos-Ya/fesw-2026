import asyncio
import random
import statistics
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx

from app.shared.datetime_utils import CHILE_TZ


class ErrorTransitorioMercadoPublico(Exception):
    """Falla pasajera de la API: el dato existe, pero ahora no se pudo traer.

    Se distingue del detalle vacío porque el servicio de ingesta reacciona
    distinto: un detalle vacío marca la licitación como procesada, un fallo
    pasajero la deja en la cola para el próximo intento.
    """


class CuotaAgotadaError(ErrorTransitorioMercadoPublico):
    """429: se acabaron las peticiones del día. Insistir solo gasta más."""


class PresupuestoAgotadoError(CuotaAgotadaError):
    """La corrida llegó a su máximo de peticiones (`max_peticiones`).

    Es un tope propio, no de la API: el ticket sigue teniendo cuota, así que no
    se rota. Hereda de `CuotaAgotadaError` porque quien la recibe tiene que
    hacer lo mismo, que es dejar de pedir sin cobrarle el intento a la licitación.
    """


@dataclass
class ListadoLicitaciones:
    """Lo que devolvió el listado, y si alcanzó a recorrerlo entero.

    `completo` es False cuando la paginación se cortó antes de tiempo: un 5xx o
    un 429 que sobrevivieron a los reintentos, una página ilegible, o el tope de
    licitaciones que pidió el llamador.

    Existe por el cursor persistente. Sin este dato, una corrida truncada se
    registraba como buena, el cursor avanzaba hasta el final de la ventana, y lo
    que quedó sin listar no se volvía a pedir nunca.
    """

    items: list[dict[str, Any]] = field(default_factory=list)
    completo: bool = True


# Cliente HTTP de Mercado Público (ChileCompra V2) para interactuar con la API
def _iso_8601(momento: datetime) -> str:
    """Formato que documenta la guía para los rangos: 2026-04-01T12:00:00Z.

    **La hora va en hora de Chile, aunque lleve Z.** La API guarda y compara
    hora de pared de Chile con etiqueta UTC (medido el 2026-09-29: la última
    hora real en UTC devolvía 0 publicadas; la misma ventana corrida 3 h hacia
    atrás, 498). Mandar UTC de verdad desplazaba la ventana 3-4 h, y el cron
    nocturno perdía lo publicado en las horas posteriores a cada corrida.

    Un naive se asume UTC, como toda fecha del sistema.
    """
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")


# La API acepta `tamano_pagina` entre **10 y 50** (medido el 2026-09-10: un 1
# devuelve 400 con ese mensaje). Se usa el mínimo porque lo que decide el 504 es
# el tamaño de la página, no el de la ventana. Medido el 2026-10-13 en hora punta
# (18:22-18:43 UTC), una petición por caso sin reintentos:
#
#   10 por página: 6 de 6 respondieron, 13,5 s de media.
#   20 por página: la mitad a dos tercios, ~24 s; el resto, 504 a los ~29 s.
#   50 por página: ninguna.
#
# Una ventana de 15 min fallaba igual que una de 2 h. Con 10 se hacen el doble de
# páginas, pero casi ninguna se reintenta, así que en total son ~30% más
# peticiones y la corrida termina antes. Fuera de hora punta 20 también respondía
# bien; 10 se usa siempre para no depender de la hora.
TAMANO_PAGINA = 10

# Ventana por defecto cuando el delta no es positivo.
VENTANA_POR_DEFECTO_MS = 86400000

# Paciencia del listado ante un 5xx o un timeout. Medido el 2026-10-05: entre las
# 10:00 y las 18:00 (Chile) el gateway devuelve 504 casi cada hora, y con cuatro
# intentos (esperas de 2, 4 y 8 s) una página caída cortaba la paginación
# entera. Seis intentos con tope de 30 s son ~1 min de espera por página en el
# peor caso, más lo que tarde el gateway en cortar cada uno (~30 s): una página
# irrecuperable cuesta unos 4 min, que el tope de 50 min del cron aguanta.
#
# El 429 no usa esto: sus cuatro intentos deciden cuándo rotar de ticket.
INTENTOS_SERVIDOR_LISTADO = 6
INTENTOS_CUOTA = 4
ESPERA_MAXIMA_REINTENTO = 30.0

# Páginas caídas seguidas que se saltan antes de dar la API por caída. Una
# suelta es inestabilidad del gateway y conviene seguir con las siguientes; tres
# seguidas, ya no.
PAGINAS_CAIDAS_SEGUIDAS_MAX = 3


def espera_reintento(
    base: float,
    intento: int,
    *,
    azar: Callable[[], float] = random.random,
) -> float:
    """Segundos antes del reintento siguiente: exponencial, con tope y con azar.

    El azar solo recorta hasta la mitad, para que los crons que coinciden no
    reintenten todos en el mismo instante sin perder del todo la espera.
    """
    bruta = min(ESPERA_MAXIMA_REINTENTO, base * (2**intento))
    return bruta * (0.5 + 0.5 * azar())


def _desfase_chile(momento: datetime) -> timedelta:
    """Cuántas horas va Chile detrás de UTC en ese momento (3 o 4).

    Un naive se asume UTC, como toda fecha del sistema.
    """
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    offset = momento.astimezone(CHILE_TZ).utcoffset() or timedelta(0)
    return -offset


def _params_ventana(
    from_date: datetime,
    to_date: datetime,
    *,
    por_publicacion: bool,
    estado: str | None,
    numero_pagina: int = 1,
) -> dict[str, Any]:
    """Parámetros del listado para una ventana de tiempo.

    Vive fuera de `get_tenders` porque el conteo (`contar`) necesita exactamente
    los mismos. Duplicarlos es la forma de que un día dejen de coincidir y la
    volumetría termine midiendo una ventana distinta de la que se ingesta.

    `ttl_cambio_ms` y `publicado_desde`/`publicado_hasta` son **mutuamente
    excluyentes**: la guía de la API los pone en grupos distintos de parámetros y
    advierte que no se combinan.
    """
    params: dict[str, Any] = {
        "tamano_pagina": TAMANO_PAGINA,
        "numero_pagina": numero_pagina,
    }
    if por_publicacion:
        params["publicado_desde"] = _iso_8601(from_date)
        params["publicado_hasta"] = _iso_8601(to_date)
    else:
        # La API resta el ttl a su "ahora" en UTC y lo compara contra fechas
        # guardadas en hora de Chile, así que la ventana efectiva es el ttl menos
        # el desfase de Chile (medido el 2026-09-29: 3,0 h devolvía 0 cambios y
        # 3,1 h, los últimos seis minutos). Se suma para que la ventana pedida
        # sea la que de verdad se recibe.
        ventana = to_date - from_date
        if ventana <= timedelta(0):
            ventana = timedelta(milliseconds=VENTANA_POR_DEFECTO_MS)
        ventana += _desfase_chile(to_date)
        params["ttl_cambio_ms"] = int(ventana.total_seconds() * 1000)
    if estado:
        params["estado"] = estado
    return params


@dataclass
class _Pagina:
    """Una página del listado ya interpretada (ver `_pedir_pagina`)."""

    numero: int
    estado: str
    items: list[dict[str, Any]] = field(default_factory=list)
    total_paginas: int = 1


class MercadoPublicoClient:
    """Cliente de Compra Ágil, con rotación de tickets.

    La cuota de 10.000 peticiones diarias es del **ticket**, no de la máquina ni
    del proyecto, así que varios tickets suman capacidad. Cuando uno se agota, el
    cliente pasa al siguiente y reintenta.

    **Rotación por agotamiento, no reparto.** La API devuelve 429 por dos motivos
    que no distingue: un balde de tokens que se recarga en segundos, y la cuota
    del día. Rotar recién cuando un 429 sobrevive a los cuatro reintentos acierta
    en los dos casos — si era el balde, el ticket nuevo también responde y no se
    perdió nada; si era la cuota, se pasó a capacidad fresca. Repartir las
    peticiones entre tickets desde el principio, en cambio, gastaría todos a la
    vez y dejaría la ingesta sin margen justo al final.
    """

    def __init__(
        self,
        api_key: str | None = None,
        espera_base: float = 1.0,
        *,
        api_keys: list[str] | None = None,
        intentos_detalle: int = 4,
        max_peticiones: int | None = None,
        concurrencia_listado: int = 1,
    ):
        tickets = [t for t in (api_keys or ([api_key] if api_key else [])) if t]
        if not tickets:
            raise ValueError("MercadoPublicoClient necesita al menos un ticket.")
        self._tickets = tickets
        self._indice = 0
        # Factor de la espera exponencial entre reintentos. Se inyecta para que
        # los tests no duerman de verdad.
        self._espera_base = espera_base
        self.base_url = "https://api2.mercadopublico.cl/v2/compra-agil"
        # Intentos por detalle. Público y mutable: la ingesta usa menos en la
        # pasada de reintentos que al vaciar la cola, con el mismo cliente.
        self.intentos_detalle = intentos_detalle
        # Peticiones hechas, reintentos incluidos. Cada intento gasta cuota del
        # ticket aunque responda 504.
        self.peticiones = 0
        # Tope de la corrida. `None` = sin tope.
        self.max_peticiones = max_peticiones
        # Páginas del listado que se piden a la vez, después de la primera.
        self.concurrencia_listado = max(1, concurrencia_listado)
        # (tipo, resultado, segundos) de cada petición, para `resumen()`.
        self._registros: list[tuple[str, str, float]] = []

    def _anotar(self, tipo: str, resultado: str, inicio: float) -> None:
        self._registros.append((tipo, resultado, time.perf_counter() - inicio))

    def resumen(self) -> dict[str, dict[str, Any]]:
        """Peticiones por tipo, con sus resultados y latencias (plan 305).

        Es lo que cada corrida deja en su línea `RESUMEN` del log: cuántas
        respondieron 200, cuántas 504, cuántas se cortaron por timeout, y cuánto
        tardaron (p50 y p90), por separado el listado y el detalle.
        """
        resumen: dict[str, dict[str, Any]] = {}
        for tipo in ("listado", "detalle"):
            registros = [r for r in self._registros if r[0] == tipo]
            segundos = sorted(r[2] for r in registros)
            por_resultado: dict[str, int] = {}
            for _, resultado, _ in registros:
                por_resultado[resultado] = por_resultado.get(resultado, 0) + 1
            resumen[tipo] = {
                "peticiones": len(registros),
                "por_resultado": por_resultado,
                "p50_s": round(statistics.median(segundos), 1) if segundos else None,
                "p90_s": round(segundos[int(0.9 * (len(segundos) - 1))], 1)
                if segundos
                else None,
            }
        return resumen

    def _contar_peticion(self) -> None:
        """Descuenta una petición del presupuesto, o corta si ya no queda."""
        if self.max_peticiones is not None and self.peticiones >= self.max_peticiones:
            raise PresupuestoAgotadoError(
                f"La corrida llegó a su máximo de {self.max_peticiones} peticiones."
            )
        self.peticiones += 1

    @property
    def api_key(self) -> str:
        """El ticket en uso. Cambia cuando el anterior agota su cuota."""
        return self._tickets[self._indice]

    def _cabeceras(self) -> dict[str, str]:
        """Se construyen por intento, no una vez: el ticket puede haber rotado."""
        return {"ticket": self.api_key}

    def _rotar_ticket(self) -> bool:
        """Pasa al siguiente ticket. False si ya no queda ninguno.

        No vuelve al primero: dentro de una misma corrida, un ticket que agotó su
        cuota no se recupera, y reintentar con él solo gastaría los reintentos
        contra una puerta cerrada.
        """
        if self._indice + 1 >= len(self._tickets):
            return False
        self._indice += 1
        print(
            f"[API MP] Ticket agotado. Se cambia al {self._indice + 1} "
            f"de {len(self._tickets)}."
        )
        return True

    # Obtiene el listado de cambios recientes en base a una ventana de tiempo (en milisegundos)
    async def get_tenders(
        self,
        from_date: datetime,
        to_date: datetime,
        quantity: int,
        *,
        por_publicacion: bool = False,
        estado: str | None = None,
        al_recibir_pagina: Callable[[list[dict[str, Any]]], Awaitable[None]]
        | None = None,
    ) -> ListadoLicitaciones:
        """Lista licitaciones en una ventana de tiempo.

        `al_recibir_pagina` recibe los ítems de cada página antes de pedir la
        siguiente. Sirve para aplicar lo listado a medida que llega: si la
        corrida se corta después, lo de las páginas anteriores ya quedó.

        Por defecto pregunta por lo que **cambió** (`ttl_cambio_ms`), que es lo
        que quiere la sincronización diaria. Con `por_publicacion=True` pregunta
        por lo que se **publicó** en el rango, que es lo que quiere una carga
        inicial: un corpus, no un delta. La guía pone los dos en grupos
        distintos de parámetros y advierte que no se combinan.

        `estado` filtra en el servidor (`publicada`, o varios separados por
        coma), así que las cerradas y desiertas ni siquiera se descargan. Medido:
        sin una ventana de tiempo acompañándolo, la API responde 504.
        """
        all_items: list[dict[str, Any]] = []
        # Optimista: solo se baja a False si la paginación se corta antes de
        # haber visto la última página que la API declara, o si se saltó alguna.
        completo = True

        def params_de(numero: int) -> dict[str, Any]:
            return _params_ventana(
                from_date,
                to_date,
                por_publicacion=por_publicacion,
                estado=estado,
                numero_pagina=numero,
            )

        async with httpx.AsyncClient() as client:
            # La primera va sola: es la que dice cuántas páginas hay. Sin ella no
            # se sabe hasta dónde seguir, así que si cae no se salta: se corta.
            primera = await self._pedir_pagina(client, 1, params_de(1))
            if primera.estado != "ok":
                print(
                    f"[API MP] Página 1 sin respuesta ({primera.estado}). Se "
                    "detiene la paginación con 0 licitaciones listadas."
                )
                return ListadoLicitaciones(items=[], completo=False)
            if not primera.items:
                return ListadoLicitaciones(items=[], completo=True)
            all_items.extend(primera.items)
            if al_recibir_pagina is not None:
                await al_recibir_pagina(primera.items)
            total_pages = primera.total_paginas

            # El resto, por tandas de `concurrencia_listado`. Cada tanda se
            # entrega en orden de página: un código repetido en dos páginas no
            # puede aplicarse con el dato viejo encima del nuevo.
            siguiente = 2
            caidas_seguidas = 0
            seguir = True
            while seguir and siguiente <= total_pages and len(all_items) < quantity:
                tanda = list(
                    range(
                        siguiente,
                        min(siguiente + self.concurrencia_listado, total_pages + 1),
                    )
                )
                paginas = await asyncio.gather(
                    *(self._pedir_pagina(client, n, params_de(n)) for n in tanda)
                )
                for pagina in paginas:
                    if pagina.estado == "caida":
                        # Agotados los reintentos ante 5xx o timeouts. La página
                        # se pierde, pero las siguientes suelen responder.
                        completo = False
                        caidas_seguidas += 1
                        if caidas_seguidas >= PAGINAS_CAIDAS_SEGUIDAS_MAX:
                            print(
                                f"[API MP] {caidas_seguidas} páginas seguidas sin "
                                "responder. Se detiene la paginación con "
                                f"{len(all_items)} licitaciones listadas."
                            )
                            seguir = False
                            break
                        print(
                            f"[API MP] Página {pagina.numero} no respondió tras "
                            "varios intentos. Se salta y se sigue con la siguiente."
                        )
                        continue
                    if pagina.estado != "ok":
                        # Cuota agotada, presupuesto de la corrida o un error que
                        # reintentar no arregla: seguir pidiendo solo gasta más.
                        print(
                            f"[API MP] Página {pagina.numero}: {pagina.estado}. Se "
                            f"detiene la paginación con {len(all_items)} "
                            "licitaciones listadas."
                        )
                        completo = False
                        seguir = False
                        break
                    if not pagina.items:
                        seguir = False
                        break
                    all_items.extend(pagina.items)
                    caidas_seguidas = 0
                    if al_recibir_pagina is not None:
                        await al_recibir_pagina(pagina.items)
                    if len(all_items) >= quantity:
                        seguir = False
                        break
                siguiente += len(tanda)
                if seguir:
                    # Pequeña pausa entre tandas para no saturar la API.
                    await asyncio.sleep(0.5)

        # El `while` termina solo cuando ya se juntaron `quantity` items, y en
        # ese caso quedan páginas sin mirar: el corte lo puso el llamador con su
        # tope, no la API diciendo que no hay más.
        if len(all_items) >= quantity:
            completo = False

        return ListadoLicitaciones(items=all_items[:quantity], completo=completo)

    async def _pedir_pagina(
        self, client: httpx.AsyncClient, numero: int, params: dict[str, Any]
    ) -> "_Pagina":
        """Una página del listado, ya interpretada. Nunca levanta.

        `estado` es `ok`, `caida` (5xx o timeouts tras los reintentos), `cuota`
        (429 tras rotar todos los tickets), `presupuesto` (la corrida llegó a su
        máximo) o `error` (una respuesta que reintentar no arregla).
        """
        print(f"[API MP] Consultando página {numero} (listado) a {self.base_url}...")
        try:
            response = await self._get_con_reintentos(client, params)
        except PresupuestoAgotadoError as e:
            print(f"[API MP] {e}")
            return _Pagina(numero, "presupuesto")
        if response is None:
            return _Pagina(numero, "caida")
        if response.status_code == 429:
            return _Pagina(numero, "cuota")
        if response.status_code >= 400:
            print(f"[HTTP Error MP] Página {numero}: {response.status_code}")
            return _Pagina(numero, "error")
        try:
            envelope = cast(dict[str, Any], response.json())
        except Exception as e:  # noqa: BLE001
            print(f"[Error MP] Página {numero} ilegible: {e}")
            return _Pagina(numero, "error")
        payload = cast(dict[str, Any], envelope.get("payload", {})) or {}
        items = cast(list[dict[str, Any]], payload.get("items", [])) or []
        paginacion = cast(dict[str, Any], payload.get("paginacion", {})) or {}
        total = paginacion.get("total_paginas", 1)
        return _Pagina(numero, "ok", items, total if isinstance(total, int) else 1)

    async def contar(
        self,
        from_date: datetime,
        to_date: datetime,
        *,
        por_publicacion: bool = False,
        estado: str | None = None,
    ) -> int | None:
        """Cuántas licitaciones hay en la ventana, **sin descargarlas**.

        Una sola petición: `paginacion.total_resultados` viene ya en la primera
        página y no depende de haberla recorrido. Es lo que vuelve viable medir
        la volumetría — una serie de 30 días cuesta 30 peticiones de las 10.000
        del ticket, frente a las ~30.000 que costaría listarlas.

        Devuelve `None` cuando **no se pudo saber**: la API no respondió tras los
        reintentos, o la respuesta vino sin ese campo. Es distinto de `0`, que
        significa que la ventana está vacía. Confundirlos convertiría una caída
        de la API en un día sin publicaciones, que es justo el error que una
        serie temporal no perdona.

        Aviso al interpretar el número: un `total_resultados` de exactamente
        10.000 puede ser un tope de la API y no el total real. Ante eso, acotar
        la ventana.
        """
        params = _params_ventana(
            from_date, to_date, por_publicacion=por_publicacion, estado=estado
        )

        async with httpx.AsyncClient() as client:
            response = await self._get_con_reintentos(client, params)

        if response is None or response.status_code != 200:
            return None
        try:
            envelope = cast(dict[str, Any], response.json())
        except Exception as e:
            print(f"[Error MP] Respuesta ilegible al contar la ventana: {e}")
            return None

        payload = cast(dict[str, Any], envelope.get("payload", {})) or {}
        paginacion = cast(dict[str, Any], payload.get("paginacion", {})) or {}
        total = paginacion.get("total_resultados")
        return total if isinstance(total, int) else None

    async def _get_con_reintentos(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
    ) -> httpx.Response | None:
        """GET al listado, agotando un ticket antes de pasar al siguiente."""
        while True:
            respuesta = await self._get_con_un_ticket(client, params)
            agotado = respuesta is not None and respuesta.status_code == 429
            if agotado and self._rotar_ticket():
                continue
            return respuesta

    async def _get_con_un_ticket(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
        intentos_cuota: int = INTENTOS_CUOTA,
        intentos_servidor: int = INTENTOS_SERVIDOR_LISTADO,
    ) -> httpx.Response | None:
        """GET al listado, reintentando ante fallas pasajeras del servidor.

        La API falla de dos formas transitorias, y cada una lleva su propia
        cuenta de intentos:

        - **5xx o timeout.** Devuelve 504 cuando la consulta tarda de su lado, y
          500 ("Servicio no disponible") sin más. En hora punta pasa casi cada
          hora, así que se le tiene paciencia (`INTENTOS_SERVIDOR_LISTADO`).
        - **429.** La versión anterior lo trataba como terminal, siguiendo la
          guía de la API, que manda esperar al día siguiente. Medido el 28 de
          agosto de 2026, eso no se sostiene: la API aplica un balde de tokens
          de capacidad pequeña que se recarga en segundos, y aparecen 429
          sueltos entre respuestas correctas. Sus intentos (`INTENTOS_CUOTA`)
          son los que deciden cuándo rotar de ticket.

        Un 429 que sobrevive a sus intentos sí se devuelve: ahí la cuota se
        agotó de verdad y el llamador debe parar. Un 5xx que sobrevive a los
        suyos devuelve None.
        """
        fallas_cuota = 0
        fallas_servidor = 0
        while True:
            try:
                self._contar_peticion()
                inicio = time.perf_counter()
                try:
                    respuesta = await client.get(
                        self.base_url,
                        headers=self._cabeceras(),
                        params=params,
                        timeout=60.0,
                    )
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    self._anotar("listado", type(e).__name__, inicio)
                    raise
                self._anotar("listado", str(respuesta.status_code), inicio)
                if respuesta.status_code < 500 and respuesta.status_code != 429:
                    return respuesta
                if respuesta.status_code == 429:
                    fallas_cuota += 1
                    if fallas_cuota >= intentos_cuota:
                        # Se devuelve para que el llamador distinga "cuota
                        # agotada" de "el servidor no respondió".
                        return respuesta
                    intento, de = fallas_cuota, intentos_cuota
                else:
                    fallas_servidor += 1
                    if fallas_servidor >= intentos_servidor:
                        return None
                    intento, de = fallas_servidor, intentos_servidor
                motivo = f"HTTP {respuesta.status_code}"
            except (httpx.TimeoutException, httpx.TransportError) as e:
                fallas_servidor += 1
                if fallas_servidor >= intentos_servidor:
                    return None
                intento, de = fallas_servidor, intentos_servidor
                motivo = type(e).__name__

            espera = espera_reintento(self._espera_base, intento)
            print(
                f"[API MP] {motivo} en el listado. Reintento {intento}/{de - 1} "
                f"en {espera:.1f}s..."
            )
            if espera:
                await asyncio.sleep(espera)

    # Obtiene el detalle crudo de una licitación específica
    async def get_tender_detail(self, id: str) -> dict[str, Any]:
        """Detalle de una licitación, agotando un ticket antes de pasar al siguiente.

        `CuotaAgotadaError` sale de acá solo cuando **todos** los tickets se
        agotaron: mientras quede uno, el fallo del anterior es invisible para el
        llamador, que es justo lo que se quiere — la ingesta no tiene por qué
        saber cuántos tickets hay.
        """
        while True:
            try:
                return await self._detalle_con_un_ticket(id)
            except PresupuestoAgotadoError:
                # El tope es de la corrida, no del ticket: rotar no lo arregla.
                raise
            except CuotaAgotadaError:
                if not self._rotar_ticket():
                    raise

    async def _detalle_con_un_ticket(self, id: str) -> dict[str, Any]:
        """Detalle de una licitación. `{}` solo si de verdad no hay nada que traer.

        Un 429, un 5xx o un timeout **no** devuelven `{}`: levantan una excepción.
        Devolverlos como vacío hacía que la ingesta los tomara por "esta
        licitación no tiene detalle" y la marcara procesada para siempre,
        perdiéndola sin posibilidad de reintento.

        Los tres se reintentan con espera creciente antes de rendirse. El 429 en
        particular es pasajero —la API aplica un balde de tokens que se recarga
        en segundos—, y al primero se cortaba la ingesta entera: en una carga
        inicial de horas eso la detiene a los minutos.

        Un 4xx que no sea 429 sí devuelve `{}`: esa licitación no está
        disponible y volver a pedirla daría lo mismo.

        El timeout es de 30 s y no de 15: el detalle tarda ~3,3 s de mediana pero
        se han medido respuestas de 9 s, y un timeout corto convierte una
        respuesta lenta en un reintento innecesario.
        """
        detail_url = f"{self.base_url}/{id}"
        # Dos conteos, como en el listado. Los 5xx y timeouts usan
        # `intentos_detalle`, que cada pasada ajusta para no gastar cuota contra
        # un 504. El 429 tiene el suyo: con 1 o 2 intentos, una ráfaga corta del
        # balde de tokens se tomaba por cuota agotada y cortaba la corrida entera
        # (2026-10-14).
        intentos_servidor = max(1, self.intentos_detalle)
        fallas_servidor = 0
        fallas_cuota = 0

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    self._contar_peticion()
                    inicio = time.perf_counter()
                    try:
                        response = await client.get(
                            detail_url, headers=self._cabeceras(), timeout=30.0
                        )
                    except (httpx.TimeoutException, httpx.TransportError) as e:
                        self._anotar("detalle", type(e).__name__, inicio)
                        raise
                    self._anotar("detalle", str(response.status_code), inicio)
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    # La licitación está: fue la conexión la que falló.
                    fallas_servidor += 1
                    if fallas_servidor >= intentos_servidor:
                        raise ErrorTransitorioMercadoPublico(
                            f"{type(e).__name__} al pedir el detalle de {id} "
                            f"tras {fallas_servidor} intentos."
                        ) from e
                    motivo, intento = type(e).__name__, fallas_servidor
                else:
                    if response.status_code == 429:
                        fallas_cuota += 1
                        if fallas_cuota >= INTENTOS_CUOTA:
                            raise CuotaAgotadaError(
                                f"Cuota agotada al pedir el detalle de {id} "
                                f"tras {fallas_cuota} intentos."
                            )
                        motivo, intento = "HTTP 429", fallas_cuota
                    elif response.status_code >= 500:
                        fallas_servidor += 1
                        if fallas_servidor >= intentos_servidor:
                            raise ErrorTransitorioMercadoPublico(
                                f"HTTP {response.status_code} al pedir el detalle "
                                f"de {id} tras {fallas_servidor} intentos."
                            )
                        motivo = f"HTTP {response.status_code}"
                        intento = fallas_servidor
                    elif response.status_code >= 400:
                        print(
                            f"[HTTP Error MP] Error al obtener detalle de {id}: "
                            f"{response.status_code}"
                        )
                        return {}
                    else:
                        try:
                            envelope = cast(dict[str, Any], response.json())
                            return cast(dict[str, Any], envelope.get("payload", {}))
                        except Exception as e:
                            print(
                                f"[Error MP] Respuesta ilegible en el detalle de "
                                f"{id}: {e}"
                            )
                            return {}

                espera = self._espera_base * (2**intento)
                print(
                    f"[API MP] {motivo} en el detalle de {id}. "
                    f"Reintento {intento} en {espera}s..."
                )
                if espera:
                    await asyncio.sleep(espera)
