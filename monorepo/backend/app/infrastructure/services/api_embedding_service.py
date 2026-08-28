"""Embeddings servidos por una API externa en vez de un modelo en proceso.

Existe por una restricción de despliegue: BGE-M3 cargado con sentence-transformers
son ~4,3 GB de caché de modelo, y no cabe en el free tier de Railway. La API sirve
el mismo modelo, así que los vectores son intercambiables con los que ya están
indexados en Qdrant —esa compatibilidad es la razón de no elegir otro proveedor
con otro modelo, aunque fuera más barato.

Habla el dialecto OpenAI de embeddings, que es lo que expone DeepInfra en
`/v1/openai`. Cualquier proveedor compatible sirve cambiando `base_url`.
"""

import math

import httpx

from app.application.services.embedding_service import IEmbeddingService

# Tope de textos por petición. Los proveedores acotan el tamaño del lote y la
# ingesta masiva manda miles de licitaciones de una vez.
DEFAULT_BATCH_SIZE = 64

# Generoso a propósito: un lote grande de textos largos tarda, y cortar la
# conexión a mitad de camino significa reintentar el lote entero.
DEFAULT_TIMEOUT_SECONDS = 60.0


class ApiEmbeddingService(IEmbeddingService):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepinfra.com/v1/openai",
        model_name: str = "BAAI/bge-m3",
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._batch_size = max(1, batch_size)
        self._timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectores: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            for inicio in range(0, len(texts), self._batch_size):
                tanda = texts[inicio : inicio + self._batch_size]
                vectores.extend(await self._embed_tanda(cliente, tanda))
        return vectores

    async def _embed_tanda(
        self, cliente: httpx.AsyncClient, tanda: list[str]
    ) -> list[list[float]]:
        respuesta = await cliente.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model_name,
                "input": tanda,
                "encoding_format": "float",
            },
        )
        # Sin esto un 401 o un 429 devolverían una lista vacía y la ingesta
        # seguiría como si nada, dejando licitaciones sin vector en el índice.
        respuesta.raise_for_status()

        datos = respuesta.json().get("data", [])
        if len(datos) != len(tanda):
            raise ValueError(
                f"El proveedor devolvió {len(datos)} vectores para {len(tanda)} textos."
            )

        # Se ordena por `index` y no se confía en el orden de la lista: la API lo
        # publica precisamente porque no garantiza el orden de llegada. Ignorarlo
        # asocia cada texto al vector de otro, sin que nada falle.
        ordenados = sorted(datos, key=lambda d: d["index"])
        return [_normalizar(d["embedding"]) for d in ordenados]


def _normalizar(vector: list[float]) -> list[float]:
    """Deja el vector de largo 1, como hace `normalize_embeddings=True` en local.

    Con distancia coseno el orden del ranking no cambia, pero los scores crudos
    sí, y hay umbrales calibrados sobre ellos. El vector nulo se devuelve tal
    cual: no tiene dirección que preservar y dividir por cero no ayuda.
    """
    norma = math.sqrt(sum(componente * componente for componente in vector))
    if norma == 0:
        return vector
    return [componente / norma for componente in vector]
