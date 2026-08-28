import asyncio
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


# Cliente HTTP de Mercado Público (ChileCompra V2) para interactuar con la API
def _iso_8601(momento: datetime) -> str:
    """Formato que documenta la guía para los rangos de fecha: 2026-04-01T12:00:00Z.

    Se normaliza a UTC antes de formatear: mandar una hora local con el sufijo Z
    desplazaría la ventana varias horas sin que nada avisara.
    """
    if momento.tzinfo is not None:
        momento = momento.astimezone(UTC)
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


class MercadoPublicoClient:
    def __init__(self, api_key: str, espera_base: float = 1.0):
        self.api_key = api_key
        # Factor de la espera exponencial entre reintentos. Se inyecta para que
        # los tests no duerman de verdad.
        self._espera_base = espera_base
        self.base_url = "https://api2.mercadopublico.cl/v2/compra-agil"

    # Obtiene el listado de cambios recientes en base a una ventana de tiempo (en milisegundos)
    async def get_tenders(
        self,
        from_date: datetime,
        to_date: datetime,
        quantity: int,
        *,
        por_publicacion: bool = False,
        estado: str | None = None,
    ) -> list[dict[str, Any]]:
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
        headers = {"ticket": self.api_key}
        # Calculamos la ventana de tiempo en milisegundos
        delta = to_date - from_date
        time_window_ms = int(delta.total_seconds() * 1000)
        if time_window_ms <= 0:
            time_window_ms = 86400000  # Por defecto 24 horas si el delta no es positivo

        # 50 es el máximo que acepta la API, pero medido tarda ~21 s por página y
        # su gateway corta cerca de los 30: el 504 aparece de forma
        # intermitente. Con 20 la respuesta baja a unos pocos segundos y es
        # estable. Son más llamadas al endpoint de listado, pero ese cuesta una
        # petición por página frente a una por licitación en el de detalle, así
        # que el impacto en la cuota es marginal.
        api_page_size = 20
        all_items: list[dict[str, Any]] = []
        current_page = 1

        async with httpx.AsyncClient() as client:
            while len(all_items) < quantity:
                params: dict[str, Any] = {
                    "tamano_pagina": api_page_size,
                    "numero_pagina": current_page,
                }
                if por_publicacion:
                    params["publicado_desde"] = _iso_8601(from_date)
                    params["publicado_hasta"] = _iso_8601(to_date)
                else:
                    params["ttl_cambio_ms"] = time_window_ms
                if estado:
                    params["estado"] = estado
                try:
                    print(
                        f"[API MP] Consultando página {current_page} (listado de cambios) a {self.base_url}..."
                    )
                    response = await self._get_con_reintentos(client, headers, params)
                    if response is None:
                        # Agotados los reintentos. Se corta, pero avisando: antes
                        # un 5xx pasajero detenía la paginación en silencio y la
                        # ingesta parecía haber terminado bien.
                        print(
                            f"[API MP] Página {current_page} no respondió tras varios "
                            "intentos. Se detiene la paginación con "
                            f"{len(all_items)} licitaciones listadas."
                        )
                        break
                    if response.status_code == 429:
                        # Llega aquí solo tras agotar los reintentos: un 429
                        # pasajero ya se reintentó dentro de _get_con_reintentos.
                        print(
                            "[API MP] Cuota agotada (429 tras varios reintentos). "
                            f"Se detiene la paginación con {len(all_items)} "
                            "licitaciones listadas."
                        )
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
                    break
                except Exception as e:
                    print(
                        f"[Error MP] Falla inesperada en página {current_page} al listar licitaciones: {e}"
                    )
                    break

        return all_items[:quantity]

    async def _get_con_reintentos(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
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
                    self.base_url, headers=headers, params=params, timeout=60.0
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
        headers = {"ticket": self.api_key}
        detail_url = f"{self.base_url}/{id}"
        intentos = 4

        async with httpx.AsyncClient() as client:
            for intento in range(1, intentos + 1):
                ultimo = intento == intentos
                try:
                    response = await client.get(
                        detail_url, headers=headers, timeout=30.0
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
