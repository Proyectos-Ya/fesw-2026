"""Re-ranking delegado a Pinecone, sirviendo el mismo BGE-Reranker-v2-M3.

Solo se cubren los fallos que no se notan desde afuera: un reranker mal
implementado no lanza errores, devuelve un orden distinto. Y un orden malo se
confunde con "el modelo no acertó".
"""

import json
from uuid import uuid4

import httpx
import pytest
import respx

from app.infrastructure.services.api_reranker_service import ApiRerankerService

URL = "https://api.pinecone.io/rerank"

ID_A, ID_B, ID_C = uuid4(), uuid4(), uuid4()
CANDIDATAS = [(ID_A, "obra de pavimentación"), (ID_B, "servicio de aseo"), (ID_C, "suministro de computadores")]


def _servicio() -> ApiRerankerService:
    return ApiRerankerService(api_key="pc-secreto")


def _respuesta(pares: list[tuple[int, float]]) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"index": i, "score": s} for i, s in pares]})


class TestCorrespondenciaDeResultados:
    @respx.mock
    @pytest.mark.asyncio
    async def test_asocia_cada_score_a_la_candidata_correcta(self):
        """El `index` apunta a la posición en la lista enviada, no al orden de llegada.

        Interpretarlo mal devuelve licitaciones reales con scores de otras: el
        listado se ve perfectamente normal y está completamente equivocado.
        """
        respx.post(URL).mock(return_value=_respuesta([(2, 0.9), (0, 0.5), (1, 0.1)]))

        resultado = await _servicio().rerank("computadores", CANDIDATAS, limit=3)

        assert resultado == [(ID_C, 0.9), (ID_A, 0.5), (ID_B, 0.1)]

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_aplica_la_calibracion_platt(self):
        """temperature y bias se ajustaron sobre los logits crudos del ONNX INT8.

        Pinecone devuelve un score ya normalizado; aplicarle encima la sigmoide
        calibrada lo deforma. El score tiene que pasar tal cual.
        """
        respx.post(URL).mock(return_value=_respuesta([(0, 0.42)]))

        (_, score), = await _servicio().rerank("x", CANDIDATAS[:1], limit=1)

        assert score == 0.42

    @respx.mock
    @pytest.mark.asyncio
    async def test_respeta_el_limite(self):
        respx.post(URL).mock(return_value=_respuesta([(0, 0.9), (1, 0.5)]))

        ruta = respx.calls
        resultado = await _servicio().rerank("x", CANDIDATAS, limit=2)

        assert len(resultado) == 2
        assert json.loads(ruta.last.request.content)["top_n"] == 2


class TestFallosDelProveedor:
    @respx.mock
    @pytest.mark.asyncio
    async def test_un_error_se_propaga(self):
        """Devolver la lista sin ordenar se vería igual que un reranker que no acertó."""
        respx.post(URL).mock(return_value=httpx.Response(429, json={"error": "rate limit"}))

        with pytest.raises(httpx.HTTPStatusError):
            await _servicio().rerank("x", CANDIDATAS, limit=3)

    @respx.mock
    @pytest.mark.asyncio
    async def test_sin_candidatas_no_llama_a_la_api(self):
        ruta = respx.post(URL).mock(return_value=_respuesta([]))

        assert await _servicio().rerank("x", [], limit=3) == []
        assert not ruta.called
