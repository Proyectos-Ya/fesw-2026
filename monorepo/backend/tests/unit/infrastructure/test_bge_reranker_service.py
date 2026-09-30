import os
import sys
from unittest.mock import ANY, MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

# Stubbing dependencies en sys.modules para permitir importar el servicio sin instalar dependencias pesadas
sys.modules.setdefault("transformers", MagicMock())
sys.modules.setdefault("onnxruntime", MagicMock())
sys.modules.setdefault("huggingface_hub", MagicMock())

from app.infrastructure.services.bge_reranker_service import (  # noqa: E402
    BgeRerankerService,
)


@pytest.fixture
def mock_tokenizer() -> MagicMock:
    tokenizer = MagicMock()
    # Mockea el retorno de la tokenización
    # Un par por llamada: el servicio puntúa cada candidato por separado.
    tokenizer.return_value = {
        "input_ids": np.array([[1, 2, 3]]),
        "attention_mask": np.array([[1, 1, 1]]),
        "token_type_ids": np.array([[0, 0, 0]]),
    }
    return tokenizer


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    # Logit de cada candidato, en el orden en que se evalúan (uno por llamada)
    session.run.side_effect = [[np.array([[2.0]])], [np.array([[-1.0]])]]
    return session


@pytest.mark.anyio
async def test_bge_reranker_initialization_and_rerank(
    mock_tokenizer: MagicMock, mock_session: MagicMock
) -> None:
    # Comprueba la inicialización correcta del modelo ONNX y el cálculo de afinidad de rerank con Platt Scaling.
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

        service = BgeRerankerService(temperature=1.0, bias=1.5)

        # Valida que se inicialice con el modelo correcto en la capa de infraestructura
        mock_at.from_pretrained.assert_called_once_with(
            "onnx-community/bge-reranker-v2-m3-ONNX"
        )
        # Solo se baja la variante configurada: el repositorio publica el mismo
        # modelo en ocho precisiones que suman 8,3 GB.
        mock_sd.assert_called_once_with(
            repo_id="onnx-community/bge-reranker-v2-m3-ONNX",
            allow_patterns=["onnx/model_quantized.onnx", "*.json"],
        )

        # Validamos con la misma concatenación de ruta usada en la clase concreta
        expected_path = os.path.join("/fake/model/dir", "onnx", "model_quantized.onnx")
        mock_is.assert_called_once_with(
            expected_path,
            sess_options=ANY,
            providers=["CPUExecutionProvider"],
        )

        # Ejecuta el re-ranking para 2 candidatos con un límite de M = 1
        c1, c2 = uuid4(), uuid4()
        candidates = [(c1, "doc 1"), (c2, "doc 2")]

        results = await service.rerank("query text", candidates, limit=1)

        # Valida que se tokenice el query contra cada documento candidato, un par
        # por llamada (ver test_el_puntaje_de_un_par_no_depende_de_los_demas_candidatos)
        assert [c.args[0] for c in mock_tokenizer.call_args_list] == [
            [["query text", "doc 1"]],
            [["query text", "doc 2"]],
        ]
        assert mock_tokenizer.call_args.kwargs == {
            "padding": True,
            "truncation": True,
            "return_tensors": "np",
            "max_length": 512,
        }

        # Valida que los logits se conviertan a probabilidades con Sigmoide Platt Scaling y se ordene/recorte
        # Sigmoide((2.0 + 1.5) / 1.0) = Sigmoide(3.5) = 0.97067
        # Sigmoide((-1.0 + 1.5) / 1.0) = Sigmoide(0.5) = 0.622459
        assert len(results) == 1
        assert results[0][0] == c1
        assert pytest.approx(results[0][1], rel=1e-3) == 0.97067


class _TokenizadorFalso:
    """Devuelve una fila por par, con el largo del documento como único token útil."""

    def __call__(self, pairs, **_kwargs):
        ids = np.array([[len(doc)] for _query, doc in pairs])
        return {"input_ids": ids, "attention_mask": np.ones_like(ids)}


class _SesionDependienteDelLote:
    """Imita la cuantización INT8 dinámica del ONNX real.

    La escala de las activaciones se calcula sobre el lote completo, así que el
    logit de un par cambia según qué otros pares se evalúan con él. Aquí se
    simula restando la media del lote: mismo par, distinto lote, distinto logit.
    """

    def run(self, _outputs, feed):
        base = feed["input_ids"][:, 0].astype(float)
        return [(base - base.mean() / 2.0).reshape(-1, 1)]


def _servicio_con(tokenizer, session) -> BgeRerankerService:
    service = BgeRerankerService.__new__(BgeRerankerService)
    service.tokenizer = tokenizer
    service.session = session
    service.temperature = 1.0
    service.bias = 0.0
    return service


@pytest.mark.anyio
async def test_el_puntaje_de_un_par_no_depende_de_los_demas_candidatos() -> None:
    """El ranking puntúa ~50 candidatas juntas y el cálculo a pedido una sola.

    Con el modelo cuantizado, el mismo par salía 0,35 solo y 0,44 dentro de un
    lote de 50: la ficha y el dashboard mostraban porcentajes distintos para la
    misma licitación. Cada par tiene que puntuarse por separado.
    """
    service = _servicio_con(_TokenizadorFalso(), _SesionDependienteDelLote())
    objetivo = uuid4()
    otros = [(uuid4(), "x" * n) for n in (5, 40, 90)]

    solo = dict(await service.rerank("q", [(objetivo, "abc")], limit=1))
    en_lote = dict(await service.rerank("q", [(objetivo, "abc"), *otros], limit=4))

    assert en_lote[objetivo] == pytest.approx(solo[objetivo])
