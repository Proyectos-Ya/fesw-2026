import asyncio
from datetime import datetime
from typing import Any, cast

import httpx


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

        api_page_size = 50  # Usamos el tamaño máximo permitido por request (50) para optimizar llamadas
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
                    response = await client.get(
                        self.base_url, headers=headers, params=params, timeout=30.0
                    )
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

    # Obtiene el detalle crudo de una licitación específica
    async def get_tender_detail(self, id: str) -> dict[str, Any]:
        headers = {"ticket": self.api_key}
        detail_url = f"{self.base_url}/{id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(detail_url, headers=headers, timeout=15.0)
                response.raise_for_status()
                detail_envelope = cast(dict[str, Any], response.json())
                return cast(dict[str, Any], detail_envelope.get("payload", {}))
            except httpx.HTTPStatusError as http_err:
                print(
                    f"[HTTP Error MP] Error al obtener detalle de {id}: {http_err.response.status_code}"
                )
                return {}
            except Exception as e:
                print(f"[Error MP] Falla inesperada al obtener detalle de {id}: {e}")
                return {}
