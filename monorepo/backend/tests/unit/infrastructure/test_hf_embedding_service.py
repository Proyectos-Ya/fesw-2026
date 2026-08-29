"""Adaptador del formato de Hugging Face, que no es el dialecto OpenAI.

HF sirve BGE-M3 por `feature-extraction` y devuelve un **array de arrays plano**:
sin envoltorio `data`, sin `index`, sin clave `embedding`. Su ruta `/v1/embeddings`
responde 404 para este modelo (verificado el 28 de agosto de 2026).

Solo se cubren los fallos silenciosos. La ausencia de `index` es lo que hace este
adaptador más frágil que el de DeepInfra: el orden de la respuesta *es* el de la
entrada y no hay forma de verificarlo, así que la comprobación de cantidad es la
única red que queda.
"""

import httpx
import pytest
import respx

from app.infrastructure.services.api_embedding_service import (
    HuggingFaceEmbeddingService,
)

URL = (
    "https://router.huggingface.co/hf-inference/models/BAAI/bge-m3"
    "/pipeline/feature-extraction"
)


def _servicio(**extra) -> HuggingFaceEmbeddingService:
    return HuggingFaceEmbeddingService(
        api_key="hf-secreto", base_url="https://router.huggingface.co", **extra
    )


class TestFormatoDeHuggingFace:
    @respx.mock
    @pytest.mark.asyncio
    async def test_lee_la_lista_plana_en_el_orden_de_entrada(self):
        respx.post(URL).mock(
            return_value=httpx.Response(200, json=[[1.0, 0.0], [0.0, 1.0]])
        )

        assert await _servicio().embed(["uno", "dos"]) == [[1.0, 0.0], [0.0, 1.0]]

    @respx.mock
    @pytest.mark.asyncio
    async def test_manda_inputs_y_no_input(self):
        """La clave del cuerpo difiere de la de OpenAI; con `input` responde 400."""
        ruta = respx.post(URL).mock(return_value=httpx.Response(200, json=[[1.0, 0.0]]))

        await _servicio().embed(["hola"])

        import json

        cuerpo = json.loads(ruta.calls.last.request.content)
        assert cuerpo["inputs"] == ["hola"]
        assert "input" not in cuerpo

    @respx.mock
    @pytest.mark.asyncio
    async def test_normaliza_igual_que_el_modo_local(self):
        respx.post(URL).mock(return_value=httpx.Response(200, json=[[3.0, 4.0]]))

        (vector,) = await _servicio().embed(["hola"])

        assert vector == pytest.approx([0.6, 0.8])


class TestFallosSilenciosos:
    @respx.mock
    @pytest.mark.asyncio
    async def test_falla_si_faltan_vectores(self):
        """Sin `index` que verificar, esta es la única defensa contra el desfase."""
        respx.post(URL).mock(return_value=httpx.Response(200, json=[[1.0, 0.0]]))

        with pytest.raises(ValueError, match="2 textos"):
            await _servicio().embed(["uno", "dos"])

    @respx.mock
    @pytest.mark.asyncio
    async def test_rechaza_embeddings_por_token(self):
        """Un array de tres niveles es un embedding por token, no por texto.

        Promediarlos daría un vector plausible, de la dimensión correcta y
        silenciosamente distinto al que produce el modo local.
        """
        respx.post(URL).mock(
            return_value=httpx.Response(200, json=[[[1.0, 0.0], [0.0, 1.0]]])
        )

        with pytest.raises(ValueError, match="por token"):
            await _servicio().embed(["hola"])

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_error_del_proveedor_se_propaga(self):
        """Quedarse sin crédito en HF no debe dejar licitaciones sin vector."""
        respx.post(URL).mock(return_value=httpx.Response(402, json={"error": "no"}))

        with pytest.raises(httpx.HTTPStatusError):
            await _servicio().embed(["hola"])
