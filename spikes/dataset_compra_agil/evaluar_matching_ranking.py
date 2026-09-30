"""
Script de Evaluación de Matching y Ranking de Licitaciones (Compra Ágil)
Calcula métricas formales de Information Retrieval (NDCG@K, Success@1, MRR, Precision@K, Recall@K)
utilizando:
  1. Ground Truth Real Estricto (Adjudicaciones reales en Mercado Público = Relevancia 2, sin juez)
  2. Simulación de Interacción (Clicks y Visualizaciones = Relevancia 1 con Gemini 3.5 Flash Lite)
  3. Comparación de Estrategias:
     - Estrategia A: Baseline Embedding Puro (Coseno)
     - Estrategia B: Búsqueda Híbrida (Dense + Coincidencia Léxica)
     - Estrategia C: Híbrido + Afinidad Regional Canónica (are_regions_matching)
     - Estrategia D: Pipeline Producción (First-Stage Híbrido + Cross-Encoder Reranker fusionados con RRF)
  4. Pruebas de Significancia Estadística: Wilcoxon pareado con corrección Holm-Bonferroni y Paired Bootstrap (IC 95%).
"""

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import NAMESPACE_DNS, uuid5

# Codificación UTF-8 para Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import numpy as np
from pydantic import BaseModel
from scipy.stats import wilcoxon

# Cargar variables de entorno si están disponibles
try:
    from dotenv import load_dotenv

    for ep in [
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[2] / "monorepo" / ".env",
        Path(__file__).resolve().parents[2] / "monorepo" / "backend" / ".env",
    ]:
        if ep.exists():
            load_dotenv(ep)
except ImportError:
    pass

# Cargar dependencias de backend
backend_path = Path(__file__).resolve().parents[2] / "monorepo" / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.shared.regions import are_regions_matching

reranker_instance = None
try:
    from app.infrastructure.services.bge_reranker_service import BgeRerankerService
    reranker_instance = BgeRerankerService()
    print("[Reranker] BgeRerankerService (BGE-M3 ONNX INT8) cargado exitosamente para Estrategia D.")
except Exception as e:
    print(f"[Reranker] BgeRerankerService no cargado ({e}). Se omitirá Estrategia D si no hay dependencias.")


# =====================================================================
# Modelos Auxiliares y Métricas de Ranking (IR)
# =====================================================================

class DecisionUsuarioSimulada(BaseModel):
    tender_code: str
    relevante_para_click: bool
    justificacion_corta: str


class LoteDecisionesSimuladas(BaseModel):
    evaluaciones: List[DecisionUsuarioSimulada]


def calcular_dcg(relevancias: List[int], k: int) -> float:
    """Calcula Discounted Cumulative Gain hasta posición k."""
    dcg = 0.0
    for i, rel in enumerate(relevancias[:k], 1):
        if rel > 0:
            dcg += (2**rel - 1) / math.log2(i + 1)
    return dcg


def calcular_ndcg(relevancias_obtenidas: List[int], relevancias_ideales: List[int], k: int) -> float:
    """Calcula Normalized Discounted Cumulative Gain (NDCG@k)."""
    dcg = calcular_dcg(relevancias_obtenidas, k)
    idcg = calcular_dcg(relevancias_ideales, k)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def calcular_success_at_1(relevancias: List[int]) -> float:
    """1.0 si el ítem en la posición #1 es relevante (rel >= 1), de lo contrario 0.0."""
    return 1.0 if relevancias and relevancias[0] >= 1 else 0.0


def calcular_mrr(relevancias: List[int]) -> float:
    """Calcula Reciprocal Rank del primer resultado relevante (rel >= 1)."""
    for i, rel in enumerate(relevancias, 1):
        if rel >= 1:
            return 1.0 / i
    return 0.0


def calcular_precision_at_k(relevancias: List[int], k: int) -> float:
    """Porcentaje de items relevantes en el Top-K."""
    if k == 0:
        return 0.0
    top = relevancias[:k]
    return sum(1 for r in top if r >= 1) / k


def calcular_recall_at_k(relevancias: List[int], total_positivos: int, k: int) -> float:
    """Fracción de items relevantes recuperados en el Top-K sobre el total disponible."""
    if total_positivos == 0:
        return 0.0
    top = relevancias[:k]
    recuperados = sum(1 for r in top if r >= 1)
    return min(1.0, recuperados / total_positivos)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# =====================================================================
# Pruebas Estadísticas: Wilcoxon Pareado, Holm-Bonferroni y Bootstrap
# =====================================================================

def calcular_significancia_pareada(series_a: List[float], series_b: List[float]) -> Tuple[float, float, Tuple[float, float]]:
    """
    Calcula:
      1. Diferencia media (B - A)
      2. p-valor del test de rangos con signo de Wilcoxon pareado
      3. Intervalo de confianza al 95% por Bootstrap pareado sobre la diferencia
    """
    diffs = np.array(series_b) - np.array(series_a)
    mean_diff = float(np.mean(diffs))

    if np.all(diffs == 0):
        p_val = 1.0
    else:
        try:
            stat, p_val = wilcoxon(diffs, alternative="two-sided")
        except Exception:
            p_val = 1.0

    # Bootstrap pareado de la diferencia (2000 réplicas con semilla fija)
    rng = np.random.default_rng(42)
    n = len(diffs)
    boot_means = [np.mean(rng.choice(diffs, size=n, replace=True)) for _ in range(2000)]
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    return mean_diff, float(p_val), (ci_lower, ci_upper)


def corregir_holm_bonferroni(p_valores: List[float]) -> List[float]:
    """Aplica corrección de Holm-Bonferroni a una lista de p-valores."""
    n = len(p_valores)
    ordenados = sorted(enumerate(p_valores), key=lambda x: x[1])
    p_adj = [0.0] * n
    max_p = 0.0
    for rank, (orig_idx, p) in enumerate(ordenados):
        adj = p * (n - rank)
        adj = max(adj, max_p)
        adj = min(adj, 1.0)
        max_p = adj
        p_adj[orig_idx] = adj
    return p_adj


# =====================================================================
# Simulador de Usuario con Gemini (LLM-as-a-User) con Métricas de Fallback
# =====================================================================

class SimuladorUsuarioLLM:
    """
    Simula el comportamiento de un usuario/licitador evaluando si haría 'Click'
    o revisaría en detalle una licitación basándose en el perfil de su empresa.
    """

    def __init__(self, api_key: str, cache_file: Optional[Path] = None, model_name: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key
        self.model_name = model_name
        self.cache_file = cache_file
        self.cache: Dict[str, bool] = {}
        self.fallbacks_count: int = 0
        self.llamadas_api_count: int = 0
        from google import genai
        self.client = genai.Client(api_key=self.api_key)
        self._cargar_cache()

    def _cargar_cache(self):
        if self.cache_file and self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                print(f"[Simulador LLM] Se cargaron {len(self.cache)} decisiones de click desde caché.")
            except Exception:
                self.cache = {}

    def guardar_cache(self):
        if self.cache_file:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)

    async def simular_clicks_proveedor(
        self,
        proveedor_info: Dict[str, Any],
        candidatos_tenders: List[Dict[str, Any]],
    ) -> Dict[str, bool]:
        from google.genai import types

        rut = proveedor_info.get("rut", "")
        perfil = proveedor_info.get("perfil", {})
        resumen_empresa = (
            f"Empresa: {perfil.get('legal_name')}\n"
            f"Rubros: {', '.join(perfil.get('sectors', []))}\n"
            f"Descripción: {perfil.get('description', '')}\n"
            f"Palabras Clave: {', '.join(perfil.get('keywords', [])[:15])}\n"
            f"Regiones: {', '.join(perfil.get('regions', []))}"
        )

        resultado = {}
        pendientes_evaluar = []

        for t in candidatos_tenders:
            code = t.get("code")
            cache_key = f"{rut}::{code}"
            if cache_key in self.cache:
                resultado[code] = self.cache[cache_key]
            else:
                pendientes_evaluar.append(t)

        if not pendientes_evaluar:
            return resultado

        lista_licitaciones_texto = []
        for t in pendientes_evaluar:
            items_str = ", ".join([it.get("nombre", "") for it in t.get("items", [])[:4]])
            desc = t.get("description") or t.get("name")
            lista_licitaciones_texto.append(
                f"- Código: {t.get('code')}\n"
                f"  Título: {t.get('name')}\n"
                f"  Descripción: {desc[:200]}...\n"
                f"  Región: {t.get('region', 'N/A')}\n"
                f"  Ítems: {items_str}"
            )

        prompt = f"""
Eres el encargado de compras públicas y postulación a licitaciones de la siguiente empresa:
{resumen_empresa}

A continuación, se te presenta una lista de oportunidades de compra pública (Compra Ágil) recomendadas para tu empresa.
Para cada oportunidad, evalúa si como usuario de la empresa harías CLICK para ver el detalle y postular, o si la descartarías por ser de otro rubro o ajena a tus capacidades.

OPORTUNIDADES A EVALUAR:
{chr(10).join(lista_licitaciones_texto)}

INSTRUCCIONES:
Para cada oportunidad (según su código exacto), responde con:
- tender_code: código de la oportunidad
- relevante_para_click: true si harías click por afinidad comercial directa o complementaria, false si es de otro rubro ajeno.
- justificacion_corta: motivo en una frase.
"""

        modelos_disponibles = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]
        for m_name in modelos_disponibles:
            for intento in range(1, 3):
                try:
                    self.llamadas_api_count += 1
                    response = self.client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=LoteDecisionesSimuladas,
                            temperature=0.1,
                        ),
                    )
                    data = json.loads(response.text)
                    evaluaciones = data.get("evaluaciones", [])
                    for ev in evaluaciones:
                        code_ev = ev.get("tender_code")
                        val = bool(ev.get("relevante_para_click"))
                        resultado[code_ev] = val
                        self.cache[f"{rut}::{code_ev}"] = val
                    self.guardar_cache()
                    return resultado
                except Exception as err:
                    err_str = str(err)
                    if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                        await asyncio.sleep(1.5 * intento)
                        continue
                    else:
                        break

        # Fallback a heurística sólo ante fallo completo de API
        self.fallbacks_count += len(pendientes_evaluar)
        print(f"  [Aviso Simulador LLM] Modelos no respondieron para {perfil.get('legal_name')}. Usando afinidad léxica.")
        sectores_prov = [s.lower() for s in perfil.get("sectors", [])]
        for t in pendientes_evaluar:
            t_text = f"{t.get('name', '')} {t.get('description', '')}".lower()
            click = any(s in t_text for s in sectores_prov)
            resultado[t.get("code")] = click
            self.cache[f"{rut}::{t.get('code')}"] = click
        self.guardar_cache()
        return resultado


# =====================================================================
# Generador y Administrador de Embeddings (Cacheable)
# =====================================================================

class GestorEmbeddings:
    """Gestiona la generación de embeddings vía Gemini API con persistencia local en caché."""

    def __init__(self, api_key: str, cache_file: Path):
        self.api_key = api_key
        self.cache_file = cache_file
        self.cache: Dict[str, List[float]] = {}
        self.fallbacks_count: int = 0
        from google import genai
        self.client = genai.Client(api_key=self.api_key)
        self._cargar_cache()

    def _cargar_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                print(f"[Caché] Se cargaron {len(self.cache)} embeddings existentes desde {self.cache_file.name}")
            except Exception:
                self.cache = {}

    def guardar_cache(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f)

    async def obtener_embedding(self, texto: str, id_clave: str) -> np.ndarray:
        if id_clave in self.cache:
            return np.array(self.cache[id_clave], dtype=np.float32)

        texto_limpio = texto[:1800] if len(texto) > 1800 else texto
        for intento in range(1, 4):
            try:
                res = self.client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=texto_limpio,
                )
                vector = res.embeddings[0].values
                self.cache[id_clave] = vector
                return np.array(vector, dtype=np.float32)
            except Exception:
                await asyncio.sleep(1.5 * intento)

        self.fallbacks_count += 1
        return np.zeros(3072, dtype=np.float32)


# =====================================================================
# Pipeline de Evaluación y Comparativa de Estrategias
# =====================================================================

async def ejecutar_evaluacion_completa(
    dataset_dir: Path,
    api_key: str,
    top_k: int = 10,
    usar_simulador_llm: bool = True,
):
    print("=" * 80)
    print("🚀 INICIO DE EVALUACIÓN DE MATCHING Y RANKING (COMPRA ÁGIL)")
    print(f"Directorio de datos: {dataset_dir}")
    print(f"Top-K evaluado: {top_k}")
    print("=" * 80)

    archivo_proveedores = dataset_dir / "dataset_compra_agil_proveedores.json"
    archivo_tenders = dataset_dir / "compras_agiles_para_matching.json"
    archivo_cache = dataset_dir / "embeddings_cache.json"
    archivo_sim_cache = dataset_dir / "simulaciones_usuario_cache.json"

    with open(archivo_proveedores, "r", encoding="utf-8") as f:
        proveedores = json.load(f)

    with open(archivo_tenders, "r", encoding="utf-8") as f:
        tenders = json.load(f)

    print(f"-> Proveedores cargados: {len(proveedores)}")
    print(f"-> Catálogo de Compras Ágiles indexables: {len(tenders)}")

    gestor_emb = GestorEmbeddings(api_key=api_key, cache_file=archivo_cache)
    simulador = SimuladorUsuarioLLM(api_key=api_key, cache_file=archivo_sim_cache) if usar_simulador_llm else None

    # 1. Cargar/Generar Embeddings
    print("\n[1/4] Verificando embeddings del catálogo...")
    tenders_dict: Dict[str, Dict[str, Any]] = {}
    tenders_vectores: Dict[str, np.ndarray] = {}

    for i, t in enumerate(tenders, 1):
        code = t["code"]
        tenders_dict[code] = t
        items_desc = ". ".join([f"{it.get('nombre', '')} ({it.get('descripcion') or ''})" for it in t.get("items", [])[:5]])
        texto_tender = f"{t.get('name', '')}. {t.get('description', '')}. Partidas requeridas: {items_desc}".strip()
        vec = await gestor_emb.obtener_embedding(texto_tender, id_clave=f"tender_{code}")
        tenders_vectores[code] = vec

    gestor_emb.guardar_cache()

    # 2. Cargar/Generar Embeddings de Proveedores
    print("[2/4] Verificando embeddings de proveedores...")
    proveedores_vectores: Dict[str, np.ndarray] = {}
    for prov in proveedores:
        rut = prov["rut"]
        perfil = prov.get("perfil", {})
        texto_prov = (
            f"Proveedor rubros: {', '.join(perfil.get('sectors', []))}. "
            f"Descripción: {perfil.get('description', '')}. "
            f"Especialidades técnicas: {', '.join(perfil.get('keywords', [])[:20])}."
        )
        vec = await gestor_emb.obtener_embedding(texto_prov, id_clave=f"prov_{rut}")
        proveedores_vectores[rut] = vec

    gestor_emb.guardar_cache()

    # 3. Evaluar Estrategias de Ranking
    print("\n[3/4] Ejecutando Ranking y Evaluación...")

    estrategias_nombres = ["A_Embedding_Puro", "B_Hibrido_Lexico", "C_Hibrido_Regional"]
    if reranker_instance is not None:
        estrategias_nombres.append("D_Produccion_RRF")

    metricas_dura = {est: {"ndcg_5": [], "ndcg_10": [], "success_1": [], "mrr": [], "p_5": [], "p_10": [], "recall_10": []} for est in estrategias_nombres}
    metricas_juez = {est: {"ndcg_5": [], "ndcg_10": [], "success_1": [], "mrr": [], "p_5": [], "p_10": [], "recall_10": []} for est in estrategias_nombres}

    total_evaluados = 0

    for idx, prov in enumerate(proveedores, 1):
        rut = prov["rut"]
        perfil = prov.get("perfil", {})
        vec_prov = proveedores_vectores[rut]
        positivos_gt = set(prov.get("ids_procesos_positivos", []))
        regiones_prov = list(perfil.get("regions", []))
        keywords_prov = [k.lower() for k in perfil.get("keywords", [])[:20]]
        sectores_prov = [s.lower() for s in perfil.get("sectors", [])]

        texto_prov = (
            f"Proveedor: {', '.join(perfil.get('sectors', []))}. "
            f"Descripción: {perfil.get('description', '')}. "
            f"Especialidades: {', '.join(perfil.get('keywords', [])[:15])}."
        )

        scores_A = []
        scores_B = []
        scores_C = []

        for code, t in tenders_dict.items():
            vec_tender = tenders_vectores[code]
            sim_cos = cosine_sim(vec_prov, vec_tender)

            t_text = f"{t.get('name', '')} {t.get('description', '')}".lower()
            kw_match = sum(1 for kw in keywords_prov if kw in t_text)
            sec_match = sum(1 for sc in sectores_prov if sc in t_text)
            lexical_boost = min(0.35, (kw_match * 0.05) + (sec_match * 0.10))

            t_region = t.get("region") or ""
            # FIX: uso de función canónica are_regions_matching
            regional_match = are_regions_matching(t_region, regiones_prov)

            # Estrategia A: Puro Coseno
            score_a = sim_cos

            # Estrategia B: Híbrido (70% Coseno + 30% Léxico)
            score_b = (0.70 * sim_cos) + (0.30 * min(1.0, lexical_boost * 3.0))

            # Estrategia C: Híbrido + Boost regional (+0.05 si coincide, sin penalización destructiva)
            score_c = score_b + (0.05 if regional_match else 0.0)

            scores_A.append((code, score_a))
            scores_B.append((code, score_b))
            scores_C.append((code, score_c))

        scores_A.sort(key=lambda x: x[1], reverse=True)
        scores_B.sort(key=lambda x: x[1], reverse=True)
        scores_C.sort(key=lambda x: x[1], reverse=True)

        top_A = [code for code, _ in scores_A[:top_k]]
        top_B = [code for code, _ in scores_B[:top_k]]
        top_C = [code for code, _ in scores_C[:top_k]]

        # Estrategia D: Pipeline Producción con Reciprocal Rank Fusion (RRF)
        top_D = []
        if reranker_instance is not None:
            candidatos_top20 = [code for code, _ in scores_B[:20]]
            cand_pairs = [
                (
                    uuid5(NAMESPACE_DNS, c),
                    f"Partidas: {', '.join([it.get('nombre', '') for it in tenders_dict[c].get('items', [])[:3]])}. "
                    f"Licitación: {tenders_dict[c].get('name', '')}. {tenders_dict[c].get('description') or ''}."
                )
                for c in candidatos_top20
            ]
            rerank_results = await reranker_instance.rerank(query_text=texto_prov, candidates=cand_pairs, limit=20)
            
            # RRF con k=60 estándar para evitar incompatibilidad de escalas y ruidos min-max
            rank_map_stage1 = {code: rank for rank, (code, _) in enumerate(scores_B[:20], 1)}
            rank_map_rerank = {code: rank for rank, (uid, _) in enumerate(rerank_results, 1) for code in candidatos_top20 if uuid5(NAMESPACE_DNS, code) == uid}

            scores_D = []
            for c in candidatos_top20:
                r1 = rank_map_stage1.get(c, 20)
                r2 = rank_map_rerank.get(c, 20)
                rrf_score = (1.0 / (60 + r1)) + (1.0 / (60 + r2))
                scores_D.append((c, rrf_score))

            scores_D.sort(key=lambda x: x[1], reverse=True)
            top_D = [code for code, _ in scores_D[:top_k]]

        # Evaluar decisiones con Simulador LLM
        candidatos_a_evaluar = list(set(top_A + top_B + top_C + top_D))
        candidatos_tenders_info = [tenders_dict[c] for c in candidatos_a_evaluar if c in tenders_dict]

        clicks_simulados = {}
        if simulador:
            clicks_simulados = await simulador.simular_clicks_proveedor(prov, candidatos_tenders_info)

        # -------------------------------------------------------------
        # Escala 1: Métricas Duras (Solo Relevancia 2 = Ganadas Reales)
        # -------------------------------------------------------------
        def rel_dura(code: str) -> int:
            return 2 if code in positivos_gt else 0

        ideal_dura = sorted([rel_dura(code) for code in tenders_dict], reverse=True)
        total_gt_ganadas = len(positivos_gt)  # Siempre 5

        # -------------------------------------------------------------
        # Escala 2: Métricas con Juez LLM (Escala Graduada 0, 1, 2)
        # -------------------------------------------------------------
        def rel_juez(code: str) -> int:
            if code in positivos_gt:
                return 2
            if clicks_simulados.get(code, False):
                return 1
            return 0

        ideal_juez = sorted([rel_juez(code) for code in tenders_dict], reverse=True)
        total_relevantes_juez = sum(1 for r in ideal_juez if r >= 1)

        estrategias_evaluar = [
            ("A_Embedding_Puro", top_A),
            ("B_Hibrido_Lexico", top_B),
            ("C_Hibrido_Regional", top_C),
        ]
        if top_D:
            estrategias_evaluar.append(("D_Produccion_RRF", top_D))

        for est_nombre, top_lista in estrategias_evaluar:
            # 1. Medir Duras
            rels_d = [rel_dura(c) for c in top_lista]
            metricas_dura[est_nombre]["ndcg_5"].append(calcular_ndcg(rels_d, ideal_dura, k=5))
            metricas_dura[est_nombre]["ndcg_10"].append(calcular_ndcg(rels_d, ideal_dura, k=10))
            metricas_dura[est_nombre]["success_1"].append(calcular_success_at_1(rels_d))
            metricas_dura[est_nombre]["mrr"].append(calcular_mrr(rels_d))
            metricas_dura[est_nombre]["p_5"].append(calcular_precision_at_k(rels_d, k=5))
            metricas_dura[est_nombre]["p_10"].append(calcular_precision_at_k(rels_d, k=10))
            metricas_dura[est_nombre]["recall_10"].append(calcular_recall_at_k(rels_d, total_gt_ganadas, k=10))

            # 2. Medir con Juez
            rels_j = [rel_juez(c) for c in top_lista]
            metricas_juez[est_nombre]["ndcg_5"].append(calcular_ndcg(rels_j, ideal_juez, k=5))
            metricas_juez[est_nombre]["ndcg_10"].append(calcular_ndcg(rels_j, ideal_juez, k=10))
            metricas_juez[est_nombre]["success_1"].append(calcular_success_at_1(rels_j))
            metricas_juez[est_nombre]["mrr"].append(calcular_mrr(rels_j))
            metricas_juez[est_nombre]["p_5"].append(calcular_precision_at_k(rels_j, k=5))
            metricas_juez[est_nombre]["p_10"].append(calcular_precision_at_k(rels_j, k=10))
            metricas_juez[est_nombre]["recall_10"].append(calcular_recall_at_k(rels_j, total_relevantes_juez, k=10))

        total_evaluados += 1
        if idx % 10 == 0 or idx == len(proveedores):
            print(f"  Evaluados {idx}/{len(proveedores)} proveedores...")

    # 4. Consolidar Informe
    print("\n" + "=" * 95)
    print("📊 TABLA 1: MÉTRICAS DURAS (SOLO ADJUDICACIONES REALES - GROUND TRUTH, REL = 2)")
    print("Población: 50 proveedores | 5 adjudicaciones reales por proveedor | Catálogo: 250 licitaciones")
    print("=" * 95)
    header = f"{'Estrategia':<22} | {'NDCG@5':<7} | {'NDCG@10':<7} | {'Succ@1':<7} | {'MRR':<7} | {'P@5':<7} | {'P@10 (Max.5)':<12} | {'Recall@10':<9}"
    print(header)
    print("-" * len(header))

    res_duras_print = {}
    for est in metricas_dura:
        m = metricas_dura[est]
        res_duras_print[est] = {
            "ndcg_5": np.mean(m["ndcg_5"]),
            "ndcg_10": np.mean(m["ndcg_10"]),
            "success_1": np.mean(m["success_1"]),
            "mrr": np.mean(m["mrr"]),
            "p_5": np.mean(m["p_5"]),
            "p_10": np.mean(m["p_10"]),
            "recall_10": np.mean(m["recall_10"]),
        }
        r = res_duras_print[est]
        print(f"{est:<22} | {r['ndcg_5']:.4f}  | {r['ndcg_10']:.4f}   | {r['success_1']:.4f}  | {r['mrr']:.4f}  | {r['p_5']:.4f}  | {r['p_10']:.4f}       | {r['recall_10']:.4f}")

    print("=" * 95)

    print("\n" + "=" * 95)
    print("📊 TABLA 2: MÉTRICAS CON JUEZ LLM (ESCALA GRADUADA: REL = 2 ADJUDICADA, REL = 1 CLICK)")
    print("=" * 95)
    print(header)
    print("-" * len(header))

    res_juez_print = {}
    for est in metricas_juez:
        m = metricas_juez[est]
        res_juez_print[est] = {
            "ndcg_5": np.mean(m["ndcg_5"]),
            "ndcg_10": np.mean(m["ndcg_10"]),
            "success_1": np.mean(m["success_1"]),
            "mrr": np.mean(m["mrr"]),
            "p_5": np.mean(m["p_5"]),
            "p_10": np.mean(m["p_10"]),
            "recall_10": np.mean(m["recall_10"]),
        }
        r = res_juez_print[est]
        print(f"{est:<22} | {r['ndcg_5']:.4f}  | {r['ndcg_10']:.4f}   | {r['success_1']:.4f}  | {r['mrr']:.4f}  | {r['p_5']:.4f}  | {r['p_10']:.4f}       | {r['recall_10']:.4f}")

    print("=" * 95)

    # 5. Pruebas de Significancia Estadística (sobre NDCG@10 en Métricas Duras)
    print("\n📈 PRUEBAS DE SIGNIFICANCIA ESTADÍSTICA (Wilcoxon Pareado + Holm-Bonferroni + Bootstrap IC 95%)")
    print("Variable analizada: NDCG@10 (Métricas Duras)")
    print("-" * 95)

    comparaciones = [
        ("A_Embedding_Puro", "B_Hibrido_Lexico"),
        ("A_Embedding_Puro", "C_Hibrido_Regional"),
        ("A_Embedding_Puro", "D_Produccion_RRF"),
        ("B_Hibrido_Lexico", "C_Hibrido_Regional"),
        ("B_Hibrido_Lexico", "D_Produccion_RRF"),
    ]

    p_raw_list = []
    diff_stats = []

    for est_a, est_b in comparaciones:
        if est_a in metricas_dura and est_b in metricas_dura:
            vals_a = metricas_dura[est_a]["ndcg_10"]
            vals_b = metricas_dura[est_b]["ndcg_10"]
            diff, p_raw, (ci_low, ci_high) = calcular_significancia_pareada(vals_a, vals_b)
            p_raw_list.append(p_raw)
            diff_stats.append((est_a, est_b, diff, p_raw, ci_low, ci_high))

    p_adj_list = corregir_holm_bonferroni(p_raw_list)

    print(f"{'Comparación':<35} | {'Diff Media':<10} | {'p-raw':<8} | {'p-adj (Holm)':<12} | {'Bootstrap 95% CI':<20}")
    print("-" * 95)
    for (est_a, est_b, diff, p_raw, ci_low, ci_high), p_adj in zip(diff_stats, p_adj_list):
        comp_str = f"{est_b} vs {est_a}"
        signif = "*" if p_adj < 0.05 else "ns"
        ci_str = f"[{ci_low:+.4f}, {ci_high:+.4f}]"
        print(f"{comp_str:<35} | {diff:+.4f}     | {p_raw:.4f}   | {p_adj:.4f} ({signif})   | {ci_str:<20}")

    print("-" * 95)
    print("Significancia: * p < 0.05 corregido por Holm | ns = no significativo (p >= 0.05)")

    # 6. Reporte de Robustez y Fallbacks
    print("\n🛡️ REPORTE DE ROBUSTEZ Y FALLBACKS")
    print(f"- Fallbacks de Embeddings (vectores de ceros): {gestor_emb.fallbacks_count}")
    if simulador:
        print(f"- Llamadas API a Gemini realizadas:           {simulador.llamadas_api_count}")
        print(f"- Fallbacks del Juez (heurística léxica):     {simulador.fallbacks_count}")
        print(f"- Decisiones cargadas desde caché de disco:   {len(simulador.cache)}")
    print("=" * 95)

    # Exportar resultados estructurados
    resultados_json = {
        "metricas_duras": {est: {k: round(float(v), 4) for k, v in r.items()} for est, r in res_duras_print.items()},
        "metricas_juez": {est: {k: round(float(v), 4) for k, v in r.items()} for est, r in res_juez_print.items()},
        "significancia_ndcg10_dura": [
            {
                "comparacion": f"{est_b} vs {est_a}",
                "diff_media": round(float(diff), 4),
                "p_raw": round(float(p_raw), 4),
                "p_adj_holm": round(float(p_adj), 4),
                "ci_95": [round(float(ci_low), 4), round(float(ci_high), 4)],
                "es_significativo": bool(p_adj < 0.05),
            }
            for (est_a, est_b, diff, p_raw, ci_low, ci_high), p_adj in zip(diff_stats, p_adj_list)
        ],
        "fallbacks": {
            "embeddings": gestor_emb.fallbacks_count,
            "juez_heuristico": simulador.fallbacks_count if simulador else 0,
        },
    }

    salida_reporte = dataset_dir / "metricas_matching_resultados.json"
    with open(salida_reporte, "w", encoding="utf-8") as f:
        json.dump(resultados_json, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Resultados completos exportados a: {salida_reporte.resolve()}")
    return resultados_json


def main():
    parser = argparse.ArgumentParser(description="Evalúa el ranking de licitaciones y calcula métricas IR rigurosas.")
    parser.add_argument("--data-dir", type=str, default="spikes/dataset_compra_agil/data", help="Ruta de datos")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K a evaluar")
    parser.add_argument("--sin-llm", action="store_true", help="Desactiva la simulación de clicks con LLM.")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY") or ""
    if not api_key:
        print("❌ Error: Se requiere GEMINI_API_KEY en el entorno para embeddings y simulación.")
        sys.exit(1)

    asyncio.run(
        ejecutar_evaluacion_completa(
            dataset_dir=Path(args.data_dir),
            api_key=api_key,
            top_k=args.top_k,
            usar_simulador_llm=not args.sin_llm,
        )
    )


if __name__ == "__main__":
    main()
