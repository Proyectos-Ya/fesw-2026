# ADR-0005: Matching Enriquecido en Sombra con Anexos Oficiales

* **Fecha**: 2026-10-05  
* **Estado**: Aceptado  
* **Autores**: Equipo Chiripa  

---

## 1. Contexto

En la plataforma Chiripa, el motor de emparejamiento semántico (*matching*, desarrollado en Spike 2) calcula la afinidad entre el perfil de una MiPyme proveedora y las licitaciones públicas disponibles en Mercado Público y Compra Ágil, utilizando un pipeline híbrido de filtrado vectorial y reordenamiento con modelos de lenguaje (*cross-encoder reranker*).

En la Fase 2 del Plan 233 se incorporó la ingesta y extracción estructurada de anexos oficiales mediante Gemini (`tender_digest`), produciendo resúmenes ejecutivos, entregables técnicos, cláusulas de multas y garantías. Esta información complementaria es crítica: con frecuencia, los metadatos base publicados por las entidades compradoras en Mercado Público (título somero y descripción breve) omiten especificaciones técnicas indispensables que determinan si una empresa puede o no postular con éxito.

No obstante, inyectar directamente esta información en la fórmula de puntuación en producción (`CompatibilityScorer.score_many()`) conlleva serios riesgos técnicos y de negocio:

1. **Riesgo de descalibración de la escala:** La escala de afinidad ([0.0, 1.0]) y sus umbrales operativos ("Recomendado", "Evaluar con cautela", "No recomendado") fueron minuciosamente calibrados. Modificar las señales de entrada de forma no supervisada podría sesgar al alza o a la baja los puntajes globales.
2. **Restricción de contexto del Reranker (512 tokens):** Los modelos cross-encoder operan con una ventana rígida de 512 tokens (~2048 caracteres). Concatenar texto indiscriminadamente causaría un truncamiento silencioso del final del texto o, peor aún, desplazaría la descripción base de la licitación.
3. **Contaminación de la fuente de verdad:** La tabla de partidas de la licitación (`tender_items`) refleja estrictamente los ítems licitados oficiales en Mercado Público. Mezclar partidas tentativas inferidas desde bases administrativas generaría inconsistencias contractuales.
4. **Falta de validación contra comportamiento real:** No es posible asegurar a priori si un ranking enriquecido con anexos generará mayor interés, clics y postulaciones efectivas sin medir su rendimiento frente al comportamiento histórico de los usuarios.

---

## 2. Decisión Tomada

Se implementa una **arquitectura de evaluación de emparejamiento en sombra (*Shadow Matching*)**, formalizada en la Decisión 9 del Plan 233, gobernada por las siguientes directrices arquitectónicas:

### 2.1. Feature Flag y Modo Inerte (`MATCHING_SHADOW_ENABLED`)
El sistema incorpora el flag de configuración `matching_shadow_enabled: bool = False` en `app/config.py`.
- **Cuando está inactivo (`False`, por defecto):** No se ejecuta ninguna escritura ni lectura en las tablas de sombra. El impacto en rendimiento de la base de datos y memoria en producción es estrictamente nulo.
- **Cuando está activo (`True`):** El caso de uso `ComputeShadowScoreUseCase` calcula las puntuaciones de sombra y las persiste exclusivamente en tablas desacopladas.

### 2.2. Aislamiento Total de Producción
Se garantiza que la experiencia del usuario final no se vea alterada:
- Las puntuaciones de sombra se almacenan en `matching_shadow_score`, manteniendo intacta la tabla productiva `matching_result`.
- Las pseudo-partidas extraídas de los anexos se guardan en la tabla dedicada `tender_attachment_item`, sin tocar jamás la tabla oficial `tender_items`.

### 2.3. Refactor y Equivalencia Matemática de `CompatibilityScorer.signals()`
Se refactoriza el servicio central de compatibilidad para exponer `signals(supplier, tender, tender_text=None, digest=None) -> CompatibilitySignals`, descomponiendo los componentes individuales (`reranker_score`, `best_match`, `coverage`, `final_score`).
- Se verifica contractualmente mediante pruebas automatizadas que, cuando `digest is None`, `signals().final_score` produce un resultado **matemáticamente idéntico** al método productivo `score_many()`.

### 2.4. Recorte Estricto de Texto a 512 Tokens
El servicio `TextBuilder.build_from_tender_with_digest()` formatea el texto combinado imponiendo un límite absoluto de 512 tokens (~2048 caracteres):
- El texto base de la licitación (título + descripción) se preserva íntegramente con máxima prioridad.
- El texto agregado proveniente del digest de los anexos (resumen y requisitos) se anexa al final y es el único sujeto a recorte si se sobrepasa el presupuesto disponible de caracteres.

### 2.5. Variantes de Enriquecimiento
Se definen formalmente dos variantes experimentales:
- `att-text-v1`: Enriquecimiento textual directo incorporando el digest recortado al texto suministrado al reranker.
- `att-items-v1`: Enriquecimiento a nivel de partidas comparando las capacidades del proveedor contra las pseudo-partidas de `tender_attachment_item`.

### 2.6. Evaluación y Replay Offline/Online (`ReplayShadowRankingUseCase`)
Aprovechando la telemetría de ranking implementada en la Decisión 8 (`ranking_impression` y `tender_interaction`):
- `ReplayShadowRankingUseCase` reconstruye las listas de licitaciones efectivamente servidas a los usuarios en sesiones reales.
- Reordena retrospectivamente dichas listas utilizando los puntajes calculados por las variantes de sombra y calcula la variación en NDCG@10 ($\Delta NDCG@10$).

### 2.7. Criterio Estricto de Promoción a Producción
Ninguna variante de sombra sustituirá el algoritmo en producción de forma automática. La promoción a producción exigirá un PR independiente y requerirá demostrar:
1. Incremento de AUC $\ge +0{,}02$ o $\Delta NDCG@10$ positivo con significancia estadística.
2. Preservación de la calibración de la escala sin inflación de falsos positivos.
3. Latencia p95 de scoring dentro de los límites operacionales del servicio.

---

## 3. Alternativas Consideradas

| Alternativa | Razón del descarte |
|---|---|
| **A/B Testing en Vivo Directo (50/50 de usuarios con algoritmo modificado)** | Riesgo inaceptable de degradar la experiencia y pérdida de confianza de MiPymes reales que dependen de las recomendaciones diarias para ofertar. |
| **Inyección de pseudo-partidas directamente en `tender_items`** | Ruptura de la integridad referencial y de la fuente de verdad oficial de Mercado Público. Habría provocado discrepancias con las API públicas y los procesos de sincronización/actualización de licitaciones. |
| **Paso de texto de anexos sin límite de tokens** | Inútil y riesgoso: los modelos cross-encoder descartan silenciosamente cualquier contenido más allá del token 512, lo cual truncaría arbitrariamente información sin control del sistema. |
| **Cálculo de sombra en memoria sin persistencia** | Impediría auditar retrospectivamente por qué una licitación varió de posición y haría imposible el análisis offline de correlación con las interacciones registradas. |

---

## 4. Consecuencias

### Positivas
- **Cero riesgo para usuarios de producción:** Permite investigar y calibrar modelos complejos con datos y tráfico reales sin alterar la interfaz ni los porcentajes mostrados.
- **Trazabilidad y auditoría experimental:** Cada cálculo de sombra registra su variante (`variant_id`), fecha y puntuación, facilitando comparaciones reproducibles.
- **Monitoreo cuantitativo con métricas estándar:** Posibilita el cálculo continuo de $\Delta NDCG@10$ sobre impresiones y clics reales antes de tomar decisiones definitivas de despliegue.

### Negativas / Compromisos
- **Consumo de almacenamiento y cómputo cuando el flag está activo:** Ejecutar el scoring duplicado incrementa el tiempo de procesamiento y el espacio en base de datos en la tabla `matching_shadow_score`.
  - *Mitigación:* Gobernado por `MATCHING_SHADOW_ENABLED` (apagado por defecto) y ejecutable de forma asíncrona o por lotes programados.
