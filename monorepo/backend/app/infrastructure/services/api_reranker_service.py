"""Re-ranking servido por una API externa en vez de un modelo ONNX en proceso.

Misma razón que `ApiEmbeddingService`: la variante INT8 del reranker son ~588 MB
de caché, que sumados a BGE-M3 no caben en el free tier de Railway. El proveedor
sirve el mismo BGE-Reranker-v2-M3, así que el criterio de orden es el mismo.

Sobre la calibración: `BgeRerankerService` devuelve
`sigmoid((logit + bias) / temperature)`, mientras que la API entrega
`sigmoid(logit)` a secas. Aplicarle la sigmoide calibrada encima al valor de la
API lo deformaría, pero **dejarlo crudo tampoco sirve**: quien lo consume lo
trata como si estuviera calibrado. `final_score` pondera el reranker al 50%, y
de ahí salen el porcentaje que ve el usuario y el umbral con el que decide
recibir alertas; sin recalibrar, los mismos datos rinden un tercio del puntaje
en producción que en local y las alertas dejan de dispararse.

La solución es el paso intermedio: **invertir la sigmoide para recuperar el
logit** y aplicarle entonces la misma calibración que en local. Verificado el 28
de agosto de 2026 contra el reranker local sobre tres glosas que cubren cuatro
órdenes de magnitud de score: error máximo 0,016, del mismo orden que la
diferencia ya existente entre las variantes INT8 y fp32 del modelo (0,010,
registrada en PENDIENTES 7.1).
"""

import math
from uuid import UUID

import httpx

from app.application.services.reranker_service import IRerankerService
from app.config import settings

DEFAULT_TIMEOUT_SECONDS = 30.0

# Los extremos exactos dan logit infinito al invertir la sigmoide. Se acotan al
# float más cercano que sí es invertible; en la práctica ningún score real llega
# ahí, pero un 0.0 redondeado por el proveedor bastaría para tumbar la búsqueda.
_EPSILON = 1e-12


class ApiRerankerService(IRerankerService):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.pinecone.io",
        model_name: str = "bge-reranker-v2-m3",
        api_version: str = "2025-04",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        temperature: float | None = None,
        bias: float | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._api_version = api_version
        self._timeout = timeout
        # La calibración se comparte con el modo local a propósito: es lo que hace
        # que un mismo par consulta/licitación puntúe igual en los dos entornos.
        self._temperature = (
            temperature if temperature is not None else settings.reranker_temperature
        )
        self._bias = bias if bias is not None else settings.reranker_bias

    async def rerank(
        self,
        query_text: str,
        candidates: list[tuple[UUID, str]],
        limit: int,
    ) -> list[tuple[UUID, float]]:
        if not candidates:
            return []

        documentos = [
            {"id": str(indice), "text": texto}
            for indice, (_, texto) in enumerate(candidates)
        ]

        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            respuesta = await cliente.post(
                f"{self._base_url}/rerank",
                headers={
                    "Api-Key": self._api_key,
                    # La API versiona por header y rechaza las peticiones sin él.
                    "X-Pinecone-API-Version": self._api_version,
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model_name,
                    "query": query_text,
                    "documents": documentos,
                    "top_n": limit,
                    "rank_fields": ["text"],
                    # El texto ya lo tenemos: pedirlo de vuelta solo infla la
                    # respuesta, y en una tanda de candidatas eso pesa.
                    "return_documents": False,
                },
            )
            # Un 429 devolviendo la lista sin ordenar sería indistinguible de un
            # reranker que simplemente no acertó, y nadie lo notaría.
            respuesta.raise_for_status()

        resultados = respuesta.json().get("data", [])
        ordenados: list[tuple[UUID, float]] = []
        for item in resultados:
            posicion = item["index"]
            # El proveedor solo puede devolver posiciones de lo que se le mandó;
            # si devuelve otra cosa, es mejor saberlo acá que servir un id ajeno.
            if not 0 <= posicion < len(candidates):
                raise ValueError(
                    f"El proveedor devolvió el índice {posicion}, fuera de las "
                    f"{len(candidates)} candidatas enviadas."
                )
            ordenados.append(
                (candidates[posicion][0], self._recalibrar(float(item["score"])))
            )

        return ordenados[:limit]

    def _recalibrar(self, score: float) -> float:
        """Lleva `sigmoid(logit)` a la misma escala que produce el modo local.

        Es monótona, así que no puede reordenar lo que el proveedor ya ordenó:
        solo cambia la magnitud.
        """
        p = min(max(score, _EPSILON), 1.0 - _EPSILON)
        logit = math.log(p / (1.0 - p))
        calibrado = (logit + self._bias) / max(self._temperature, 0.1)
        return 1.0 / (1.0 + math.exp(-calibrado))
