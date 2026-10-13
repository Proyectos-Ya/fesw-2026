# Spike 2: Evaluación y Mejora del Pipeline de Matching Semántico

* **Estimación:** 8 Story Points (SP)
* **Fecha:** Septiembre 2026
* **Ambiente:** `monorepo/backend` (BGE-M3 y BGE-Reranker locales) + `spikes/dataset_compra_agil`
* **Estado:** medición dura y medición con juez LLM completas. Falta validar el juez frente a humanos (§6).

---

## Resumen ejecutivo

Este spike evalúa el motor de matching licitación ↔ proveedor con métricas de Information Retrieval sobre datos reales de Mercado Público (Compra Ágil).

Las versiones anteriores de este informe tenían errores de medición que inflaban o distorsionaban los resultados (fuga de información, catálogo cerrado, región mal comparada, cifras mal cruzadas, juez sin validar). Se rehízo el benchmark corrigiéndolos. **Resultados con datos sin fuga (N = 50 proveedores):**

* El baseline denso (BGE-M3) **casi no encuentra** las compras que el proveedor ganó después: NDCG@10 = 0.052, y solo 7 de 50 consultas recuperan algún acierto en el top-10.
* Agregar BM25 real y señales estructuradas (región canónica + categoría UNSPSC del historial) **triplica el NDCG@10 (0.052 → 0.158)** y esa mejora **es estadísticamente significativa** (Holm p = 0.002, IC 95 % pareado [+0.057, +0.160]).
* El reranker (BGE-Reranker-v2-m3 INT8) sobre el top-100 **no mejora** al híbrido estructural (NDCG@10 0.118 vs 0.158, p = 0.063, no significativo) y su techo lo fija el primer estadio.
* Aun el mejor pipeline (C) recupera solo el **24 % de las adjudicaciones en el top-10** y el **67 % en el top-100**: el primer estadio sigue siendo el cuello de botella.
* **Con un juez LLM sobre un pool común** (que además cuenta como buenas las órdenes afines que el proveedor no ganó), el orden de las estrategias se mantiene y las brechas son mayores: NDCG@10 de 0.379 (A) a 0.660 (C), P@10 (relevancia ≥ 1) de 49 % a 77 %. Con el juez, el reranker (D) queda **peor** que C (−0.060, IC [−0.097, −0.027]).

| Criterio de aceptación | Estado | Evidencia |
| :--- | :---: | :--- |
| **CA-1:** métricas y pruebas que midan la calidad del matching | **Cumplido** | `evaluar_benchmark_temporal.py` (métricas duras) y `evaluar_con_juez_temporal.py` (graduadas): NDCG@10, MRR, Success@1, P@10, Recall@K por etapa, Wilcoxon pareado + Holm + bootstrap pareado. |
| **CA-2:** estrategias de mejora con incremento sustancial | **Cumplido con reservas** | C vs A: ΔNDCG@10 = +0.106 en métricas duras y +0.281 con juez, ambos significativos (Holm p ≤ 0.002). Las reservas son de validez externa (§7): el juez no está validado frente a humanos y falta medir el caso sin historial. |

---

## 1. Métricas

| Métrica | Qué mide | Nota de interpretación |
| :--- | :--- | :--- |
| **NDCG@10** | Calidad posicional del ranking | Solo comparable entre estrategias sobre el mismo catálogo y consultas. |
| **Success@1** | % de consultas con un acierto en la posición 1 | Es distinto del MRR. |
| **MRR** | Promedio de 1/posición del primer acierto | Un MRR de 0.9 **no** significa 90 % de aciertos en la posición 1. |
| **P@10** | Aciertos en el top-10 / 10 | Techo = 0.20, porque cada proveedor tiene 2 positivos. |
| **Recall@K** (10/50/100/200) | Fracción de las adjudicaciones posteriores recuperada en el top-K | **Recall@100/200 es el techo de cualquier reranker.** |

Relevancia dura: 2 = adjudicación real del proveedor **posterior** a su historial; 0 = todo lo demás.

---

## 2. Dataset (split temporal, catálogo natural)

Scripts: `recolectar_muestra_temporal.py`, `recolectar_ocs_proveedores.py`, `construir_benchmark_temporal.py`. Datos en `spikes/dataset_compra_agil/data/temporal/`.

* **50 proveedores** reales con 5 órdenes de Compra Ágil cada uno, con fecha. Las 3 más antiguas son su **historial**; las 2 restantes (estrictamente posteriores) son los **positivos**. Total: 100 positivos.
* **Perfil del proveedor** generado por LLM **solo desde el historial** (sectores canónicos, descripción, keywords) + regiones y categorías UNSPSC reales del historial. No ve los positivos.
* **Catálogo: 1.176 órdenes** = 100 positivos + 1.076 distractores, todos del mismo endpoint de detalle (mismo formato: partidas, categoría UNSPSC, región real). Los distractores son una muestra aleatoria de las Compras Ágiles de 11 días hábiles de septiembre 2026 (≈55.000 disponibles), excluyendo cualquier orden de los 50 proveedores.
* Se elimina de la descripción de cada orden la línea "dirigida a <PROVEEDOR>" (filtraba el nombre del ganador) y la justificación de selección.

---

## 3. Estrategias

| | Estrategia |
| :--- | :--- |
| **A** | Coseno denso BGE-M3 (baseline de producción) |
| **B** | Híbrido: denso + BM25 (tokenizado, sin tildes, stemming ligero, sobre título, descripción y partidas), fusionados con **RRF** (sin pesos ad hoc) |
| **C** | B + señal estructural por RRF: región canónica (`are_regions_matching`) y categoría UNSPSC presente en el historial |
| **E** | B + multi-consulta: una consulta densa por producto histórico, puntaje = máximo |
| **D** | Reranker BGE-v2-m3 (INT8, consulta corta) sobre el top-100 de C, fusionado por RRF |

---

## 4. Resultados: métricas duras

*N = 50 consultas · catálogo = 1.176 · techo P@10 = 0.20*

| Estrategia | NDCG@10 | MRR | Success@1 | P@10 | R@10 | R@50 | R@100 | R@200 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A: Denso (baseline)** | 0.0517 | 0.0675 | 0.02 | 0.016 | 0.08 | 0.24 | 0.38 | 0.53 |
| **B: Híbrido BM25 + RRF** | 0.0973 | 0.1225 | 0.06 | 0.030 | 0.15 | 0.45 | 0.55 | 0.75 |
| **C: Híbrido + señales estructurales** | **0.1579** | **0.1816** | 0.08 | **0.048** | **0.24** | **0.59** | **0.67** | **0.80** |
| **E: Multi-consulta** | 0.1193 | 0.1440 | 0.06 | 0.038 | 0.19 | 0.41 | 0.55 | 0.70 |
| **D: Reranker sobre top-100 de C** | 0.1175 | 0.1632 | **0.10** | 0.032 | 0.16 | 0.52 | 0.67 | 0.80 |

Consultas con al menos un acierto en el top-10: A 7/50 · B 13/50 · **C 20/50** · E 17/50 · D 14/50.

### Significancia (NDCG@10; Wilcoxon pareado, corrección Holm, bootstrap pareado sobre la diferencia por consulta)

| Comparación | Δ | IC 95 % | p ajustado (Holm) |
| :--- | :---: | :---: | :---: |
| B vs A | +0.046 | [+0.017, +0.077] | 0.017 * |
| **C vs A** | **+0.106** | [+0.057, +0.160] | **0.002 *** |
| E vs A | +0.068 | [+0.030, +0.110] | 0.011 * |
| D vs A | +0.066 | [+0.025, +0.111] | 0.011 * |
| C vs B | +0.061 | [+0.021, +0.104] | 0.017 * |
| D vs C (sin corrección; comparación posterior) | −0.040 | [−0.083, +0.001] | p = 0.063 (ns) |
| E vs B (sin corrección; comparación posterior) | +0.022 | [−0.001, +0.047] | p = 0.125 (ns) |

---

## 5. Diagnóstico

1. **El denso solo es débil para este problema.** Los textos de Compra Ágil son cortos, con títulos administrativos y partidas específicas; el vector de un perfil general recupera el rubro, no la compra concreta. Recall@100 = 38 %.
2. **Lo léxico y lo estructural aportan más que un reranker.** BM25 sobre partidas suma +0.046; las señales de región y categoría UNSPSC suman otros +0.061. Con C, Recall@100 sube a 67 %.
3. **El reranker no compensa un primer estadio débil.** Mejora el Success@1 (0.10 vs 0.08) pero empeora NDCG@10 y Recall@10 frente a C; los positivos que no entran al top-100 no se pueden rescatar. Con métricas duras la diferencia D vs C no es significativa (N = 50); con el juez (§6) D queda claramente por debajo de C.
4. **La región sí ayuda cuando se compara bien.** El resultado del informe anterior ("la región daña el ranking") era un artefacto: la región del catálogo trae espacios finales (`"Región de Coquimbo "`) y la comparación por igualdad de texto castigaba 140 de 250 adjudicaciones. Con `are_regions_matching` (ids normalizados) esa señal ya no perjudica y, combinada con la categoría, mejora el ranking. El benchmark no aísla el aporte de la región por separado de la categoría (ver §8).

---

## 6. Métricas con juez LLM (pool común)

**Qué se corrigió.** El informe anterior afirmaba un "κ = 0.0909 contra una auditoría manual experta"; **era incorrecto**: la "auditoría" era una regla de palabras clave escrita en el script, no una persona, y su κ no sustenta descartar jueces LLM. Además, la tabla con juez salía de un pool armado solo con el ranking de A, así que lo que B, C y D traían fuera del pool contaba como irrelevante.

**Cómo se hizo ahora** (`juez_claude_lotes.py`, `evaluar_con_juez_temporal.py`; los juicios los emitieron subagentes de Claude porque la cuota gratuita de Gemini se agotó):

* **Pool común de 1.146 pares** = unión del top-10 de las cinco estrategias + las 100 adjudicaciones. Cobertura de juicios del top-10 de cada estrategia: 100 %.
* Escala estricta 0/1/2 (2 = mismo producto; 1 = misma familia, podría cotizarlo; 0 = otro rubro). Juzgado **a ciegas**: el juez no sabe qué órdenes fueron adjudicadas ni en qué posición quedó cada una.
* Relevancia usada = máx(juicio, 2 si es una adjudicación real). El ideal del NDCG se calcula sobre el pool.
* **Validación entre jueces:** una muestra de 150 pares se juzgó con un segundo modelo (Opus) sin ver el primero: **κ ponderado = 0.82, acuerdo exacto = 80 %, κ binario (≥1) = 0.75**. Es acuerdo entre dos LLM; **no es validez frente a humanos**.
* Distribución del juez (0/1/2): 484 / 390 / 272. De las 100 adjudicaciones reales, juzgadas a ciegas: 26 salieron 0, 31 salieron 1 y 43 salieron 2. Es decir, **el 26 % de lo que los proveedores realmente ganaron no calza con su perfil según el juez**: a veces ganan fuera de su giro, o el perfil no lo refleja.

| Estrategia | NDCG@10 | P@10 (rel ≥ 1) | P@10 (rel = 2) | Success@1 (rel ≥ 1) |
| :--- | :---: | :---: | :---: | :---: |
| **A: Denso** | 0.379 | 0.490 | 0.200 | 0.62 |
| **B: Híbrido BM25 + RRF** | 0.579 | 0.708 | 0.314 | 0.90 |
| **C: Híbrido + señales estructurales** | **0.660** | **0.772** | **0.380** | 0.94 |
| **E: Multi-consulta** | 0.615 | 0.726 | 0.346 | 0.88 |
| **D: Reranker sobre top-100 de C** | 0.600 | 0.702 | 0.318 | 0.94 |

| Comparación (NDCG@10 con juez) | Δ | IC 95 % | p ajustado (Holm) |
| :--- | :---: | :---: | :---: |
| B vs A | +0.200 | [+0.167, +0.235] | < 0.001 * |
| **C vs A** | **+0.281** | [+0.237, +0.328] | **< 0.001 *** |
| E vs A | +0.237 | [+0.196, +0.278] | < 0.001 * |
| D vs A | +0.221 | [+0.172, +0.273] | < 0.001 * |
| C vs B | +0.081 | [+0.050, +0.113] | < 0.001 * |
| D vs C (comparación posterior, sin corrección) | −0.060 | [−0.097, −0.027] | p = 0.005 |
| E vs B (comparación posterior, sin corrección) | +0.037 | [+0.012, +0.060] | p = 0.001 |

**Lectura.** Con el juez el orden es el mismo que con las métricas duras (C > E > D > B > A) y las brechas son mucho mayores, porque también se premia recomendar órdenes afines que el proveedor no ganó. Aquí el reranker sí queda por debajo de C de forma consistente, no solo dentro del ruido. Su único punto a favor sigue siendo el Success@1 en métricas duras.

**Sesgo a tener en cuenta.** El juez y BM25 miran lo mismo (perfil vs partidas), así que las estrategias léxicas pueden salir favorecidas frente al denso. Por eso las conclusiones sobre A vs el resto deben leerse junto con la tabla de métricas duras (§4), que no depende de ningún juez.

**Pendiente.** Etiquetar a mano `data/temporal/muestra_para_etiquetar.csv` (150 pares del pool, sin el juicio del LLM) y medir el acuerdo juez–humano.

---

## 7. Calibración del porcentaje de compatibilidad

**El problema.** El porcentaje actual es P = 0,5·reranker + 0,25·rubro + 0,25·keywords con bono léxico de frase exacta. En la práctica el bono léxico casi siempre vale 0 (plurales, tildes, palabras intermedias, rubro buscado solo en título/descripción), así que el máximo real es ~50 % del reranker. Una revisión humana de "Buses del Sur SpA" confirmó que licitaciones claramente relevantes aparecían con 21–28 %. Como el selector "verde" exige P ≥ 70 %, casi nada llega a ese umbral.

**Datos de calibración.** Se etiquetaron 1.146 pares (pool común de las estrategias de §4 y las adjudicaciones reales) con una escala 0/1/2 usando un juez LLM (κ ponderado = 0,82 entre dos instancias de Claude). Se realizó validación cruzada agrupada por proveedor (GroupKFold 5 pliegues).

| Hallazgo | Detalle |
| :--- | :--- |
| **Señales actuales insuficientes (Hallazgo 1)** | AUC (rel ≥ 1): Actual P0 = 0,58; reranker R = 0,54–0,56; coseno Qdrant S = 0,58. Calibradas sin nuevas señales, dan un porcentaje honesto pero plano (~40 % para todo). No alcanzan para distinguir bien. |
| **Bug en reranker INT8 (Hallazgo 2, corregido en backend)** | Cuantización dinámica por lote: el mismo par daba 0,35 al puntuar solo vs 0,44 en lote de 50. Solución: puntuar cada par por separado. Mejora: idéntico y ~3× más rápido (7–8 s vs 21–24 s para 50 candidatas). |
| **Nuevas señales (Hallazgo 3)** | Reranker con consulta corta "Rubro: … Productos: …" (Rc): 0,65; mejor calce keyword↔partida (B): 0,73; cobertura de partidas (C): 0,78; MaxSim normalizado (K): 0,67; descripción↔partida (D): 0,59. |

**Modelos evaluados** (`AUC / Brier / ECE / Precisión en ≥70 % / Media ordinal ajena–afín–exacta`):

| Modelo | AUC | Brier | ECE | Prec. ≥70 % | Ordinal |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Actual (P0) | 0,58 | 0,33 | 0,28 | — | 27–30–33 % |
| R | 0,54 | 0,24 | 0,02 | — | 40–41–41 % |
| Rc | 0,64 | — | — | — | — |
| B+C | 0,76 | — | — | — | — |
| **Rc+B+C** | **0,75** | **0,20** | **0,06** | **93 % (57/61)** | **34–42–52 %** |

(S, K y D no mejoran al combinarse.)

**Fórmula elegida.** Calibración logística multivariante:

$$P = 50 \cdot \sigma(z_1) + 50 \cdot \min(\sigma(z_2), \sigma(z_1))$$

$$z = a + b \cdot \text{logit}(R_c) + c \cdot B + d \cdot C$$

donde $\sigma$ es la función sigmoide. Coeficientes:

| Predicción | a | b | c | d |
| :--- | :---: | :---: | :---: | :---: |
| P(rel ≥ 1) | −3,888 | 0,328 | 3,255 | 6,030 |
| P(rel = 2) | −5,096 | 0,401 | 3,533 | 5,062 |

**Ejemplos de mejora** (perfil benchmark / perfil Buses del Sur; licitación / cambio esperado):

| Caso | Hoy | Calibrado |
| :--- | :---: | :---: |
| 3799-307 Programa Familia | 42 % | 85 % |
| 1028897-1297 Alumnos Carahue (revisión humana: >80 %) | 32–35 % | 68–74 % |
| 4408-466 Programa HPV (revisión humana: 40–50 %) | 35 % | 62–66 % |
| 4322-501 Arriendo de vehículo (afín) | 14 % | 42–46 % |

**Limitaciones de esta calibración.** Etiquetas del juez LLM (no validadas contra humanos); 45 de 50 proveedores son del sector salud (sesgo de muestra); el porcentaje sigue algo comprimido (exactas ronda 50–85 %); sumar BM25 sobre partidas y categoría UNSPSC probablemente amplíe el recorrido.

---

## 8. Limitaciones (leer antes de usar las cifras)

1. **Solo 100 positivos y N = 50 consultas.** Alcanza para detectar diferencias grandes (C vs A), no para ordenar estrategias parecidas (D vs C, E vs B). Los intervalos son anchos.
2. **Ruido de etiquetas.** Solo cuentan como relevantes las compras que ese proveedor ganó. Otras órdenes del mismo rubro ganadas por otros proveedores valen 0, por lo que las cifras absolutas **subestiman** la calidad real. Sirven para comparar estrategias, no como nota absoluta.
3. **Catálogo de 1.176 órdenes.** Es una muestra (~2 %) de lo que hay en un período. En producción el catálogo es mayor y más ruidoso; los valores absolutos no son extrapolables.
4. **El perfil se generó desde el historial de ventas.** Cubre el caso de un proveedor con historial. **El caso de un proveedor nuevo, que solo tiene lo escrito en el wizard, no está medido.** Es el caso más importante para el producto y hay que evaluarlo aparte.
5. **Las señales de C usan el historial** (categorías y regiones de las 3 primeras órdenes). Parte del acierto puede deberse a compradores y productos que se repiten.
6. **Sin repetición con otras muestras del catálogo.** No se midió la variabilidad por elegir otro conjunto de distractores.
7. Las 250 adjudicaciones y los distractores provienen del mismo mes; no se probó generalización a otros períodos.

---

## 9. Plan de acción para producción

1. **Adoptar búsqueda híbrida (denso + BM25 con partidas) en el primer estadio** y añadir las señales de región canónica y categoría UNSPSC como componentes de la fusión por RRF. Es la única mejora con evidencia estadística. Implementarla nativa en Qdrant (sparse + denso) en `rank_tenders.py` antes de tocar pesos.
2. **No priorizar el reranker** hasta que el primer estadio recupere mejor (Recall@100 ≥ 80 %); hoy solo cambia el orden dentro de un pool que ya tiene el 67 %.
3. **Llevar al backend la fórmula calibrada Rc+B+C** (en curso): implementar la calibración logística multivariante en `compatibility_percentage.py` con los coeficientes de §7.
4. **Medir el caso sin historial** (proveedor nuevo): perfil escrito en el wizard, sin categorías históricas. Es la prueba que falta para decidir el diseño del onboarding (pedir productos concretos y no solo sectores).
5. **Ampliar la muestra** (N ≥ 200 proveedores, más períodos) y aislar el aporte de región vs categoría con ablaciones.
6. **Validar el juez frente a humanos** (etiquetar el CSV de §6) y, cuando exista tráfico, sustituirlo por telemetría real: clicks, guardados y postulaciones.

---

## 10. Reproducir

```bash
# desde D:\ProyectosYA, con monorepo\backend\.venv activo y MERCADO_PUBLICO_API_KEY / GEMINI_API_KEY en monorepo\.env
python spikes/dataset_compra_agil/recolectar_muestra_temporal.py --por-dia 100 --pausa 0.5   # distractores (reanudable)
python spikes/dataset_compra_agil/recolectar_ocs_proveedores.py                              # OCs de los 50 proveedores (con fecha)
python spikes/dataset_compra_agil/construir_benchmark_temporal.py                            # split temporal + perfiles desde historial
python spikes/dataset_compra_agil/evaluar_benchmark_temporal.py                              # Tabla de métricas duras (§4)
python spikes/dataset_compra_agil/juez_claude_lotes.py exportar    # pool común en lotes (y "muestra" para el segundo juez)
#   -> los lotes data/temporal/juez_claude/entrada_*.json se juzgaron con subagentes de Claude (salida_*.json)
python spikes/dataset_compra_agil/juez_claude_lotes.py integrar    # une los juicios y calcula el acuerdo entre jueces
python spikes/dataset_compra_agil/evaluar_con_juez_temporal.py                               # Tabla con juez (§6)
python spikes/dataset_compra_agil/calibrar_compatibilidad.py                                 # Calibración univariante R, Rc, etc. (§7)
python spikes/dataset_compra_agil/calibrar_multivector.py                                    # Calibración multivariante Rc+B+C (§7)
```

Los scripts `evaluar_matching_ranking.py`, `construir_dataset_sin_fuga.py`, `generar_pool_y_validar_juez.py` y `evaluar_benchmark_riguroso_2250.py` corresponden a versiones anteriores del benchmark con los errores descritos arriba y **no deben usarse para sacar conclusiones**.
