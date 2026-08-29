"""Embeddings delegados a DeepInfra, sirviendo el mismo BGE-M3 que la versión local.

Estos tests no tocan la red: `respx` intercepta las llamadas de httpx. Lo que
verifican es el contrato con el que se habla al proveedor, que es justo lo que no
se puede comprobar leyendo el código de la interfaz.
"""

import httpx
import pytest
import respx

from app.infrastructure.services.api_embedding_service import (
    DeepInfraEmbeddingService,
)

URL = "https://api.deepinfra.com/v1/openai/embeddings"


def _servicio(**extra) -> DeepInfraEmbeddingService:
    return DeepInfraEmbeddingService(
        api_key="dp-secreto",
        base_url="https://api.deepinfra.com/v1/openai",
        model_name="BAAI/bge-m3",
        **extra,
    )


def _respuesta(vectores: list[list[float]], desordenada: bool = False) -> httpx.Response:
    datos = [{"index": i, "embedding": v} for i, v in enumerate(vectores)]
    if desordenada:
        datos.reverse()
    return httpx.Response(200, json={"data": datos})


class TestContratoConElProveedor:
    @respx.mock
    @pytest.mark.asyncio
    async def test_manda_el_modelo_los_textos_y_la_credencial(self):
        ruta = respx.post(URL).mock(return_value=_respuesta([[1.0, 0.0]]))

        await _servicio().embed(["hola"])

        pedido = ruta.calls.last.request
        assert pedido.headers["authorization"] == "Bearer dp-secreto"
        import json

        cuerpo = json.loads(pedido.content)
        assert cuerpo["model"] == "BAAI/bge-m3"
        assert cuerpo["input"] == ["hola"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_respeta_el_orden_pedido_y_no_el_de_la_respuesta(self):
        """La API devuelve un `index` por algo: el orden no está garantizado.

        Si se ignora, cada texto queda asociado al vector de otro. Nada falla:
        simplemente el buscador devuelve resultados sin relación con la consulta.
        """
        respx.post(URL).mock(
            return_value=_respuesta([[1.0, 0.0], [0.0, 1.0]], desordenada=True)
        )

        vectores = await _servicio().embed(["primero", "segundo"])

        assert vectores == [[1.0, 0.0], [0.0, 1.0]]

    @respx.mock
    @pytest.mark.asyncio
    async def test_normaliza_los_vectores(self):
        """La versión local usa normalize_embeddings=True; hay que igualarla.

        Con distancia coseno el ranking no cambia, pero los scores crudos sí, y
        hay umbrales calibrados sobre ellos.
        """
        respx.post(URL).mock(return_value=_respuesta([[3.0, 4.0]]))

        (vector,) = await _servicio().embed(["hola"])

        assert vector == pytest.approx([0.6, 0.8])

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_vector_nulo_no_revienta_al_normalizar(self):
        respx.post(URL).mock(return_value=_respuesta([[0.0, 0.0]]))

        assert await _servicio().embed(["hola"]) == [[0.0, 0.0]]


class TestCasosBorde:
    @respx.mock
    @pytest.mark.asyncio
    async def test_sin_textos_no_llama_a_la_api(self):
        ruta = respx.post(URL).mock(return_value=_respuesta([]))

        assert await _servicio().embed([]) == []
        assert not ruta.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_parte_las_tandas_grandes_en_varias_peticiones(self):
        """La ingesta masiva manda miles de textos y el proveedor tiene tope."""
        ruta = respx.post(URL).mock(
            side_effect=lambda pedido: _respuesta(
                [[1.0, 0.0]] * len(__import__("json").loads(pedido.content)["input"])
            )
        )

        vectores = await _servicio(batch_size=2).embed(["a", "b", "c", "d", "e"])

        assert len(vectores) == 5
        assert ruta.call_count == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_un_error_del_proveedor_se_propaga(self):
        """Devolver vectores en cero dejaría basura indexada en Qdrant."""
        respx.post(URL).mock(return_value=httpx.Response(401, json={"error": "no"}))

        with pytest.raises(httpx.HTTPStatusError):
            await _servicio().embed(["hola"])

    @respx.mock
    @pytest.mark.asyncio
    async def test_falla_si_faltan_vectores_en_la_respuesta(self):
        """Menos vectores que textos desalinea todo lo que venga después."""
        respx.post(URL).mock(return_value=_respuesta([[1.0, 0.0]]))

        with pytest.raises(ValueError, match="2 textos"):
            await _servicio().embed(["uno", "dos"])
