import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

import httpx


class ErrorTransitorioMercadoPublico(Exception):
    """Falla pasajera de la API: el dato existe, pero ahora no se pudo traer.

    Se distingue del detalle vacío porque el servicio de ingesta reacciona
    distinto: un detalle vacío marca la licitación como procesada, un fallo
    pasajero la deja en la cola para el próximo intento.
    """


class CuotaAgotadaError(ErrorTransitorioMercadoPublico):
    """429: se acabaron las peticiones del día. Insistir solo gasta más."""


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
    """Formato que documenta la guía para los rangos de fecha: 2026-04-01T12:00:00Z.

    Se normaliza a UTC antes de formatear: mandar una hora local con el sufijo Z
    desplazaría la ventana varias horas sin que nada avisara.
    """
    if momento.tzinfo is not None:
        momento = momento.astimezone(UTC)
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


# 50 es el máximo que acepta la API, pero medido tarda ~21 s por página y su
# gateway corta cerca de los 30: el 504 aparece de forma intermitente. Con 20 la
# respuesta baja a unos pocos segundos y es estable. Son más llamadas al endpoint
# de listado, pero ese cuesta una petición por página frente a una por licitación
# en el de detalle, así que el impacto en la cuota es marginal.
TAMANO_PAGINA = 20

# Ventana por defecto cuando el delta no es positivo.
VENTANA_POR_DEFECTO_MS = 86400000


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
        ventana_ms = int((to_date - from_date).total_seconds() * 1000)
        if ventana_ms <= 0:
            ventana_ms = VENTANA_POR_DEFECTO_MS
        params["ttl_cambio_ms"] = ventana_ms
    if estado:
        params["estado"] = estado
    return params


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
    ) -> ListadoLicitaciones:
        """Lista licitaciones en una ventana de tiempo.

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
        current_page = 1
        # Optimista: solo se baja a False si la paginación se corta antes de
        # haber visto la última página que la API declara.
        completo = True

        async with httpx.AsyncClient() as client:
            while len(all_items) < quantity:
                params = _params_ventana(
                    from_date,
                    to_date,
                    por_publicacion=por_publicacion,
                    estado=estado,
                    numero_pagina=current_page,
                )
                try:
                    print(
                        f"[API MP] Consultando página {current_page} (listado de cambios) a {self.base_url}..."
                    )
                    response = await self._get_con_reintentos(client, params)
                    if response is None:
                        # Agotados los reintentos. Se corta, pero avisando: antes
                        # un 5xx pasajero detenía la paginación en silencio y la
                        # ingesta parecía haber terminado bien.
                        print(
                            f"[API MP] Página {current_page} no respondió tras varios "
                            "intentos. Se detiene la paginación con "
                            f"{len(all_items)} licitaciones listadas."
                        )
                        completo = False
                        break
                    if response.status_code == 429:
                        # Llega aquí solo tras agotar los reintentos: un 429
                        # pasajero ya se reintentó dentro de _get_con_reintentos.
                        print(
                            "[API MP] Cuota agotada (429 tras varios reintentos). "
                            f"Se detiene la paginación con {len(all_items)} "
                            "licitaciones listadas."
                        )
                        completo = False
                        break
                    response.raise_for_status()

                    envelope = cast(dict[str, Any], response.json())
                    payload = cast(dict[str, Any], envelope.get("payload", {})) or {}
                    items = cast(list[dict[str, Any]], payload.get("items", [])) or []

                    if not items:
                        break

                    all_items.extend(items)

                    paginacion = payload.get("paginacion", {}) or {}
                    total_pages = paginacion.get("total_paginas", 1)
                    if current_page >= total_pages:
                        break

                    current_page += 1

                    # Pequeño delay para no saturar la API entre páginas de listado
                    await asyncio.sleep(0.5)

                except httpx.HTTPStatusError as http_err:
                    print(
                        f"[HTTP Error MP] Error en página {current_page} al listar licitaciones: {http_err.response.status_code}"
                    )
                    completo = False
                    break
                except Exception as e:
                    print(
                        f"[Error MP] Falla inesperada en página {current_page} al listar licitaciones: {e}"
                    )
                    completo = False
                    break

        # El `while` termina solo cuando ya se juntaron `quantity` items, y en
        # ese caso quedan páginas sin mirar: el corte lo puso el llamador con su
        # tope, no la API diciendo que no hay más.
        if len(all_items) >= quantity:
            completo = False

        return ListadoLicitaciones(items=all_items[:quantity], completo=completo)

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
        intentos: int = 4,
    ) -> httpx.Response | None:
        """GET al listado, agotando un ticket antes de pasar al siguiente."""
        while True:
            respuesta = await self._get_con_un_ticket(client, params, intentos)
            agotado = respuesta is not None and respuesta.status_code == 429
            if agotado and self._rotar_ticket():
                continue
            return respuesta

    async def _get_con_un_ticket(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
        intentos: int = 4,
    ) -> httpx.Response | None:
        """GET al listado, reintentando ante fallas pasajeras del servidor.

        La API falla de dos formas transitorias:

        - **5xx.** Devuelve 504 cuando la consulta tarda de su lado, y 500
          ("Servicio no disponible") sin más. Rendirse al primero descarta
          licitaciones que sí están disponibles.
        - **429.** La versión anterior lo trataba como terminal, siguiendo la
          guía de la API, que manda esperar al día siguiente. Medido el 28 de
          agosto de 2026, eso no se sostiene: la API aplica un balde de tokens
          de capacidad pequeña que se recarga en segundos, y aparecen 429
          sueltos entre respuestas correctas. Cortando al primero, una carga
          inicial de horas no llega nunca al final.

        Un 429 que sobrevive a todos los reintentos sí se devuelve: ahí la cuota
        se agotó de verdad y el llamador debe parar.
        """
        for intento in range(1, intentos + 1):
            try:
                respuesta = await client.get(
                    self.base_url,
                    headers=self._cabeceras(),
                    params=params,
                    timeout=60.0,
                )
                if respuesta.status_code < 500 and respuesta.status_code != 429:
                    return respuesta
                if respuesta.status_code == 429 and intento == intentos:
                    # Agotados los reintentos: se devuelve para que el llamador
                    # distinga "cuota agotada" de "el servidor no respondió".
                    return respuesta
                motivo = f"HTTP {respuesta.status_code}"
            except (httpx.TimeoutException, httpx.TransportError) as e:
                motivo = type(e).__name__

            if intento < intentos:
                espera = self._espera_base * (2**intento)
                print(
                    f"[API MP] {motivo} en el listado. Reintento {intento}/{intentos - 1} "
                    f"en {espera}s..."
                )
                if espera:
                    await asyncio.sleep(espera)
        return None

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
        intentos = 4

        async with httpx.AsyncClient() as client:
            for intento in range(1, intentos + 1):
                ultimo = intento == intentos
                try:
                    response = await client.get(
                        detail_url, headers=self._cabeceras(), timeout=30.0
                    )
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    # La licitación está: fue la conexión la que falló.
                    if ultimo:
                        raise ErrorTransitorioMercadoPublico(
                            f"{type(e).__name__} al pedir el detalle de {id} "
                            f"tras {intentos} intentos."
                        ) from e
                    motivo = type(e).__name__
                else:
                    if response.status_code == 429:
                        if ultimo:
                            raise CuotaAgotadaError(
                                f"Cuota agotada al pedir el detalle de {id} "
                                f"tras {intentos} intentos."
                            )
                        motivo = "HTTP 429"
                    elif response.status_code >= 500:
                        if ultimo:
                            raise ErrorTransitorioMercadoPublico(
                                f"HTTP {response.status_code} al pedir el detalle "
                                f"de {id} tras {intentos} intentos."
                            )
                        motivo = f"HTTP {response.status_code}"
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
                    f"Reintento {intento}/{intentos - 1} en {espera}s..."
                )
                if espera:
                    await asyncio.sleep(espera)

        # Inalcanzable: el último intento siempre devuelve o levanta.
        raise ErrorTransitorioMercadoPublico(f"Sin respuesta para el detalle de {id}.")
