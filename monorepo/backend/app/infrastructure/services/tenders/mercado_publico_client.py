import asyncio
from datetime import datetime
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
class MercadoPublicoClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api2.mercadopublico.cl/v2/compra-agil"

    # Obtiene el listado de cambios recientes en base a una ventana de tiempo (en milisegundos)
    async def get_tenders(
        self, from_date: datetime, to_date: datetime, quantity: int
    ) -> list[dict[str, Any]]:
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
                params = {
                    "ttl_cambio_ms": time_window_ms,
                    "tamano_pagina": api_page_size,
                    "numero_pagina": current_page,
                }
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
                        print(
                            "[API MP] Cuota agotada (Error 429). Deteniendo paginación."
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
        intentos: int = 3,
    ) -> httpx.Response | None:
        """GET al listado, reintentando ante fallas pasajeras del servidor.

        La API devuelve 504 de forma intermitente cuando la consulta tarda
        demasiado de su lado. No es un error nuestro ni de cuota, así que
        rendirse al primero descarta licitaciones que sí están disponibles.
        Un 429 se devuelve tal cual: ahí no hay que insistir, la cuota se agotó.
        """
        for intento in range(1, intentos + 1):
            try:
                respuesta = await client.get(
                    self.base_url, headers=headers, params=params, timeout=60.0
                )
                if respuesta.status_code == 429 or respuesta.status_code < 500:
                    return respuesta
                motivo = f"HTTP {respuesta.status_code}"
            except (httpx.TimeoutException, httpx.TransportError) as e:
                motivo = type(e).__name__

            if intento < intentos:
                espera = 2**intento
                print(
                    f"[API MP] {motivo} en el listado. Reintento {intento}/{intentos - 1} "
                    f"en {espera}s..."
                )
                await asyncio.sleep(espera)
        return None

    # Obtiene el detalle crudo de una licitación específica
    async def get_tender_detail(self, id: str) -> dict[str, Any]:
        """Detalle de una licitación. `{}` solo si de verdad no hay nada que traer.

        Un 429, un 5xx o un timeout **no** devuelven `{}`: levantan
        `ErrorTransitorioMercadoPublico`. Devolverlos como vacío hacía que la
        ingesta los tomara por "esta licitación no tiene detalle" y la marcara
        procesada para siempre, perdiéndola sin posibilidad de reintento.
        """
        headers = {"ticket": self.api_key}
        detail_url = f"{self.base_url}/{id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(detail_url, headers=headers, timeout=15.0)
                if response.status_code == 429:
                    raise CuotaAgotadaError(
                        f"Cuota diaria agotada al pedir el detalle de {id}."
                    )
                if response.status_code >= 500:
                    raise ErrorTransitorioMercadoPublico(
                        f"HTTP {response.status_code} al pedir el detalle de {id}."
                    )
                response.raise_for_status()
                detail_envelope = cast(dict[str, Any], response.json())
                return cast(dict[str, Any], detail_envelope.get("payload", {}))
            except (httpx.TimeoutException, httpx.TransportError) as e:
                # La licitación está: fue la conexión la que falló.
                raise ErrorTransitorioMercadoPublico(
                    f"{type(e).__name__} al pedir el detalle de {id}."
                ) from e
            except httpx.HTTPStatusError as http_err:
                # 4xx que no es 429: la licitación no está disponible y volver a
                # pedirla daría lo mismo.
                print(
                    f"[HTTP Error MP] Error al obtener detalle de {id}: {http_err.response.status_code}"
                )
                return {}
            except ErrorTransitorioMercadoPublico:
                raise
            except Exception as e:
                print(f"[Error MP] Falla inesperada al obtener detalle de {id}: {e}")
                return {}
