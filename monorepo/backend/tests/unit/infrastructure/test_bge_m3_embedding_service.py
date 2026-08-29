from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.services.bge_m3_embedding_service import BgeM3EmbeddingService

_MODULE = "app.infrastructure.services.bge_m3_embedding_service"


def _mock_vectors(n: int, dim: int = 1024) -> MagicMock:
    """Returns a mock whose .tolist() yields n vectors of `dim` floats."""
    mock = MagicMock()
    mock.tolist.return_value = [[0.1] * dim for _ in range(n)]
    return mock


@pytest.fixture
def mock_model():
    with patch(f"{_MODULE}.SentenceTransformer") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def service(mock_model) -> BgeM3EmbeddingService:
    return BgeM3EmbeddingService()


# ---------------------------------------------------------------------------
# Lista vacía — cortocircuito sin llamar al modelo
# ---------------------------------------------------------------------------


async def test_embed_lista_vacia_retorna_vacia(service: BgeM3EmbeddingService) -> None:
    assert await service.embed([]) == []


async def test_embed_lista_vacia_no_llama_encode(
    service: BgeM3EmbeddingService, mock_model: MagicMock
) -> None:
    await service.embed([])

    mock_model.encode.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_embed_retorna_lista_de_vectores(
    service: BgeM3EmbeddingService, mock_model: MagicMock
) -> None:
    mock_model.encode.return_value = _mock_vectors(2)

    resultado = await service.embed(["texto uno", "texto dos"])

    assert len(resultado) == 2
    assert len(resultado[0]) == 1024
    assert len(resultado[1]) == 1024


async def test_embed_un_texto_retorna_un_vector(
    service: BgeM3EmbeddingService, mock_model: MagicMock
) -> None:
    mock_model.encode.return_value = _mock_vectors(1)

    resultado = await service.embed(["texto único"])

    assert len(resultado) == 1


async def test_embed_output_es_lista_de_listas_de_float(
    service: BgeM3EmbeddingService, mock_model: MagicMock
) -> None:
    mock_model.encode.return_value = _mock_vectors(1)

    resultado = await service.embed(["texto"])

    assert isinstance(resultado, list)
    assert isinstance(resultado[0], list)
    assert isinstance(resultado[0][0], float)


# ---------------------------------------------------------------------------
# Delegación correcta al modelo
# ---------------------------------------------------------------------------


async def test_embed_pasa_textos_a_encode(
    service: BgeM3EmbeddingService, mock_model: MagicMock
) -> None:
    textos = ["licitacion de aseo", "contrato de mantención"]
    mock_model.encode.return_value = _mock_vectors(2)

    await service.embed(textos)

    assert mock_model.encode.call_args[0][0] == textos


async def test_embed_usa_normalize_embeddings(
    service: BgeM3EmbeddingService, mock_model: MagicMock
) -> None:
    mock_model.encode.return_value = _mock_vectors(1)

    await service.embed(["texto"])

    assert mock_model.encode.call_args.kwargs.get("normalize_embeddings") is True


def test_constructor_carga_modelo_con_nombre_dado() -> None:
    with patch(f"{_MODULE}.SentenceTransformer") as mock_cls:
        mock_cls.return_value = MagicMock()

        BgeM3EmbeddingService(model_name="BAAI/bge-m3")

        mock_cls.assert_called_once_with("BAAI/bge-m3")
