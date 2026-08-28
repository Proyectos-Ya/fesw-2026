"""Elección entre modelos locales y APIs externas para embedding y reranker.

Los modelos locales (BGE-M3 con sentence-transformers, BGE-Reranker en ONNX) no
caben en el free tier de Railway: ~4,3 GB y ~588 MB de caché respectivamente. La
alternativa es delegarlos a un proveedor externo que sirva *los mismos* modelos,
para no invalidar lo ya indexado en Qdrant.

El riesgo que cubren estos tests: elegir el modo API sin credencial. Eso no falla
al arrancar, falla en la primera consulta del primer usuario —y para el embedding
significa además vectores basura escritos en el índice.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {
    "postgres_password": "x",
    "gemini_api_key": "x",
    "gemini_model": "x",
    "mercado_publico_api_key": "x",
    "jwt_secret_key": "K" * 32,
}


def _construir(**extra) -> Settings:
    return Settings(_env_file=None, **BASE, **extra)  # type: ignore[arg-type,call-arg]


class TestProveedorPorDefecto:
    def test_por_defecto_ambos_son_locales(self):
        """El compose local no debe empezar a gastar créditos de una API."""
        s = _construir()
        assert s.embedding_provider == "local"
        assert s.reranker_provider == "local"

    def test_solo_acepta_local_o_api(self):
        with pytest.raises(ValidationError):
            _construir(embedding_provider="deepinfra")


class TestCredencialesObligatoriasEnModoApi:
    def test_embedding_en_modo_api_exige_la_key_de_deepinfra(self):
        with pytest.raises(ValidationError, match="EMBEDDING_API_KEY"):
            _construir(embedding_provider="deepinfra")

    def test_reranker_en_modo_api_exige_la_key_de_pinecone(self):
        with pytest.raises(ValidationError, match="PINECONE_API_KEY"):
            _construir(reranker_provider="pinecone")

    def test_en_modo_api_con_credencial_construye(self):
        s = _construir(
            embedding_provider="deepinfra",
            embedding_api_key="dp-secreto",
            reranker_provider="pinecone",
            pinecone_api_key="pc-secreto",
        )
        assert s.embedding_provider == "deepinfra"
        assert s.reranker_provider == "pinecone"

    def test_una_key_vacia_no_cuenta_como_credencial(self):
        """`EMBEDDING_API_KEY=` sin rellenar es el error de plantilla habitual."""
        with pytest.raises(ValidationError, match="EMBEDDING_API_KEY"):
            _construir(embedding_provider="huggingface", embedding_api_key="   ")

    def test_en_modo_local_no_se_exige_ninguna_credencial(self):
        """Nadie que trabaje en local debería necesitar cuentas de terceros."""
        s = _construir()
        assert s.embedding_api_key is None
        assert s.pinecone_api_key is None

    def test_los_proveedores_son_independientes(self):
        """Embedding por API y reranker local es una combinación legítima."""
        s = _construir(embedding_provider="huggingface", embedding_api_key="hf")
        assert s.embedding_provider == "huggingface"
        assert s.reranker_provider == "local"
