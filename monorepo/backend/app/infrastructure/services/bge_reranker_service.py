import asyncio
import os
from uuid import UUID

from huggingface_hub import snapshot_download
import numpy as np

from app.application.services.reranker_service import IRerankerService


class BgeRerankerService(IRerankerService):
    """
    Implementación del servicio de re-ranking usando BGE-Reranker-v2-M3 en formato ONNX.
    Optimizado con soporte prioritario para cuantización INT8 y calibración Platt Scaling (bias + temperatura).
    """

    def __init__(
        self,
        model_name: str = "onnx-community/bge-reranker-v2-m3-ONNX",
        temperature: float = 1.5,
        bias: float = 1.5,
    ) -> None:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        self.temperature = temperature
        self.bias = bias
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Descarga / obtención desde caché local de Hugging Face
        model_dir = snapshot_download(repo_id=model_name)

        # Priorizar archivo cuantizado (INT8) para máxima velocidad en CPU
        possible_paths = [
            os.path.join(model_dir, "onnx", "model_quantized.onnx"),
            os.path.join(model_dir, "onnx", "model.onnx"),
            os.path.join(model_dir, "model_quantized.onnx"),
            os.path.join(model_dir, "model.onnx"),
        ]

        onnx_path = None
        for path in possible_paths:
            if os.path.exists(path):
                onnx_path = path
                break

        if not onnx_path:
            raise FileNotFoundError(
                f"No se encontró el archivo ONNX en el modelo {model_name}"
            )

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = min(os.cpu_count() or 4, 8)
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

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

        logits = await loop.run_in_executor(
            None,
            lambda: self.session.run(["logits"], input_feed)[0],
        )

        if len(logits.shape) > 1 and logits.shape[1] > 0:
            logits = logits[:, 0]

        # Sigmoide con calibración Platt Scaling (bias y temperatura)
        calibrated_logits = (logits + self.bias) / max(self.temperature, 0.1)
        scores = 1.0 / (1.0 + np.exp(-calibrated_logits))
        scores_list = scores.tolist()

        ranked_candidates = [
            (candidates[i][0], float(scores_list[i]))
            for i in range(len(candidates))
        ]

        ranked_candidates.sort(key=lambda x: x[1], reverse=True)
        return ranked_candidates[:limit]
