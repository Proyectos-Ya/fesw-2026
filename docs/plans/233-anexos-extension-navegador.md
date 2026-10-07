# Plan Técnico: Anexos de Mercado Público, segundo llamado, datos del ranking y extensión de navegador

**Issue asociada**: Refs #233 (Spike 2: Evaluación y mejora de matching). Las decisiones 8 y 9 responden directo a sus criterios, y la 1, la 3 y la 4 alimentan la 9. Las decisiones 2, 5, 6 y 7 van más allá de sus criterios: se abren como sub-issues de #233 antes de implementarlas.
**Estado**: Aprobado
**Fecha**: 2026-10-03

---

## 1. Contexto y Objetivo

El porcentaje de compatibilidad se calcula solo con el título, la descripción y las
partidas de la Compra Ágil. Spike-2 diagnosticó que ese texto es corto y administrativo:
lo que de verdad se pide (requisitos, ítems, entregables, visita técnica) está en los
**anexos**, y hoy no entran a Chiripa.

- La API v2 (`/v2/compra-agil`) trae `documentos: [{id, nombre}]` por licitación
  (`tests/fixtures/mp_listado_cambios.json`), pero `_parse_to_dto` lo descarta y la API
  no sirve los archivos.
- La ficha pública `buscador.mercadopublico.cl/ficha?code=<COT>` los descarga sin login
  ni captcha (verificado el 2026-10-02), con un token anónimo y los endpoints
  `adjunto.mercadopublico.cl/.../adjuntos-compra-agil/{listar,encrypt,descargar}`.
- El asistente solo usa archivos subidos al chat de cada usuario. Se guardan en el disco
  de Railway, que se borra en cada deploy.
- La API también trae la fecha de cierre del segundo llamado y el llamado vigente
  (`convocatoria`), y hoy ambos se descartan.
- No se registra qué se muestra en el ranking ni qué se cliquea, así que el NDCG solo se
  mide offline (spike-2, que sigue en curso).
- La postulación (HdU 20, plan `docs/plans/230-generar-documentacion-postulacion.md`,
  que hoy está en `develop` y no en esta rama) también lee los adjuntos del chat por usuario (`adjuntos_del_usuario` en
  `use_cases/proposals/_documentos.py`) y calcula su huella con los bytes de esos
  archivos.

**Relación con el plan 230:** este plan resuelve los puntos 1 (extracción persistida),
2 (originales fuera del volumen de Railway, en R2 en vez de Supabase Storage), 3 (OCR) y
7 (adjuntos por empresa) de su §5.

**Objetivo:**
- Traer los anexos (subida manual validada y extensión de navegador).
- Guardarlos en Cloudflare R2.
- Extraer con Gemini un resumen estructurado y compartido, con citas.
- Usarlo en el asistente y en un matching en sombra.
- Registrar el ranking para medir NDCG en producción y priorizar anexos en sombra.
- La postulación en MP queda fuera, con el punto de extensión reservado.

**Fuera de alcance:**
- El visor en iframe: pospuesto, aunque los PDF igual quedan en R2.
- Planes de pago.
- La postulación.

---

## 2. Decisiones Técnicas y Arquitectura

| # | Decisión | Caso de uso / Servicio | Vista | Componente |
|---|---|---|---|---|
| 1 | Guardar la lista oficial de anexos | `TenderIngestionUseCase` → `TenderIngestionService` | `TenderDetailView` | `TenderIngestaDTO.documentos` → `tender_attachment` |
| 2 | Subida manual arriba en el detalle, validada contra MP (id + nombre normalizado, sha256) | `UploadTenderAttachmentUseCase` → `R2AttachmentStorage` | `TenderAttachmentsPanel` (bajo el header, antes de la tarjeta de análisis IA; reemplaza "Documentos asociados") | `DocumentAttachmentManager` por fila oficial |
| 3 | Fecha de cierre del segundo llamado | `TenderIngestionUseCase` + `sync_estados` (`cambio_desde_item`) | `TenderDetailView`, `TenderCard` (etiqueta "Segundo llamado") | `CambioDeEstado` + `call_number`, `first_call_closing_at`, `second_call_closing_at` |
| 4 | Extracción con Gemini y resumen compartido (contrasta presupuesto y fechas de 1.er y 2.º llamado con la API) | `ExtractAttachmentUseCase` → `GeminiAttachmentExtractionService`; `BuildTenderDigestUseCase` | `DigestCard`, `DiscrepancyCard` | `tender_digest` (JSON con citas por punto) |
| 5 | El asistente RAG y la postulación leen desde el panel | `AskTenderAssistantUseCase` → `GeminiTenderAssistantService`; `adjuntos_del_usuario` y `huella_del_analisis` (proposals) | `TenderAssistantDrawer` (solo lectura) | `DocumentContextDTO.text` / `file_uri`; la huella usa el sha256 de cada archivo |
| 6 | Lo compartido no filtra datos de nadie | `PromoteAttachmentUseCase` | Etiqueta "Solo tu empresa" / "Compartido" | Estados `private → shared / conflict` |
| 7 | Extensión Chrome/Edge/Firefox, lista para postular en el futuro | `LeaseFetchJobsUseCase` → `JobRunner` + `MpFichaAdapter` | Panel en la ficha de MP + popup | `SiteAdapter` (`attachments.list/download`; `quotation.submit` reservado) |
| 8 | Datos del ranking: NDCG en producción y prioridad de anexos en sombra | `LogRankingImpressionsUseCase` + `RecordTenderInteractionUseCase` → `RankingMetricsService` + `AttachmentPriorityShadowService` | `TenderCard` y `TenderDetailView` reportan impresiones e interacciones | `ranking_impression`, ganancias, `prioridad_sombra` |
| 9 | Matching enriquecido en sombra | `CompatibilityScorer.signals()` → `ShadowScoreService` | Ninguna (el % visible no cambia) | `matching_shadow_score`, colección Qdrant `tender_attachment_items` |

### Detalles que fijan el diseño

- **Archivos:**
  - El cliente sube directo a R2 con una URL PUT prefirmada que exige
    `x-amz-checksum-sha256`. El bucket es privado, con prefijos
    `private/{workspace}/{sha256}` y `shared/{tender}/{mp_document_id}/{sha256}`.
  - Los bytes no pasan por el proxy `/api` de Vercel ni por el proceso de la API.
  - Gemini lee desde R2 con `fileUri`, o desde la Files API como respaldo. Word y Excel
    se convierten a texto (`xlsx_to_text`, docx con `zipfile`).
- **Modelo de confianza:**
  - Una subida manual queda `private` hasta que el mismo sha256 llegue desde la
    extensión o desde otra empresa. Recién ahí se copia a `shared/`.
  - Dos hashes distintos para el mismo `mp_document_id` dejan el anexo en `conflict`
    (precisado en ADR 0002: solo cuentan las versiones respaldadas; una subida suelta no bloquea ni ve a las demás).
- **Procesamiento:**
  - `AttachmentProcessingScheduler` va en el lifespan, con el mismo patrón que
    `MilestoneRefreshScheduler`.
  - Cola en Postgres (patrón `tender_metadata`), `FOR UPDATE SKIP LOCKED`,
    concurrencia 1 y parseo en `asyncio.to_thread`.
  - Flags: `RUN_ATTACHMENT_PROCESSING` y `ATTACHMENT_GEMINI_DAILY_BUDGET`.
  - Gemini con la cabecera `x-goog-api-key`.
- **Segundo llamado:**
  - `closing_at` sigue al llamado vigente y no cambia de significado.
  - Las columnas nuevas son nullable.
  - `is_closed` no se toca hasta medir cómo transita la API entre llamados.
- **Ranking:**
  - Cada respuesta de `/tenders/recommended` lleva un `ranking_id` y guarda las
    posiciones servidas en segundo plano.
  - El frontend reporta la posición mostrada y las interacciones.
  - Ganancia por interacción: detalle 1; guardar, ficha MP, anexo y asistente 2;
    análisis y cotización 3.
  - Un job diario calcula NDCG@10 por `model_version`.
  - `prioridad_sombra` = 3·log1p(impresiones top-10 en 7 días)
    + 2·log1p(interacciones en 7 días) + 2·subida manual + urgencia de cierre.
  - La prioridad se guarda, pero la cola de la extensión no la usa hasta validarla.
- **Matching en sombra:**
  - Depende de que `spike-2-matching` llegue a `develop`: `compatibility_formula.py` y
    el `CompatibilityScorer` calibrado todavía viven solo en esa rama.
  - Variantes `att-text-v1` (resumen e ítems al final del texto del reranker, recortados
    para no pasar de 512 tokens) y `att-items-v1` (pseudo-partidas en una colección
    nueva, nunca en `tender_items`).
  - Se evalúa offline (spike-2) y con replay sobre las listas registradas en la decisión
    8.
  - Se activa solo con AUC +0,02 y sin descalibrar la escala, en un PR y ADR aparte.
- **Extensión:**
  - WXT (MV3), sesión propia de Supabase emparejada desde la web (magic link generado
    por el backend), y un bridge por content script, porque Firefox no soporta
    `externally_connectable`.
  - Reutiliza las cabeceras que manda la propia ficha de MP; no copia sus claves.
  - Los hosts de proveedor para la postulación futura van como
    `optional_host_permissions` y no se declaran ahora.
  - Disponible para todo usuario autenticado, detrás de `EXTENSION_ENABLED` y del kill
    switch `GET /extension/capabilities`.
- **Seguridad:**
  - El documento se trata como dato: `responseSchema`, sin herramientas, y salida sin
    URLs ni HTML.
  - Cada punto extraído lleva cita, y se verifica contra el texto cuando lo hay.
  - Impresiones y clics: 90 días crudos, después solo agregados.
- **Settings nuevas (opcionales; sin ellas, la función queda apagada):**
  - R2: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` y
    `R2_PUBLIC_BASE_URL`.
  - Procesamiento: `RUN_ATTACHMENT_PROCESSING`, `ATTACHMENT_GEMINI_DAILY_BUDGET` y
    `ATTACHMENT_MANUAL_UPLOADS_PER_MONTH`.
  - Flags: `MATCHING_SHADOW_ENABLED` y `EXTENSION_ENABLED`.
  - Pairing: `SUPABASE_SERVICE_ROLE_KEY`.
  - Todas van como dummies en `.github/workflows/ci.yml` y `pytest_env_defaults.py`.
- **Dependencias a aprobar:** `boto3` en el backend (o un módulo SigV4 propio), y `wxt`,
  `@supabase/supabase-js` y `zod` en `monorepo/extension`.

### Riesgos

- **Datos de origen:**
  - Solo vimos `documentos` en el listado; hay que capturar un detalle real.
  - MP publica la fecha del 2.º llamado aunque nunca se llegue a él.
- **Almacenamiento y extracción:**
  - R2 podría no validar el checksum en las URLs prefirmadas; el worker recalcula.
  - Si el CORS del bucket está mal configurado, falla en producción y no en local.
  - El costo y la latencia de Gemini por anexo todavía no se miden.
  - Las citas de PDF escaneados no se pueden verificar.
  - La segunda pasada del asistente duplica el costo de esa pregunta.
  - Al cambiar la fuente de los adjuntos, cambia la huella de la postulación. Los
    análisis existentes se marcan desactualizados una vez; hay que avisarlo en el PR.
- **Extensión y Mercado Público:**
  - La SPA de MP puede cambiar sin aviso; hay canario semanal y kill switch.
  - Términos de uso y redistribución: pedir un canal oficial a ChileCompra.
  - Las tiendas revisan `webRequest` y `scripting`; AMO exige el código fuente.
- **Ranking y matching:**
  - Sesgo de posición en el NDCG online: se reporta por posición, y más adelante con
    interleaving.
  - Pocas interacciones al inicio: se reporta con intervalo bootstrap.
  - Bucle de popularidad entre la prioridad y el matching.
  - El replay no ve las candidatas nuevas de la variante en sombra.

---

## 3. Desglose de Tareas (Checklist)

### Fase 0 — Factibilidad y documentación
- [ ] Crear sub-issues de #233 para las decisiones 2, 5, 6 y 7 (`gh issue create --parent 233`; `gh` no está instalado en la máquina de desarrollo).
- [ ] Correr `graphify update`: seis archivos del plan son posteriores al grafo.
- [ ] Spike R2 + Gemini: PUT prefirmado con checksum desde la extensión y la web, `fileUri` desde R2, costo y latencia por anexo, y calidad de citas sobre los 28 documentos de `spikes/spike-1/corpus/`.
- [ ] Spike del adaptador de la ficha en Chrome y Firefox, grabando fixtures HAR saneados.
- [ ] Capturar un detalle real de `/v2/compra-agil/{code}` para confirmar `documentos`.
- [ ] ADRs `0001` (R2 y prefijos), `0002` (confianza), `0003` (extensión y adaptador), `0004` (datos del ranking y NDCG online) y `0005` (matching en sombra).

### Fase 1 — Decisiones 1, 3 y 8 (backend)
- [ ] Red: tests de `_parse_to_dto` y `cambio_desde_item` con `mp_listado_cambios.json`: `documentos`, `call_number`, ambas fechas, la "Z" en hora de Chile y la regresión de `is_closed`.
- [ ] Green: migraciones `tender_attachment` y las columnas del 2.º llamado (nullable), upsert en `TenderIngestionUseCase`, `sync_estados` y el hito "Cierre segundo llamado".
- [ ] Red: tests de `ranking_id` y posiciones, atribución de clics, NDCG@10 calculado a mano y prioridad en sombra sin consumo.
- [ ] Green: `ranking_impression`, `tender_interaction`, `POST /tenders/{id}/interactions`, job diario de NDCG y `AttachmentPriorityShadowService`. Documentar las rutas con `summary`, `response_model` y `tags`.

### Fase 1 — Decisiones 1, 3 y 8 (frontend)
- [ ] Red (Vitest): la lista de anexos con su estado, la etiqueta y la 2.ª fecha solo cuando corresponde, y el reporte de la posición mostrada con filtros.
- [ ] Green: `TenderDetailView`, `TenderCard`, y los hooks de impresiones e interacciones en `HomeDashboard` y `MatchesDashboard`.

### Fase 2 — Decisiones 2, 4, 5 y 6
- [ ] Red: tests de upload-url (422 por nombre o extensión, fila ajena, `quota_exceeded`, `deduplicated`), `complete` con checksum distinto, transiciones `private/shared/conflict`, extracción con `respx` (citas obligatorias, discrepancias de 1.er y 2.º llamado, tope diario, prompt injection), asistente sin bytes con una sola segunda pasada, y postulación leyendo los adjuntos de la licitación con una huella estable.
- [ ] Green: `attachment_file`, `attachment_extraction`, `tender_digest`, `attachment_processing_job` y `attachment_upload_quota`; `IAttachmentStorage` (R2 y disco local); `GeminiAttachmentExtractionService`; scheduler; `AskTenderAssistantUseCase`; `adjuntos_del_usuario` y `huella_del_analisis`; hitos derivados de la extracción. Invocar `supabase-postgres-best-practices` antes de crear tablas.
- [ ] Frontend: `features/tender-attachments` (panel, `DigestCard`, `DiscrepancyCard`), quitar "Documentos asociados" y dejar el drawer en solo lectura. Vitest y Playwright del flujo de subida.
- [ ] Script de migración de `tender_chat_documents` (`legacy_chat`, `private`).

### Fase 3 — Decisión 7 (extensión)
- [ ] Scaffold `monorepo/extension` (WXT) y CI: lint, `tsc`, Vitest y `web-ext lint`.
- [ ] Red: adaptador con fixtures HAR (`adapter_broken`), bridge (origin, nonce, ventana), `by-code` sin descargas repetidas, y límites de la cola con `lease` vacío en sombra.
- [ ] Green: `extension_installation`, pairing, capabilities, `MpFichaAdapter`, `R2Uploader`, `lease` y `result`.
- [ ] Playwright con la extensión sin empaquetar contra una ficha falsa local, checklist manual en Edge y fichas de las tiendas.

### Fase 4 — Decisión 9 (matching en sombra)
- [x] Red: `signals()` idéntico a `score_many`, flag apagado sin escrituras, entrada de 512 tokens como máximo, pseudo-partidas fuera de `tender_items`, y replay sobre las listas registradas.
- [x] Green: refactor de `signals()`, `matching_shadow_score`, `tender_attachment_items` y jobs `shadow_score`.
- [x] Spike de evaluación, ADR de decisión (ADR-0005) y marco de activación para PR posterior.

---

## 4. Plan de Verificación y Pruebas

```bash
# Backend (monorepo/backend, .venv activo)
pytest tests/unit -m "not integration and not network"
pytest tests/integration
python -m scripts.migraciones
alembic heads
ruff check .

# Frontend (monorepo/frontend)
pnpm run test
pnpm exec tsc --noEmit
pnpm run test:e2e

# Extensión (monorepo/extension)
pnpm run test
pnpm exec web-ext lint
```

Recorrido manual:
1. Una licitación con `documentos` lista sus anexos y, si corresponde, la etiqueta
   "Segundo llamado" con ambas fechas.
2. Una subida con nombre incorrecto da 422. La correcta queda en `private/` y pasa a
   `ready` con su digest citado.
3. Al abrir el ranking se registran el `ranking_id` y las posiciones, y el job diario
   produce un NDCG@10.
4. La extensión sin empaquetar (Chrome y Firefox) sube solo los anexos que faltan. El
   mismo sha256 corrobora el archivo y lo pasa a `shared/`.
5. Con `MATCHING_SHADOW_ENABLED`, `matching_shadow_score` se llena y el % visible no
   cambia.
