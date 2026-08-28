"""El fallback de embeddings no debe degradarse en silencio en producción.

`MockEmbeddingService` devuelve vectores de puros ceros. Con él la aplicación
arranca, responde y se ve sana, pero toda búsqueda y todo matching dan
resultados sin sentido. Peor: la ingesta escribe esos ceros en Qdrant, y eso no
se arregla corrigiendo la configuración —hay que reindexar.

Antes esto era un `logger.warning` y seguía adelante también fuera de desarrollo.
"""

import pytest

from app.bootstrap import (
    ApiEmbeddingService,
    MockEmbeddingService,
    build_embedding_service,
)
from app.config import settings
from app.infrastructure.services import bge_m3_embedding_service as modulo_local


class _EmbeddingRoto:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("no hay memoria para cargar el modelo")


@pytest.fixture
def embedding_roto(monkeypatch):
    # En el módulo de origen: build_embedding_service lo importa tarde para que
    # la imagen en modo API no necesite sentence-transformers.
    monkeypatch.setattr(modulo_local, "BgeM3EmbeddingService", _EmbeddingRoto)


def test_fuera_de_desarrollo_el_fallo_impide_arrancar(monkeypatch, embedding_roto):
    """Un deploy 'exitoso' que sirve vectores en cero es peor que uno que falla."""
    monkeypatch.setattr(settings, "embedding_provider", "local")
    monkeypatch.setattr(settings, "is_dev", False)

    with pytest.raises(RuntimeError):
        build_embedding_service()


def test_en_desarrollo_el_fallo_cae_al_mock(monkeypatch, embedding_roto):
    """En local, no tener el modelo bajado no debería impedir levantar la API."""
    monkeypatch.setattr(settings, "embedding_provider", "local")
    monkeypatch.setattr(settings, "is_dev", True)

    assert isinstance(build_embedding_service(), MockEmbeddingService)


def test_en_modo_api_no_carga_el_modelo_local(monkeypatch, embedding_roto):
    """Con el proveedor en API, que el modelo local esté roto es irrelevante."""
    monkeypatch.setattr(settings, "embedding_provider", "api")
    monkeypatch.setattr(settings, "deepinfra_api_key", "dp-secreto")

    assert isinstance(build_embedding_service(), ApiEmbeddingService)
