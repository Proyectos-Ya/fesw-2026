# Plan Técnico: Postulación, preguntas basadas en las bases y feedback de carga

**Issue asociada**: Refs #292 (sub-issue de #230)  
**Estado**: Aprobado  
**Fecha**: 2026-10-07  

---

## 1. Contexto y Objetivo

Mejoras a la HU-20 que salieron al probarla con Compras Ágiles reales. Los problemas y los criterios de aceptación están en la issue #292; este plan no los repite.

El plan base de la HU-20 es [230-generar-documentacion-postulacion.md](./230-generar-documentacion-postulacion.md). Este plan solo describe lo que cambia.

Causas encontradas en el código:

- **Pocas preguntas.** En `StartFeasibilityUseCase._exigencia`, un elemento del perfil sin polaridad cubre la exigencia como `cumple` (`_ESTADO_POR_POLARIDAD[None]`). Si Gemini cita `perfil:descripcion` o un rubro para una exigencia de experiencia, no se pregunta nada.
- **Adjuntos sin prioridad.** En `GeminiProposalService` los adjuntos van al final del mensaje, después de la ficha, el catálogo y el banco, y ninguna regla dice que manden sobre la ficha.
- **Callejón al reanudar.** Tras `stop` y `resume`, la exigencia queda `no_cumple` con decisión `stop`. `can_generate()` es falso, pero `FeasibilityStep` solo ofrece responder las exigencias `desconocido`.
- **Timeout.** El cliente corta en 60 s (`REQUEST_TIMEOUT_MS`), pero Gemini tiene 60 s de timeout y un reintento.

---

## 2. Decisiones Técnicas y Arquitectura

### 2.1 Qué puede cubrir el perfil

Una función pura del dominio, `perfil_cubre(kind, item_id)`, en `app/domain/entities/proposal.py`, junto a `KINDS_SIN_PREGUNTA`:

| Elemento del catálogo | Cubre |
|---|---|
| `perfil:descripcion`, `perfil:sector:*`, `perfil:anios-experiencia` | Nada de tipo `experiencia` ni `certificacion` |
| `perfil:certificacion:*` | Una certificación |
| `perfil:region:*` | Disponibilidad en esa región |
| `capacidad:*`, `evidencia:*` | Igual que hoy |

Si la cobertura no vale, `_exigencia` pasa a la pregunta. Para que Gemini siempre deje una, el esquema suma `fallback_question` (misma forma que `new_question`), que se usa solo cuando la cobertura del perfil se descarta.

### 2.2 Los adjuntos mandan

- Orden de las partes en el análisis y la redacción: instrucciones, adjuntos, ficha, catálogo y banco.
- `_INSTRUCCIONES`: los adjuntos son la fuente principal de exigencias, mandan si contradicen a la ficha y `origin` lleva el nombre del archivo. El perfil genérico no prueba experiencia ni certificaciones específicas.
- `_INSTRUCCIONES_REDACCION`: las condiciones del servicio salen de las bases cuando existen.
- Campo nuevo en el esquema: `mentions_attachments` (la ficha menciona bases, TDR o anexos).

### 2.3 Con qué se analizó

Migración nueva, compatible hacia atrás, en `proposal_drafts`:

- `analysis_documents` (JSONB nullable): lista de `{name, corrupted}`.
- `mentions_attachments` (boolean nullable).

`StartFeasibilityUseCase` los llena y `GET /tenders/{id}/proposal` los devuelve. La migración va en un PR propio y temprano (AGENTS.md §3).

### 2.4 Frontend

Todo dentro de `src/features/proposals/`, salvo `Toast` y el `timeoutMs` de `apiFetch`, que van a `features/shared/` porque los puede usar cualquier feature.

- **`proposalStatus(view)`** en `utils/proposal.ts` devuelve `{tone, title, detail, action}` y lo muestra un `ProposalStatusBanner` único. Reemplaza los avisos sueltos de pausa y detenida.
- **Responder de nuevo:** `FeasibilityStep` lista las excluyentes `no_cumple` con última decisión `stop`. Si la respuesta vuelve a ser "No", `record_answer` borra la decisión y pausa de nuevo. No cambia el backend.
- **Recomendación de bases**, en tono informativo, no de advertencia: en `ProposalAttachments`, al iniciar sin adjuntos y en el borrador según `analysis_documents` y `mentions_attachments`.
- **Carga:** avisos `sticky`, etapa nueva `regenerating`, capa de carga sobre el borrador, `isLoading` en botones, `Toast` de confirmación y `useStageMessage`, que cambia el texto a los 10 y 30 s. El hook deja comentado que esos mensajes van por tiempo, no por avance real.
- **Colores:** rojo para lo que bloquea, ámbar para lo que hay que revisar, verde azulado para lo informativo.

### 2.5 Dependencias y seguridad

- No hay dependencias nuevas. `Toast` se hace a mano.
- No hay variables de entorno nuevas.
- **Tiempos límite**, decididos al implementar. Vercel corta a los 120 s un rewrite a un origen externo, en todos los planes y sin poder subirlo ([límites de Vercel](https://vercel.com/docs/limits)).
  - **Backend.** `GeminiProposalService` reparte un presupuesto de 100 s entre el intento y el reintento. El reintento solo usa lo que queda y no se hace si quedan menos de 20 s.
  - **Cliente.** `proposalService.ts` pasa `timeoutMs: 115_000` en las acciones que llaman a Gemini.
  - **Proxy local.** `next.config.ts` fija `experimental.proxyTimeout: 120_000`. El valor por defecto de Next son 30 s, y con 120 s el entorno local corta igual que Vercel.
  - **Recuperación.** Si el navegador pierde la respuesta (timeout, falla de red o 504), `useProposal` relee el borrador. Si cambió, muestra el resultado; si no, avisa que se perdió la conexión.

### 2.6 Fuera de alcance: SSE

Las etapas reales con Server-Sent Events quedan para una issue aparte, después de medir el cambio en las preguntas.

- **Backend:** FastAPI 0.141 trae `fastapi.sse` (`EventSourceResponse`), así que no hace falta una dependencia nueva. Los casos de uso recibirían un callback `on_stage`.
- **Frontend:** `EventSource` no sirve, porque solo hace `GET` y no manda `Authorization`. Se leería con `fetch` y `response.body.getReader()`.
- **Límite:** la llamada a Gemini no tiene avance interno. Para tener etapas reales dentro del análisis habría que partirlo en dos llamadas.

### 2.7 Segunda etapa: campos del formulario y uso de las respuestas

Decidida el 2026-10-07, después de revisar la guía del proveedor de Compra Ágil y el detalle de la API.

**Qué pide el formulario de Mercado Público** (guía del proveedor, paso 2, y `proveedores_cotizando[]` de la API):

| Campo | Regla | Dónde se prepara |
|---|---|---|
| Valor unitario neto por ítem | Obligatorio; incluye el despacho | Cotizador |
| Tipo de impuesto | Exento, IVA, honorario o zona franca | Cotizador |
| Adjuntar archivo | Opcional, 20 MB, "archivos que especifiquen tu cotización" | Documento técnico (Word) |
| Detalle de la cotización | Obligatorio, **máximo 255 caracteres** | `offer_description` |
| Fecha de vigencia | Obligatoria, referencial | Próximos pasos |
| Declaración Jurada de Habilidad | Se acepta en una ventana al enviar; no se adjunta | Próximos pasos |

La guía no muestra un campo de nombre de la oferta y la API no lo guarda por proveedor. Se mantiene "Nombre de la oferta" por decisión del equipo, por si la plataforma actual lo pide. La cotización ganadora de 657-70-COT26 tiene un detalle de 211 caracteres.

**Cambios:**

- **Detalle de la cotización (A).** `offer_description` pasa a ser un solo párrafo de hasta 255 caracteres (`MAX_DETALLE_COTIZACION` en el dominio): qué se ofrece, para quién y las condiciones clave. El prompt pide 230 como máximo para dejar margen. La interfaz lo rotula "Detalle de la cotización" y muestra un contador; si pasa de 255, lo marca y sugiere regenerar pidiendo un texto más corto. La Declaración Jurada de Habilidad no va en "Documentos necesarios", porque se acepta al enviar. "Próximos pasos" suma el tipo de impuesto, la fecha de vigencia y la declaración.
- **Editar respuestas ya dadas (B).** "Exigencias evaluadas" ofrece "Cambiar respuesta" en las que vienen de una pregunta. `record_answer` acepta respuestas en `READY`: actualiza la exigencia; si todavía se puede redactar, el borrador sigue `READY` y `changed_requirement_ids` avisa que el texto quedó desactualizado; un "No" excluyente pausa. Si la respuesta vino de otra licitación, la interfaz avisa que el cambio aplica a todas.
- **Exigencia enlazada con su respuesta (C).** En la redacción, cada exigencia con `capability_question_id` dice `cubierta por: capacidad:<id>`.
- **Proyectos de experiencia (D).** Después de un "Sí" a una pregunta `experiencia_proyecto`, la interfaz ofrece agregar el proyecto (título, mandante, año, monto y descripción) con `POST /capabilities/questions/{id}/evidence`, que ya existe. El catálogo lo incluye como `evidencia:<id>` y la redacción lo puede citar (CA5).

**Fuera de alcance:** la dirección y el plazo de entrega, los nombres de los adjuntos y los flags del detalle de la API. La ingesta no los guarda; quedan en la issue #294.

---

## 3. Desglose de Tareas (Checklist)

Entrega en tres PRs: migración (B1), backend (B2 a B4) y frontend (F1 a F6).

### Backend

- [ ] **B1. Migración** (antes: skills `supabase` y `supabase-postgres-best-practices`)
  - [ ] [Red] El repositorio guarda y lee `analysis_documents` y `mentions_attachments`.
  - [ ] [Green] Campos en `ProposalDraft` y `ProposalDraftModel`, migración nullable, `python -m scripts.migraciones` con una sola cabeza.
- [ ] **B2. Cobertura del perfil** (§2.1)
  - [ ] [Red] `test_proposal.py`: `perfil_cubre` en cada fila de la tabla.
  - [ ] [Red] `test_start_feasibility.py`: descripción o rubro citados para una experiencia generan pregunta con `fallback_question`; una certificación del perfil cubre la misma certificación; una región cubre la disponibilidad.
  - [ ] [Green] `perfil_cubre`, `fallback_question` en `FeasibilityRequirementDTO` y en `_SCHEMA`, y `_exigencia`.
- [ ] **B3. Adjuntos primero** (§2.2, §2.3)
  - [ ] [Red] `test_start_feasibility.py`: se guardan `analysis_documents` (con los dañados marcados) y `mentions_attachments`.
  - [ ] [Red] Test del servicio: los adjuntos van antes que la ficha en `partes`.
  - [ ] [Green] Orden de partes, prompts y campo `mentions_attachments`.
  - [ ] Prueba con Gemini real en 657-70-COT26 y 3885-281-COT26, con y sin bases. Registrar cuántas preguntas salen antes y después.
- [ ] **B4. API**
  - [ ] [Red] `test_proposal_api.py`: el `GET` expone los campos nuevos.
  - [ ] [Red] `test_proposal.py`: tras `stop` y `resume`, responder "Sí" habilita `can_generate()`.
  - [ ] [Green] `response_model` del router actualizado.

### Frontend

- [ ] **F1. Estado** (§2.4)
  - [ ] [Red] `proposal.test.ts`: `proposalStatus` en cada caso (pendientes, pausa, detenida, reanudada con "No", lista, lista con advertencia).
  - [ ] [Green] `proposalStatus`, `ProposalStatusBanner` y el texto vacío de la sección Borrador.
- [ ] **F2. Preguntas**
  - [ ] [Red] `FeasibilityStep.test.tsx`: en pausa, las pendientes explican por qué no se responden; tras reanudar, la exigencia detenida se puede responder de nuevo; el botón pulsado muestra que carga.
  - [ ] [Green] `FeasibilityStep` y la pregunta en curso en `useProposal`.
- [ ] **F3. Bases**
  - [ ] [Red] `ProposalView.test.tsx`: el aviso según `analysis_documents`, `mentions_attachments` y adjuntos subidos después del análisis.
  - [ ] [Green] Textos de `ProposalAttachments`, aviso al iniciar y aviso en el borrador.
- [ ] **F4. Carga**
  - [ ] [Red] `useProposal.test.ts`: etapa `regenerating` y `notice` al terminar. `ProposalDraftViewer.test.tsx`: capa de carga al regenerar. Test de `useStageMessage` con timers falsos.
  - [ ] [Green] Avisos `sticky`, etapa nueva, capa de carga, `isLoading` y `useStageMessage`.
- [ ] **F5. Shared**
  - [ ] [Red] `Toast` y `apiFetch` con `timeoutMs`.
  - [ ] [Green] `features/shared/components/Toast.tsx`, `timeoutMs` en `shared/api/client.ts` y su uso en `proposalService.ts`.
- [ ] **F6. E2E**
  - [ ] Playwright del flujo de postulación con la API mockeada, siguiendo `frontend/e2e/quotation.spec.ts`.

### Segunda etapa (§2.7)

- [ ] **A. Detalle de la cotización**
  - [ ] [Red] Backend: el prompt de redacción pide un párrafo de hasta 230 caracteres y aclara que la declaración jurada no se adjunta; `MAX_DETALLE_COTIZACION = 255` en el dominio.
  - [ ] [Red] Frontend: rótulo "Detalle de la cotización", contador y aviso sobre 255; "Próximos pasos" con impuesto, vigencia y declaración.
  - [ ] [Green] Ambos.
- [ ] **B. Editar respuestas**
  - [ ] [Red] Dominio: responder en `READY` actualiza la exigencia sin redactar; un "No" excluyente pausa; `changed_answers` la informa.
  - [ ] [Red] Frontend: "Cambiar respuesta" en exigencias evaluadas con pregunta, con aviso si la respuesta vino de otra licitación.
  - [ ] [Green] Ambos.
- [ ] **C. Exigencia enlazada** — [Red/Green] `_exigencias` agrega `cubierta por: capacidad:<id>`.
- [ ] **D. Proyectos**
  - [ ] [Red] Servicio `addCapabilityEvidence` y formulario `EvidenceForm` tras un "Sí" a `experiencia_proyecto`.
  - [ ] [Green] Formulario, servicio y toast "Proyecto agregado. Se usará al redactar o regenerar."

---

## 4. Plan de Verificación y Pruebas

```bash
# Backend (monorepo/backend, con .venv activo)
pytest tests/unit tests/e2e/api/test_proposal_api.py
python -m scripts.migraciones

# Frontend (monorepo/frontend)
pnpm run test src/features/proposals src/features/shared
pnpm run test:e2e
```

Prueba manual en el navegador, con el backend y Supabase arriba:

1. Analizar una Compra Ágil sin bases: aparece la recomendación de subirlas. Subirlas y volver a analizar: salen más exigencias y `origin` nombra el archivo.
2. Responder "No" a una excluyente: el banner explica la pausa y las pendientes dicen por qué no se responden.
3. Detener, reanudar y responder "Sí": se habilita "Redactar borrador".
4. Regenerar: capa de carga sobre el borrador, botón con spinner y confirmación al terminar.
5. Una redacción de más de 60 s no corta en el navegador.
