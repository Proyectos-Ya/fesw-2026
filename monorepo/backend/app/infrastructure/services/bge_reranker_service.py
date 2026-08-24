import asyncio
import os
from typing import cast
from uuid import UUID

import numpy as np
from huggingface_hub import snapshot_download

from app.application.services.reranker_service import IRerankerService
from app.config import settings


class BgeRerankerService(IRerankerService):
    """
    Implementación del servicio de re-ranking usando BGE-Reranker-v2-M3 en formato ONNX.
    Optimizado con soporte prioritario para cuantización INT8 y calibración Platt Scaling (bias + temperatura).
    """

    def __init__(
        self,
        model_name: str = "onnx-community/bge-reranker-v2-m3-ONNX",
        onnx_variant: str | None = None,
        temperature: float | None = None,
        bias: float | None = None,
    ) -> None:
        # Importaciones tardías para evitar fallas durante la carga de módulos si faltan dependencias pesadas
        import onnxruntime as ort
        from transformers import AutoTokenizer

        variant = onnx_variant or settings.reranker_onnx_variant
        # La calibración acompaña a la variante: son parámetros de la
        # distribución de logits que produce ese archivo, no del modelo en
        # abstracto. Ver la nota en config.Settings.
        self.temperature = (
            temperature if temperature is not None else settings.reranker_temperature
        )
        self.bias = bias if bias is not None else settings.reranker_bias
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # allow_patterns evita bajar el repositorio completo: publica el mismo
        # modelo en ocho precisiones (fp32, fp16, int8, uint8, q4, q4f16,
        # bnb4...) que suman 8,3 GB, y solo se usa una.
        allow_patterns = [f"onnx/{variant}", "*.json"]
        if variant == "model.onnx":
            # La fp32 es la única que no cabe en un archivo: model.onnx es solo
            # el grafo (0,7 MB) y los pesos viven aparte en model.onnx_data.
            allow_patterns.append("onnx/model.onnx_data")

        model_dir = snapshot_download(repo_id=model_name, allow_patterns=allow_patterns)

        # Se busca primero la variante pedida. El resto de la lista solo cubre
        # cachés antiguas, descargadas antes de que la variante fuera
        # configurable, para no forzar una redescarga innecesaria.
        possible_paths = [
            os.path.join(model_dir, "onnx", variant),
            os.path.join(model_dir, variant),
            os.path.join(model_dir, "onnx", "model_quantized.onnx"),
            os.path.join(model_dir, "onnx", "model.onnx"),
        ]

        onnx_path = None
        for path in possible_paths:
            if os.path.exists(path):
                onnx_path = path
                break

        if not onnx_path:
            raise FileNotFoundError(
                f"No se encontró la variante ONNX '{variant}' en el modelo {model_name}"
            )

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = min(os.cpu_count() or 4, 8)
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        self.session = ort.InferenceSession(
            onnx_path,
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )

    async def rerank(
        self,
        query_text: str,
        candidates: list[tuple[UUID, str]],
        limit: int,
    ) -> list[tuple[UUID, float]]:
        """
        Calcula el score de similitud cruzada entre la consulta y los candidatos,
        aplicando calibración Platt Scaling (bias + temperatura) para secuencias de longitud asimétrica.
        """
        if not candidates:
            return []

        # Formatear pares [query, document]
        pairs = [[query_text, doc_text] for _, doc_text in candidates]

        # Tokenizamos en un executor asíncrono para no bloquear el event loop principal
        loop = asyncio.get_running_loop()
        inputs = await loop.run_in_executor(
            None,
            lambda: self.tokenizer(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="np",
                max_length=512,
            ),
        )

        input_feed = {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
        }

        if "token_type_ids" in inputs:
            input_feed["token_type_ids"] = inputs["token_type_ids"]

        # Ejecutamos la inferencia ONNX en un executor asíncrono
        # `run` está tipado como una unión amplia (ndarray | SparseTensor | ...),
        # pero al pedir la salida "logits" siempre es un ndarray denso.
        logits = cast(
            np.ndarray,
            await loop.run_in_executor(
                None,
                lambda: self.session.run(["logits"], input_feed)[0],
            ),
        )

        if len(logits.shape) > 1 and logits.shape[1] > 0:
            logits = logits[:, 0]

        # Sigmoide con calibración Platt Scaling (bias y temperatura)
        calibrated_logits = (logits + self.bias) / max(self.temperature, 0.1)
        scores = 1.0 / (1.0 + np.exp(-calibrated_logits))
        scores_list = scores.tolist()

        ranked_candidates = [
            (candidates[i][0], float(scores_list[i])) for i in range(len(candidates))
        ]

        ranked_candidates.sort(key=lambda x: x[1], reverse=True)
        return ranked_candidates[:limit]
