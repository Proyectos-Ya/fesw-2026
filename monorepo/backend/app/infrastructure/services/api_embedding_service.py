"""Embeddings servidos por una API externa en vez de un modelo en proceso.

Existe por una restricción de despliegue: BGE-M3 cargado con sentence-transformers
son ~938 MB de RAM y ~13 s de arranque, y en Railway la RAM se paga por GB al mes.
El proveedor sirve el mismo modelo, así que los vectores son intercambiables con los
que ya están indexados en Qdrant —esa compatibilidad es la razón de no elegir otro
proveedor con otro modelo, aunque fuera más barato.

Hay dos dialectos porque los proveedores no hablan el mismo protocolo:

- **DeepInfra** expone el dialecto OpenAI: `{"input": [...]}` y respuesta
  `{"data": [{"index": 0, "embedding": [...]}]}`.
- **Hugging Face** sirve BGE-M3 por `feature-extraction`: `{"inputs": [...]}` y
  respuesta como array de arrays plano, sin índices. Su ruta `/v1/embeddings`
  devuelve 404 para este modelo (verificado el 28 de agosto de 2026).

Lo común —partir en tandas, normalizar, no tragarse errores— vive en la base.
"""

import asyncio
import math
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.application.services.embedding_service import IEmbeddingService

# Tope de textos por petición. Los proveedores acotan el tamaño del lote y la
# ingesta masiva manda miles de licitaciones de una vez.
DEFAULT_BATCH_SIZE = 64

# Generoso a propósito: un lote grande de textos largos tarda, y cortar la
# conexión a mitad de camino significa reintentar el lote entero.
DEFAULT_TIMEOUT_SECONDS = 60.0

# Intentos por tanda, incluido el primero. El cold start del proveedor —el
# modelo lleva rato dormido y la primera petición se pasa del timeout o
# responde 503— es esperable, no excepcional: sin reintentos se propagaba
# hasta el endpoint y el usuario veía un 500 al crear su empresa.
MAX_INTENTOS = 3

# Espera antes del primer reintento; se duplica en cada vuelta.
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0


def _es_reintentable(exc: Exception) -> bool:
    """Distingue "volvé a intentar" de "así no vas a lograr nada".

    Insistir sobre un 401 o un 400 sólo alarga el fallo y esconde la causa.
    """
    # TransportError cubre timeouts, conexiones rechazadas y DNS que no resuelve.
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        codigo = exc.response.status_code
        return codigo == 429 or 500 <= codigo < 600
    return False


class ApiEmbeddingService(IEmbeddingService, ABC):
    """Base común a todos los proveedores. No se instancia directamente."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str = "BAAI/bge-m3",
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._batch_size = max(1, batch_size)
        self._timeout = timeout
        self._retry_backoff = retry_backoff_seconds

    # --- Lo que cambia por proveedor ---

    @abstractmethod
    def _url(self) -> str: ...

    @abstractmethod
    def _cuerpo(self, tanda: list[str]) -> dict[str, Any]: ...

    @abstractmethod
    def _extraer(self, respuesta: Any, tanda: list[str]) -> list[list[float]]:
        """Saca los vectores de la respuesta, en el mismo orden que `tanda`."""

    def _cabeceras(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    # --- Lo común ---

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectores: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            for inicio in range(0, len(texts), self._batch_size):
                tanda = texts[inicio : inicio + self._batch_size]
                vectores.extend(await self._embed_tanda_con_reintentos(cliente, tanda))
        return vectores

    async def _embed_tanda_con_reintentos(
        self, cliente: httpx.AsyncClient, tanda: list[str]
    ) -> list[list[float]]:
        for intento in range(1, MAX_INTENTOS + 1):
            try:
                return await self._embed_tanda(cliente, tanda)
            except Exception as exc:
                # El último intento y los errores definitivos se propagan tal
                # cual: quien llama necesita ver la causa real, no un envoltorio.
                if intento == MAX_INTENTOS or not _es_reintentable(exc):
                    raise
                await asyncio.sleep(self._retry_backoff * 2 ** (intento - 1))
        raise AssertionError("inalcanzable")  # pragma: no cover

    async def _embed_tanda(
        self, cliente: httpx.AsyncClient, tanda: list[str]
    ) -> list[list[float]]:
        respuesta = await cliente.post(
            self._url(), headers=self._cabeceras(), json=self._cuerpo(tanda)
        )
        # Sin esto un 401 o un 429 devolverían una lista vacía y la ingesta
        # seguiría como si nada, dejando licitaciones sin vector en el índice.
        respuesta.raise_for_status()

        crudos = self._extraer(respuesta.json(), tanda)
        if len(crudos) != len(tanda):
            raise ValueError(
                f"El proveedor devolvió {len(crudos)} vectores para {len(tanda)} textos."
            )
        return [_normalizar(v) for v in crudos]


class DeepInfraEmbeddingService(ApiEmbeddingService):
    """Dialecto OpenAI. Sirve para cualquier proveedor compatible."""

    def _url(self) -> str:
        return f"{self._base_url}/embeddings"

    def _cuerpo(self, tanda: list[str]) -> dict[str, Any]:
        return {"model": self._model_name, "input": tanda, "encoding_format": "float"}

    def _extraer(self, respuesta: Any, tanda: list[str]) -> list[list[float]]:
        datos = respuesta.get("data", [])
        # Se ordena por `index` y no se confía en el orden de la lista: la API lo
        # publica precisamente porque no garantiza el orden de llegada. Ignorarlo
        # asocia cada texto al vector de otro, sin que nada falle.
        return [d["embedding"] for d in sorted(datos, key=lambda d: d["index"])]


class HuggingFaceEmbeddingService(ApiEmbeddingService):
    """Endpoint de feature-extraction de Hugging Face Inference Providers.

    Devuelve un array de arrays plano, sin índices ni envoltorio: el orden de la
    respuesta ES el de la entrada, y no hay forma de verificarlo. Por eso la
    comprobación de cantidad de la base es la única red que queda.
    """

    def _url(self) -> str:
        return (
            f"{self._base_url}/hf-inference/models/{self._model_name}"
            "/pipeline/feature-extraction"
        )

    def _cuerpo(self, tanda: list[str]) -> dict[str, Any]:
        # `truncate` evita un 413 con las bases técnicas largas: BGE-M3 acepta
        # 8192 tokens y por encima de eso el servidor rechaza en vez de recortar.
        return {"inputs": tanda, "normalize": True, "truncate": True}

    def _extraer(self, respuesta: Any, tanda: list[str]) -> list[list[float]]:
        if not isinstance(respuesta, list):
            raise ValueError(
                f"Se esperaba una lista de vectores y llegó {type(respuesta).__name__}."
            )
        for vector in respuesta:
            # Un array de tres niveles significa que el modelo respondió con un
            # embedding por token en vez de uno por texto. Promediarlos daría un
            # vector plausible y silenciosamente distinto al del modo local.
            if not isinstance(vector, list) or (vector and isinstance(vector[0], list)):
                raise ValueError(
                    "La respuesta no es una lista plana de vectores: el modelo "
                    "devolvió embeddings por token, no por texto."
                )
        return respuesta


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
