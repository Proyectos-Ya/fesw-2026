"""Re-ranking servido por una API externa en vez de un modelo ONNX en proceso.

Misma razón que `ApiEmbeddingService`: la variante INT8 del reranker son ~588 MB
de caché, que sumados a BGE-M3 no caben en el free tier de Railway. El proveedor
sirve el mismo BGE-Reranker-v2-M3, así que el criterio de orden es el mismo.

Diferencia importante con `BgeRerankerService`: **no** se aplica la calibración
Platt (`reranker_temperature`, `reranker_bias`). Esos parámetros se ajustaron
sobre los logits crudos que produce el archivo ONNX cuantizado; la API devuelve
un score de relevancia ya normalizado y aplicarle encima esa sigmoide lo deforma.
"""

from uuid import UUID

import httpx

from app.application.services.reranker_service import IRerankerService

DEFAULT_TIMEOUT_SECONDS = 30.0


class ApiRerankerService(IRerankerService):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.pinecone.io",
        model_name: str = "bge-reranker-v2-m3",
        api_version: str = "2025-04",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._api_version = api_version
        self._timeout = timeout

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
            ordenados.append((candidates[posicion][0], float(item["score"])))

        return ordenados[:limit]
