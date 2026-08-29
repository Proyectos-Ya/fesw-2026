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

        # Solo los ids: las magnitudes las transforma la recalibración, y lo que
        # este test cuida es a qué candidata queda pegado cada score.
        assert [tid for tid, _ in resultado] == [ID_C, ID_A, ID_B]
        assert [s for _, s in resultado] == sorted(
            (s for _, s in resultado), reverse=True
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_devuelve_el_score_en_la_escala_del_modo_local(self):
        """Pinecone entrega sigmoid(logit); el modo local, sigmoid((logit+b)/T).

        Pasar el valor crudo no es neutro: quien lo consume lo trata como si
        estuviera calibrado. `final_score` pondera el reranker al 50% y de ahí
        salen el porcentaje que ve el usuario y el umbral con el que decide
        recibir alertas. Sin recalibrar, los mismos datos dan un tercio del
        puntaje en producción que en local, y las alertas dejan de dispararse.

        El valor esperado se midió contra el reranker local el 28 de agosto de
        2026: Pinecone dio 0,04751 donde el ONNX INT8 daba 0,2802.
        """
        respx.post(URL).mock(return_value=_respuesta([(0, 0.04751419)]))

        ((_, score),) = await _servicio().rerank("x", CANDIDATAS[:1], limit=1)

        assert score == pytest.approx(0.2692, abs=1e-4)

    @respx.mock
    @pytest.mark.asyncio
    async def test_la_recalibracion_conserva_el_orden(self):
        """Es monótona: no puede reordenar lo que el proveedor ya ordenó."""
        respx.post(URL).mock(
            return_value=_respuesta([(0, 0.9), (1, 0.05), (2, 0.0001)])
        )

        scores = [s for _, s in await _servicio().rerank("x", CANDIDATAS, limit=3)]

        assert scores == sorted(scores, reverse=True)

    @respx.mock
    @pytest.mark.asyncio
    async def test_los_extremos_no_revientan_al_invertir_la_sigmoide(self):
        """Un 0 o un 1 exactos dan logit infinito: hay que acotarlos."""
        respx.post(URL).mock(return_value=_respuesta([(0, 0.0), (1, 1.0)]))

        scores = [s for _, s in await _servicio().rerank("x", CANDIDATAS[:2], limit=2)]

        assert all(0.0 <= s <= 1.0 for s in scores)
        # El 0.0 llegó en la posición 0 y el 1.0 en la 1, y el orden se respeta.
        assert scores[0] < scores[1]

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
