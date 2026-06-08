import asyncio
import os
from uuid import UUID

from huggingface_hub import snapshot_download
import numpy as np

from app.application.services.reranker_service import IRerankerService


class BgeRerankerService(IRerankerService):
    """
    Implementación del servicio de re-ranking usando BGE-Reranker-v2-M3 en formato ONNX.
    """

    def __init__(self, model_name: str = "onnx-community/bge-reranker-v2-m3-ONNX") -> None:
        # Importaciones tardías para evitar fallas durante la carga de módulos si faltan dependencias pesadas
        import onnxruntime as ort
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Descargamos el modelo desde Hugging Face usando huggingface_hub
        model_dir = snapshot_download(repo_id=model_name)

        # Buscamos el archivo ONNX en el directorio descargado
        possible_paths = [
            os.path.join(model_dir, "onnx", "model.onnx"),
            os.path.join(model_dir, "onnx", "model_quantized.onnx"),
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

        self.session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

    async def rerank(
        self,
        query_text: str,
        candidates: list[tuple[UUID, str]],
        limit: int,
    ) -> list[tuple[UUID, float]]:
        """
        Calcula el score de similitud cruzada entre la consulta y los candidatos,
        y devuelve los top M resultados.
        """
        if not candidates:
            return []

        # Formateamos pares de [query, document]
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

        # Preparamos las entradas para el session.run de ONNX
        input_feed = {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
        }

        # Si el modelo espera token_type_ids lo incluimos
        if "token_type_ids" in inputs:
            input_feed["token_type_ids"] = inputs["token_type_ids"]

        # Ejecutamos la inferencia ONNX en un executor asíncrono
        logits = await loop.run_in_executor(
            None,
            lambda: self.session.run(["logits"], input_feed)[0],
        )

        # Aplicamos la función Sigmoide a los logits para obtener probabilidades/scores (0 a 1)
        if len(logits.shape) > 1 and logits.shape[1] > 0:
            logits = logits[:, 0]

        scores = 1.0 / (1.0 + np.exp(-logits))
        scores_list = scores.tolist()

        # Mapeamos los resultados de vuelta a (tender_id, score)
        ranked_candidates = [
            (candidates[i][0], float(scores_list[i]))
            for i in range(len(candidates))
        ]

        # Ordenamos los candidatos de mayor a menor score
        ranked_candidates.sort(key=lambda x: x[1], reverse=True)

        # Devolvemos los top M candidatos
        return ranked_candidates[:limit]
