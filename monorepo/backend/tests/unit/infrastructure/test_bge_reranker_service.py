import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

# Stubbing dependencies en sys.modules para permitir importar el servicio sin instalar dependencias pesadas
sys.modules.setdefault("transformers", MagicMock())
sys.modules.setdefault("onnxruntime", MagicMock())
sys.modules.setdefault("huggingface_hub", MagicMock())

from app.infrastructure.services.bge_reranker_service import BgeRerankerService


@pytest.fixture
def mock_tokenizer() -> MagicMock:
    tokenizer = MagicMock()
    # Mockea el retorno de la tokenización
    tokenizer.return_value = {
        "input_ids": np.array([[1, 2, 3], [4, 5, 6]]),
        "attention_mask": np.array([[1, 1, 1], [1, 1, 1]]),
        "token_type_ids": np.array([[0, 0, 0], [0, 0, 0]]),
    }
    return tokenizer


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    # Mockea la salida de la sesión de inferencia de ONNX (logits de coincidencia)
    session.run.return_value = [np.array([[2.0], [-1.0]])]
    return session


@pytest.mark.anyio
async def test_bge_reranker_initialization_and_rerank(
    mock_tokenizer: MagicMock, mock_session: MagicMock
) -> None:
    # Comprueba la inicialización correcta del modelo ONNX y el cálculo de afinidad de rerank en español.
    _bge = "app.infrastructure.services.bge_reranker_service"

    # Patch local de transformers y onnxruntime ya que se importan tardíamente dentro del constructor
    with (
        patch("transformers.AutoTokenizer") as mock_at,
        patch(f"{_bge}.snapshot_download") as mock_sd,
        patch("onnxruntime.InferenceSession") as mock_is,
        patch(f"{_bge}.os.path.exists") as mock_exists,
    ):
        mock_at.from_pretrained.return_value = mock_tokenizer
        mock_sd.return_value = "/fake/model/dir"
        mock_exists.return_value = True
        mock_is.return_value = mock_session

        service = BgeRerankerService()

        # Valida que se inicialice con el modelo correcto en la capa de infraestructura
        mock_at.from_pretrained.assert_called_once_with(
            "onnx-community/bge-reranker-v2-m3-ONNX"
        )
        mock_sd.assert_called_once_with(
            repo_id="onnx-community/bge-reranker-v2-m3-ONNX"
        )
        
        # Validamos con la misma concatenación de ruta usada en la clase concreta
        expected_path = os.path.join("/fake/model/dir", "onnx", "model.onnx")
        mock_is.assert_called_once_with(
            expected_path,
            providers=["CPUExecutionProvider"],
        )

        # Ejecuta el re-ranking para 2 candidatos con un límite de M = 1
        c1, c2 = uuid4(), uuid4()
        candidates = [(c1, "doc 1"), (c2, "doc 2")]

        results = await service.rerank("query text", candidates, limit=1)

        # Valida que se tokenice el query contra cada documento candidato
        mock_tokenizer.assert_called_once_with(
            [["query text", "doc 1"], ["query text", "doc 2"]],
            padding=True,
            truncation=True,
            return_tensors="np",
            max_length=512,
        )

        # Valida que los logits se conviertan a probabilidades con Sigmoide y se ordene/recorte
        # Sigmoide(2.0) = 0.880797
        # Sigmoide(-1.0) = 0.268941
        assert len(results) == 1
        assert results[0][0] == c1
        assert pytest.approx(results[0][1], rel=1e-3) == 0.880797
