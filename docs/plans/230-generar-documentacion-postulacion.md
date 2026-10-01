# Plan Técnico: Generación de Documentación de Postulación (Compra Ágil)

**Issue asociada**: Refs #230  
**Estado**: En Revisión  
**Fecha**: 2026-09-28 (reescrito: 2026-09-29)  

---

## 1. Contexto y Objetivo

La HdU 20 pide generar un borrador de postulación: nombre y descripción de la oferta, documentos necesarios y, si las bases lo exigen, un documento técnico. Los criterios de aceptación están en la issue #230; este plan no los repite y los cita como CA1…CA9.

**Alcance de esta versión:**

- **Solo Compra Ágil.** La ingesta ya trae solo Compra Ágil (`mercado_publico_client.py`, códigos `…-COT26`). Las licitaciones públicas quedan como trabajo futuro (§5).
- **La "experiencia registrada" son preguntas.** Cuando las bases piden algo que no se sabe de la empresa, se genera una pregunta ("¿Cuenta con experiencia en X?"). Las preguntas respondidas forman un banco **de la empresa**, se reutilizan en otras licitaciones y son la fuente que cita cada párrafo del borrador (CA5).
- **El flujo tiene dos fases:**
  1. **Factibilidad:** se generan y responden las preguntas, y se resuelven las discrepancias (CA6, CA7, CA8, CA9).
  2. **Redacción:** se escriben el nombre, la descripción, los documentos y el documento técnico condicional (CA1, CA2, CA5, CA6).

La versión anterior de este plan traía extracción de texto, Supabase Storage, OCR e índice híbrido. Ningún CA lo exige, así que salen de aquí y pasan a issues propias (§5).

---

## 2. Decisiones Técnicas y Arquitectura

### 2.1 Capacidades de la empresa: las preguntas capturan, las capacidades guardan

**Situación actual:**

- El banco de preguntas es estático y depende solo del rubro (`smart_question_service.py`). No está ligado a ninguna licitación: el `tender_id` de `question_model.py` está comentado.
- `AnswerQuestionUseCase` escribe `campo:respuesta` en `supplier.keywords`, pero **nunca marca la pregunta como respondida**.
- La empresa se resuelve con `get_by_user_id`, o sea sin la empresa activa.

**Decisión:** las preguntas son solo la forma de **capturar** un dato; lo que se guarda es una **capacidad** de la empresa. Si se guardara la pregunta en sí, el dato quedaría amarrado a su redacción:

- reutilizarlo dependería de que la IA empareje textos parecidos ("pavimentación urbana" frente a "obras viales"), lo que acumula duplicados;
- un "Sí" con texto libre no alcanza para citar "el proyecto" que pide el CA5;
- una certificación que vence no tiene dónde registrarse.

**Origen del diseño:** se rescata el modelo de la rama local `230-hu-20-1-banco-de-capacidades` (`domain/entities/capability.py`, `infrastructure/repositories/capability_model.py`), que nunca se subió. Se copia el diseño y el código útil sobre `develop`, en PRs cortos. **No** se fusiona la rama: además reemplazaba entero el sistema de preguntas del home y es demasiado grande para integrarla de una vez. Su migración (`d9d22b5370ff`) no se reutiliza: se genera una nueva desde la cabeza de `develop`. Si alguien la aplicó en su base local, primero debe hacer `alembic downgrade` a la revisión anterior (ver la guía de Alembic, "revisión huérfana").

**Tres tablas:**

| Tabla | De quién es | Contenido |
|---|---|---|
| `capability_question` | **Banco compartido** entre empresas | `question`, `target_field` (clave normalizada, por ejemplo `iso_9001` o `experiencia:pavimentacion`), `category` (rubro), `kind` (`capacidad` \| `certificacion` \| `experiencia_proyecto`), `work_type` (obligatorio solo en `experiencia_proyecto`), `options[]` con `{label, polarity}` (`afirmativa` \| `negativa` \| `neutra`), `origin` (`semilla` \| `ia`) y `active`. Restricción única (`category`, `target_field`): es la deduplicación del banco. |
| `capability_answer` | **Una empresa** | `supplier_id`, `question_id`, `answer`, `answered`, `omitted`, `tender_id` (licitación que motivó la pregunta, `SET NULL`), `answered_by_user_id` (nuevo), `valid_until` (nuevo, nullable: vigencia de una certificación), `generated_at` y `answered_at`. Restricción única (`supplier_id`, `question_id`) y `CHECK NOT (answered AND omitted)`. |
| `capability_evidence` | **Una empresa** (nueva) | Proyectos que respaldan la experiencia de la empresa: `supplier_id`, `answer_id` (FK **nullable**, `SET NULL`), `work_type` (obligatorio: se copia de la pregunta cuando cuelga de una respuesta, así la evidencia no pierde su clase si la respuesta se borra), `origin` (texto con `CHECK`: `manual` \| `mercado_publico`, default `manual`), `title`, `buyer` (mandante), `year`, `amount_clp` (nullable), `description`, `created_by_user_id` (nullable: una importación no tiene autor) y `created_at`. Es lo que el borrador cita como "el proyecto" del CA5. |

**Evidencia preparada para importarse (§5, punto 10).** En esta HdU toda evidencia es `manual` y cuelga de una respuesta. Aun así, dos decisiones del esquema se toman ya, porque cambiarlas después obligaría a una migración con datos:

- `answer_id` es nullable. Una orden de compra importada de Mercado Público no responde ninguna pregunta: es experiencia que existe por sí sola y se clasifica por `work_type`. Cuando cuelga de una respuesta, `work_type` se copia de la pregunta.
- `origin` existe desde el principio, con default `manual`.

Lo que **no** se agrega todavía: `confirmed_at` y el código externo con restricción única (para no duplicar una orden de compra en dos importaciones). Dependen de lo que entregue la API y quedan para después del spike. Mientras no existan, el catálogo solo incluye evidencias `manual`.

Siguiendo la rama original, `kind`, `origin` y `polarity` se guardan como texto con `CHECK` y no como `ENUM` de Postgres: sumar un valor no exige un `ALTER TYPE` en una migración que corre antes del despliegue.

**Catálogo de experiencia (`ExperienceCatalog`), rescatado:**

- No se guarda: se compone al leer, juntando el perfil de la empresa (certificaciones, regiones, rubros, años de experiencia), las respuestas vigentes y sus evidencias. Si se copiara, habría que mantenerlo sincronizado.
- Cada elemento tiene un **id estable** según su origen y clave: `perfil:certificacion:iso-9001`, `capacidad:<question_id>` o `evidencia:<id>`. Son los ids que la IA recibe y cita en `sources[]` (§2.4).
- `last_changed_at` es el máximo entre el último cambio del perfil y la última respuesta. Permite avisar que un borrador quedó desactualizado.
- Una respuesta con `valid_until` vencido no entra al catálogo y la pregunta vuelve a quedar pendiente.
- Una MiPyme tiene decenas de elementos en su catálogo, no miles: se envía completo en el prompt, sin búsqueda vectorial.

**Cómo entra una pregunta nueva al banco:**

1. En la factibilidad (§2.3), la IA recibe el catálogo de la empresa y las claves (`target_field`) del banco para su rubro.
2. Por cada exigencia devuelve una de tres cosas:
   - el id de un elemento del catálogo que la cubre,
   - la clave de una pregunta del banco que la empresa aún no respondió,
   - una pregunta nueva, con su clave, tipo y opciones.
3. Las preguntas nuevas pasan por `question_leaks_supplier_data` (rescatada), que rechaza un enunciado que nombre a la empresa por razón social, nombre de fantasía o RUT. Luego se insertan con `origin = ia`. Si la clave ya existe, la restricción única devuelve la existente.
4. Se crea la `capability_answer` pendiente con el `tender_id` de origen.

**Excluyente o deseable:** esto es una propiedad de la **exigencia de la licitación**, no de la capacidad. Por eso vive en `ProposalDraft.requirements[].mandatory` (§2.2) y no en el banco: la misma certificación puede ser excluyente en una Compra Ágil y deseable en otra.

- **Excluyente:** si no se cumple, la oferta queda fuera. Ejemplo: "el proveedor *deberá* contar con certificación SEC".
- **Deseable:** suma, pero no descarta. Ejemplo: "*se valorará* experiencia en el sector público".
- Lo decide la IA según la redacción: "deberá", "obligatorio" o "excluyente" frente a "se valorará" o "deseable".
- Solo una respuesta con polaridad `negativa` a una exigencia excluyente abre una discrepancia (§2.3). Una negativa a una deseable solo se registra.

**Por empresa, no por usuario:**

- `supplier_id` es el de la **empresa activa**, resuelta con `_empresa_activa(workspace_context)` (`routers/tender.py`) y `resolver_empresa` (`use_cases/supplier/resolver_empresa.py`). Nunca se usa `user_id`.
- Cualquier miembro con el permiso `generate_proposal` (§2.8) puede responder y agregar evidencia. La factibilidad y la redacción usan el catálogo completo de la empresa, sin importar quién respondió.
- Las respuestas **no** modifican `supplier.keywords` ni `certifications` (§5).

**Convivencia con el sistema de preguntas del home:** `profile_question`, `SmartQuestionsBanner` y `/questions` quedan como están en esta HdU. Migrar el banner al banco de capacidades y retirar `profile_question` es una issue aparte (§5). Así este trabajo no arrastra el reemplazo completo que hizo tan grande la rama original.

### 2.2 Entidad `ProposalDraft`

Tabla nueva `proposal_drafts`. Hay un borrador por empresa y licitación, con restricción única sobre (`supplier_id`, `tender_id`). Como el borrador es de la empresa, si un miembro lo detiene, otro puede reanudarlo.

| Campo | Contenido |
|---|---|
| `status` | `FEASIBILITY` (hay preguntas pendientes), `PAUSED` (discrepancia sin decidir, CA7), `STOPPED` (detenido por el usuario, CA9) o `READY` (borrador generado). |
| `requirements` (JSON) | Exigencias extraídas: `id`, `text`, `kind` (`certificacion` \| `experiencia` \| `disponibilidad` \| `condicion` \| `documento` \| `otro`; las dos marcadas no se preguntan), `mandatory`, `origin` (descripción, ítem o nombre del adjunto), `status` (`cumple` \| `no_cumple` \| `parcial` \| `desconocido`; `parcial` sale de una respuesta neutra como "En proceso de inscripción" y no pausa), `catalog_item_id` (el elemento que la cubre, si existe) y `capability_question_id` (la pregunta pendiente, si hace falta una). |
| `requires_technical_document`, `technical_document_reason` | Si las bases exigen documento técnico, y por qué (CA1). |
| `paused_requirement_id` | La exigencia cuyo "No" tiene el borrador en `PAUSED`. |
| `warnings` (JSON) | Advertencias aceptadas al elegir "continuar" (CA8), cada una ligada a su `requirement_id`: si la empresa corrige la respuesta a "Sí", la advertencia se quita sola. |
| `discrepancy_decisions` (JSON) | `requirement_id`, `capability_question_id`, `action` (`continue` \| `stop`), `user_id` y fecha (CA8, CA9). |
| `content` (JSON, nullable) | Secciones `offer_name`, `offer_description`, `required_documents[]` y `technical_document` (opcional). Cada una tiene párrafos con `text`, `sources[]` (ids de elementos del `ExperienceCatalog`: `perfil:…`, `capacidad:…` o `evidencia:…`, con su `label`) y `placeholders[]`. |
| `last_instructions` | Últimas instrucciones de regeneración (CA4). |
| `created_by_user_id`, `created_at`, `updated_at` | Auditoría. |

**Borradores vencidos:** el estado "vencido" no se guarda. Se calcula al leer con `Tender.esta_cerrada()`, así ningún `GET` escribe en la base.

**Estados:** las transiciones viven en el dominio como métodos de la entidad (`app/domain/entities/proposal.py`): `load_requirements`, `record_answer`, `decide(continue|stop)`, `resume`, `can_generate` y `mark_ready`. Una acción que no corresponde al estado lanza `InvalidProposalTransition` (409 en la API). Reglas que se fijaron al implementar:

- Al cargar las exigencias, una excluyente que ya está en "No" (la empresa lo respondió en otra licitación) pausa de entrada.
- Una respuesta nueva reemplaza la anterior: borra la decisión y la advertencia de esa exigencia.
- En `PAUSED` se puede responder de nuevo **solo** la pregunta de la exigencia pausada; responder otra lanza `InvalidProposalTransition`.
- `resume` vuelve a `FEASIBILITY` **sin** volver a pausar, para que la empresa pueda corregir la respuesta. Mientras la excluyente siga en "No" sin una decisión de continuar, `can_generate` es falso.
- Tras continuar, si queda otra excluyente en "No" sin decidir, se pausa en esa.
- Las fechas que vuelven del JSONB con "Z" se normalizan a UTC sin zona (`aware_to_utc_naive`, en `app/shared/datetime_utils.py`).

```text
FEASIBILITY ──"No" a exigencia excluyente──▶ PAUSED
PAUSED ──continuar con advertencia──▶ FEASIBILITY
PAUSED ──corregir la respuesta a "Sí"──▶ FEASIBILITY
PAUSED ──detener──▶ STOPPED ──reanudar──▶ FEASIBILITY
FEASIBILITY ──sin preguntas pendientes + generar──▶ READY ──regenerar──▶ READY
```

### 2.3 Fase 1: factibilidad y discrepancias (CA6, CA7, CA8, CA9)

1. **Análisis.** La IA recibe la ficha (descripción e ítems), los adjuntos, el `ExperienceCatalog` de la empresa y las claves del banco para su rubro (§2.1). Devuelve las exigencias, y cada una termina en uno de estos casos:
   - **Cubierta por el catálogo** (perfil, respuesta vigente o evidencia): queda con estado `cumple` y guarda su `catalog_item_id`.
   - **Desconocida:** se reutiliza una pregunta del banco con la misma clave o se registra una nueva, neutra y sin datos de la empresa. Se crea la respuesta pendiente de la empresa.
   - **En contradicción con el perfil:** por ejemplo, las bases exigen entrega en Arica y la empresa opera solo en la RM. Se genera una pregunta que expone la discrepancia ("¿Puede cubrir entregas en Arica?").
2. **Respuestas.** El usuario responde las preguntas una a una, eligiendo una opción. Cada opción tiene polaridad. Si responde "Sí" a una pregunta `experiencia_proyecto`, se le ofrece agregar el proyecto (mandante, año, monto): es opcional, pero sin él el borrador solo puede citar la capacidad y no el proyecto (CA5).
3. **Discrepancia (CA7).** Una respuesta de polaridad `negativa` a una exigencia excluyente pasa el borrador a `PAUSED`. Un modal muestra la cláusula, la respuesta y la recomendación: *"Recomendamos no postular: las bases exigen X y declaraste no contar con ello"*. Si el "No" viene de una respuesta anterior de la empresa (otra licitación), el modal lo dice: cuándo, quién y en qué licitación. Las opciones son:
   - **Actualizar respuesta:** responder de nuevo la pregunta de la exigencia pausada, sin detener ni reanudar. Un "Sí" (o una respuesta neutra) resuelve la pausa y vuelve a `FEASIBILITY`; un "No" la mantiene. Es la salida natural cuando el "No" es viejo y la empresa ya consiguió la certificación.
   - **Continuar con advertencia (CA8):** se guarda la decisión, se agrega la advertencia a `warnings` (y luego al borrador) y se vuelve a `FEASIBILITY`.
   - **Detener (CA9):** se guarda la decisión y el borrador pasa a `STOPPED`. La ficha muestra "Postulación detenida — Reanudar". Al reanudar, se vuelve a `FEASIBILITY` y se puede **cambiar la respuesta**, por ejemplo si la empresa consiguió la certificación.
4. **Pausa de la generación (CA7).** No se puede redactar mientras haya preguntas pendientes o el borrador esté `PAUSED` o `STOPPED`. `GenerateProposalUseCase` lo rechaza con un 409.

### 2.4 Fase 2: redacción (CA1, CA2, CA5, CA6)

- **Plantilla fija de Compra Ágil.** Tiene cuatro secciones: Nombre de la oferta, Descripción, Documentos necesarios y Documento técnico. La última aparece solo si `requires_technical_document` es verdadero (CA1).
- **Redacción con IA.** Gemini redacta el contenido de cada sección con `responseSchema` JSON, igual que `GeminiDeepAnalysisService`.
- **Vacíos (CA2).** La IA marca cada dato faltante como `[[INSERTAR: X]]`. Un parser determinístico del dominio lo convierte en una entrada de `placeholders` y en el texto visible *"(Por favor, inserte aquí el valor X)"*.
- **Fuentes (CA5).** El prompt entrega una lista cerrada de fuentes: los elementos del `ExperienceCatalog` con su id estable (campos del perfil, capacidades respondidas y proyectos de evidencia), y la IA solo puede citar esos ids. El caso de uso valida cada id y descarta los que no existen. Un párrafo que afirma experiencia y queda sin fuente recibe un placeholder. Este es el guardrail contra alucinaciones.
- **Advertencias (CA8).** Las `warnings` aceptadas se incluyen en el borrador como bloque destacado.
- **Etapas (CA6).** Cada fase es una petición distinta, así que el frontend siempre sabe en qué etapa está, sin SSE ni workers:
  - Mientras corre `POST /feasibility` muestra "Analizando bases y experiencia".
  - Mientras corre `POST /generate` muestra "Redactando nombre, descripción y documentos".
  - El timeout de Gemini en este servicio sube a 60 s, porque con adjuntos tarda más que el análisis profundo, que usa 30 s.

### 2.5 Regenerar (CA4)

`POST /regenerate` recibe `instructions` en texto libre. Se validan con `_validate_prompt_injection`, que hoy es un método privado de `GeminiDeepAnalysisService` y se extrae a un helper compartido. Luego se vuelve a redactar con las mismas fuentes y advertencias, y se guarda `last_instructions`.

### 2.6 Exportar a .docx (CA3)

- **Dependencia nueva, aprobada:** `python-docx`, en `requirements.txt`.
- **Estructura del archivo:**
  - H1 con el nombre de la oferta y un H2 por sección.
  - Los documentos necesarios como viñetas.
  - Los placeholders y las advertencias como **bloques destacados**: un párrafo sombreado con la etiqueta "Revisar". Se eligió esto en vez de comentarios nativos de Word porque es más simple de implementar.

### 2.7 Licitación cerrada

Si `Tender.esta_cerrada()`, todos los endpoints que escriben responden **409** con `TenderClosedForProposal`. En el frontend, el botón queda deshabilitado con el tooltip *"Esta licitación se encuentra cerrada para postulaciones"*. El detalle ya expone `is_closed`.

### 2.8 Permisos por rol

Se agrega el permiso `generate_proposal` para ADMIN y MEMBER. VIEWER puede ver el borrador y exportarlo, pero no escribir.

- **Dónde agregarlo:** en `_ROLE_PERMISSIONS` y en `ALL_PERMISSIONS` (`domain/entities/supplier_member.py`). Antes había tres listas copiadas a mano (`infrastructure/auth/dependencies.py`, dos veces, y `use_cases/workspace/switch_workspace.py`) y un permiso que faltara en una no llegaba al `WorkspaceContext`. En B0b esas tres listas pasaron a leer `ALL_PERMISSIONS`, y un test verifica que cubre todos los permisos de los roles.
- **Backend:** los endpoints que escriben responden **403** sin el permiso, con el mismo patrón que `routers/supplier.py` usa para `edit_company_profile`.
- **Frontend:** se usa `hasPermission("generate_proposal")` de `WorkspaceContext.tsx`.

### 2.9 Adjuntos

- Son opcionales: una Compra Ágil puede no tener bases adjuntas y basta con la descripción y los ítems.
- Se reutilizan los del asistente con `ITenderChatRepository.get_documents_by_chat` y `get_document_bytes`, y se envían a Gemini como `DocumentContextDTO`, igual que hoy. No hay extracción ni storage nuevo.
- El paso de factibilidad lista los adjuntos y permite subir más con el endpoint existente de subida.
- **Limitación conocida:** los adjuntos son por usuario (`tender_chat_documents.user_id`) y no por empresa. La factibilidad usa los del miembro que la lanza (§5).

### 2.10 Endpoints

Van en un router nuevo, `infrastructure/routers/proposal.py`, con el prefijo `/tenders/{tender_id}/proposal`. Todos declaran `summary`, `response_model` y `tags`, y usan la empresa activa.

| Método y ruta | Qué hace | CA | Permiso |
|---|---|---|---|
| `GET ""` | Estado, exigencias, preguntas, contenido y si está vencida | CA2, CA5, CA9 | ver |
| `POST /feasibility` | Crea o recupera el borrador y corre el análisis | CA6, CA7 | `generate_proposal` |
| `POST /questions/{capability_question_id}/answer` | Responde la pregunta de capacidad de la empresa activa; si la respuesta es negativa y la exigencia es excluyente, pasa a `PAUSED` | CA7 | `generate_proposal` |
| `POST /discrepancy` | `{requirement_id, action: continue \| stop}` | CA8, CA9 | `generate_proposal` |
| `POST /resume` | `STOPPED` → `FEASIBILITY` | CA9 | `generate_proposal` |
| `POST /generate` | Redacta el borrador | CA1, CA2, CA5, CA6 | `generate_proposal` |
| `POST /regenerate` | `{instructions}` | CA4 | `generate_proposal` |
| `GET /export.docx` | Descarga el Word | CA3 | ver |

**Router del banco de capacidades (`/capabilities`, B0b).** Opera sobre la empresa activa y es independiente de una postulación, así que el flujo de propuesta lo reutiliza:

| Método y ruta | Qué hace | Permiso |
|---|---|---|
| `GET /catalog` | Catálogo de experiencia con ids estables | ver |
| `POST /questions/{question_id}/answer` | Responde o corrige; guarda quién respondió y la vigencia | `generate_proposal` |
| `POST /questions/{question_id}/evidence` | Agrega un proyecto a un "Sí" de experiencia (409 si no hay "Sí") | `generate_proposal` |

El `POST /questions/{capability_question_id}/answer` del router de propuestas usa el mismo caso de uso y además actualiza el estado del borrador (puede pasarlo a `PAUSED`).

### 2.11 Frontend

Nueva feature `src/features/proposals/`, siguiendo la Screaming Architecture. La ruta `app/(app)/matches/[id]/postulacion/page.tsx` solo enruta. En `TenderDetailView` (`features/matches`) se agrega únicamente el botón de entrada.

---

## 3. Desglose de Tareas (Checklist TDD)

**Entrega en PRs cortos:** B0 → B1 → B2 + B3 → B4 a B7 → F1 a F6. Se pueden crear como sub-issues de #230. B0 y B1 llevan migración y conviene mergearlos temprano, cada uno en su PR (ver AGENTS.md §3, cabezas múltiples). Antes de B0 y B1 se invoca la skill `supabase-postgres-best-practices`.

### Backend (`monorepo/backend`)

- [x] **B0. Banco de capacidades** (§2.1, §2.8). Se rescata el diseño de `230-hu-20-1-banco-de-capacidades` copiando archivos puntuales (`git show <rama>:<ruta>`), no con merge ni cherry-pick. Se entrega en dos PRs.
  - [x] **B0a. Dominio y esquema** (PR propio y temprano, porque lleva migración)
    - [x] [Red] Entidades rescatadas: `CapabilityQuestion` (coherencia `kind`/`work_type`, opciones sin repetir, `polarity_of`), `CapabilityAnswer` (no respondida y omitida a la vez) y `question_leaks_supplier_data` (razón social, nombre de fantasía y RUT en cualquier formato). Se traen también sus tests de la rama.
    - [x] [Red] Nuevo: `CapabilityEvidence` exige título y año válido. Si tiene `answer_id`, solo se asocia a respuestas `afirmativa` de tipo `experiencia_proyecto` de esa misma pregunta y hereda su `work_type` (`evidence_for_answer`); sin `answer_id`, `work_type` se indica a mano. Siempre es obligatorio. `origin` vale `manual` por defecto y solo acepta `manual` o `mercado_publico`. Una respuesta con `valid_until` vencido no cuenta como vigente.
    - [x] [Green] Entidades, `capability_model.py` con `answered_by_user_id`, `valid_until` y la tabla `capability_evidence` (`answer_id` nullable con `SET NULL`, `origin` con `CHECK` y default `manual`), y una **migración nueva** desde la cabeza de `develop`, sin reutilizar `d9d22b5370ff` (quedó como `eead2dba418a`).
    - [x] [Green] Repositorio `ICapabilityRepository` / `SqlCapabilityRepository`, rescatado y ampliado con evidencias. Test de integración: la restricción única (`category`, `target_field`) deduplica y el `CHECK` de estado se cumple.
    - [x] `python -m scripts.migraciones` debe devolver una sola cabeza.
  - [x] **B0b. Casos de uso, catálogo, permiso y router `/capabilities`**
    - [x] [Red] `BuildExperienceCatalog` (rescatado): los ids estables `perfil:…` (incluye regiones), `capacidad:…` y `evidencia:…`, excluye las respuestas vencidas y **las evidencias que no sean `manual`**, y calcula `last_changed_at`.
    - [x] [Red] `RegisterCapabilityQuestion` (rescatado): rechaza enunciados que filtran datos de la empresa y, si la clave ya existe, devuelve la pregunta existente.
    - [x] [Red] `AnswerCapabilityQuestion` (rescatado y ampliado): resuelve la empresa activa, guarda `answered_by_user_id`, vigencia y licitación de origen (que no cambia al corregir), y no toca `keywords` ni `certifications`. Nuevo `AddCapabilityEvidence`.
    - [x] [Red] Por empresa: un miembro ve las respuestas y evidencias de otro miembro de la misma empresa, y otra empresa no las ve. Sin `generate_proposal` se recibe 403; VIEWER no lo tiene.
    - [x] [Red] Regresión: `GET /questions` y el banner del home no se tocan; la suite existente sigue en verde.
    - [x] [Green] Casos de uso, permiso `generate_proposal` y `ALL_PERMISSIONS` como única lista (§2.8), router `/capabilities` (§2.10) cableado en `bootstrap.py`, y test e2e `tests/e2e/api/test_capability_api.py`.
- [x] **B1. `ProposalDraft`** (§2.2)
  - [x] [Red] Máquina de estados: un "No" excluyente pasa a `PAUSED`; un "No" deseable no pausa; una neutra queda `parcial`; `continue` agrega una advertencia; `stop` pasa a `STOPPED`; `resume` vuelve a `FEASIBILITY` sin volver a pausar; `can_generate` es falso si hay pendientes, `PAUSED` o `STOPPED` (`tests/unit/domain/test_proposal.py`).
  - [x] [Red] El parser de `[[INSERTAR: X]]` produce placeholders y el texto visible (`render_placeholders`, `DraftParagraph.from_ai_text`).
  - [x] [Green] Entidad, `ProposalDraftModel`, migración `e4849ff0c0dd` de `proposal_drafts` con la restricción única (`supplier_id`, `tender_id`), repositorio SQL y en memoria, y `TenderClosedForProposal` (en `tender_errors.py`, junto a `TenderClosedForScoring` y `TenderClosedForAnalysis`).
- [x] **B2. Factibilidad (CA7)** (§2.3)
  - [x] [Red] Con un servicio de IA falso (`tests/unit/application/test_start_feasibility.py`):
    - una exigencia cubierta por el catálogo guarda su `catalog_item_id` y no crea pregunta; un id que no existe en el catálogo se descarta (guardrail),
    - una exigencia cubierta por una respuesta **negativa** previa queda `no_cumple` con su `catalog_item_id` **y** su `capability_question_id`: así el borrador explica el origen de la pausa y la empresa puede actualizar la respuesta desde la pausa. `ExperienceItem` suma `answered_at`,
    - una exigencia con una clave del banco reutiliza esa pregunta y crea la respuesta pendiente con `tender_id`; si la empresa ya la respondió, usa esa respuesta,
    - una pregunta nueva se registra en el rubro de la empresa (`origin = ia`, opciones Sí/No); si la clave ya existe, se reutiliza; si nombra a la empresa, no entra al banco y la exigencia queda `parcial`,
    - se detecta si las bases exigen documento técnico,
    - si ya hay borrador se devuelve sin llamar a la IA; una licitación cerrada sin borrador da 409.
  - [x] [Green] Puerto `IProposalAIService.analyze_feasibility`, `GeminiProposalService` y `StartFeasibilityUseCase`.
  - [x] [Red/Green] `GET /capabilities/questions/pending`: preguntas pendientes de la empresa activa (sin responder ni omitir, o con la vigencia vencida), cada una con su licitación de origen (`tender_id`, código y nombre). La empresa sale del contexto, como en el catálogo: la respuesta no incluye `supplier_id`.
  - [x] Adelantado de B7, para poder probar B2: `POST /tenders/{id}/proposal/feasibility` y `GET /tenders/{id}/proposal` (con `is_expired` calculado al leer). Router `routers/proposal.py`, e2e en `tests/e2e/api/test_proposal_api.py`.
  - Decisiones al implementar:
    - **Rubro del banco:** el primer sector de la empresa, en slug (`categoria_de`). La IA recibe solo las preguntas activas de ese rubro.
    - **Exigencia sin cobertura válida** (id inventado, sin pregunta o con una pregunta que nombra a la empresa): queda `parcial`. No bloquea la redacción; B4 la marcará como dato por completar.
    - **Prompt probado con Gemini real** sobre la Compra Ágil 657-70-COT26. Acepta el `responseSchema`, detecta la contradicción de cobertura (Coyhaique frente a una empresa de la RM) y propone preguntas. Hubo que aclarar qué **no** es documento técnico (cotización y formularios son documentos necesarios) y que, si las bases mencionan un adjunto no recibido (un TDR), se avise en `technical_document_reason`. `temperature: 0` porque la lista de exigencias cambiaba entre llamadas.
    - **Condiciones y documentos no se preguntan.** Probado con Gemini, la mayoría de las "exigencias" de una Compra Ágil eran condiciones del servicio (13 funcionarios, 40 horas, septiembre) o antecedentes a adjuntar (cotización, formulario), y generaban preguntas que cualquier proveedor responde que sí y que no sirven en otra licitación. Dos tipos nuevos de exigencia, `condicion` y `documento` (`KINDS_SIN_PREGUNTA`), quedan `cumple` sin pregunta aunque la IA proponga una. B4 usa las condiciones para describir la oferta y los documentos para la lista de documentos necesarios (CA1). El lugar de ejecución **no** es condición: se cruza con las regiones del perfil. Con Aysén en el perfil, la Compra Ágil 657-70-COT26 pasó de 4 preguntas a ninguna.
    - **Reintento y log:** un 429 o un 5xx de Gemini se reintenta una vez; si igual falla, el 502 deja la causa en el log (antes no quedaba rastro).
    - **Pendiente para B4 y la prueba manual (§6):** afinar la clasificación (Coyhaique salió como `experiencia` y no como `disponibilidad`; no cambia la lógica porque queda cubierta por el catálogo).
- [x] **B3. Discrepancias (CA7, CA8, CA9)** (§2.3)
  - [x] [Red] Casos de uso (`tests/unit/application/test_proposal_discrepancies.py`):
    - responder guarda en el banco de la empresa (con la licitación de origen y quién respondió) **y** mueve el borrador; un "No" excluyente lo pausa;
    - en pausa, otra pregunta no se guarda en ningún lado: se valida contra el borrador antes de escribir. La pregunta pausada sí se actualiza;
    - una pregunta que no es de la postulación da 404 y una respuesta fuera de las opciones da 422, sin escribir nada;
    - continuar guarda la decisión y la advertencia; detener pasa a `STOPPED`; reanudar vuelve a `FEASIBILITY`;
    - decidir sobre una exigencia distinta de la pausada da 409, porque el usuario decidió mirando una pausa que ya cambió;
    - con la licitación cerrada no se responde, decide ni reanuda (409).
  - [x] [Green] `AnswerProposalQuestionUseCase`, `DecideDiscrepancyUseCase`, `ResumeProposalUseCase` y el helper `postulacion_abierta`.
  - [x] Rutas (adelantadas de B7): `POST /tenders/{id}/proposal/questions/{question_id}/answer`, `POST /tenders/{id}/proposal/discrepancy` (`{requirement_id, action}`) y `POST /tenders/{id}/proposal/resume`, con permiso `generate_proposal`; e2e en `tests/e2e/api/test_proposal_api.py`.
  - [x] Corrección de B1: `content` vacío se guardaba como el JSON `null` y no como `NULL` de SQL (`JSONB(none_as_null=True)`, sin migración).
  - Queda fuera: responder desde `/capabilities/questions/{id}/answer` guarda en el banco pero no mueve los borradores abiertos. Si hace falta, el borrador puede releer el catálogo al abrirse; se decide con el frontend (F3).
- [x] **B4. Redacción (CA1, CA2, CA5)** (§2.4)
  - [x] [Red] Casos de uso (`tests/unit/application/test_generate_proposal.py`):
    - con documento técnico y sin él; si las bases lo exigen y la IA no lo escribe, la sección queda como vacío; si no lo exigen, se omite aunque la IA lo escriba;
    - vacíos `[[INSERTAR]]` convertidos en texto visible;
    - fuentes: se conservan las del catálogo con su etiqueta y se descartan las inventadas; un párrafo que afirma algo de la empresa (`asserts_company_fact`) sin fuente válida recibe el vacío "respaldo de esta afirmación";
    - documentos necesarios: primero los de la factibilidad (exigencias `documento`), después los que sume la IA sin repetir;
    - 409 con preguntas pendientes, en pausa, detenido o con la licitación cerrada, **antes** de llamar a la IA; si la IA falla, el borrador no cambia.
  - [x] [Green] `IProposalAIService.generate_draft`, `GeminiProposalService.generate_draft` (esquema propio, `temperature: 0.4` para que regenerar dé otro texto) y `GenerateProposalUseCase` con `armar_contenido`.
  - [x] Ruta (adelantada de B7): `POST /tenders/{id}/proposal/generate`; e2e en `tests/e2e/api/test_proposal_api.py`.
  - Las advertencias no se copian al contenido: viven en `ProposalDraft.warnings`, y el frontend y el `.docx` las muestran como bloque destacado (F6, B6).
  - **Probado con Gemini real** sobre la Compra Ágil 657-70-COT26: el nombre y la descripción usan las condiciones del servicio y el párrafo sobre la empresa cita sus fuentes. Gemini reescribía los documentos ya detectados ("Se adjunta la cotización formal…") y salían duplicados; ahora el prompt recibe la lista de documentos ya detectados y solo agrega los que falten.
- [x] **B5. Regenerar (CA4)** (§2.5)
  - [x] [Red] `tests/unit/application/test_regenerate_proposal.py`: redacta de nuevo con las instrucciones y las guarda en `last_instructions`; una instrucción con inyección se rechaza **antes** de llamar a la IA y el borrador no cambia; solo se regenera un borrador en `READY`; con la licitación cerrada, 409. Filtro en `tests/unit/shared/test_prompt_guard.py`.
  - [x] [Green] `app/shared/prompt_guard.py` (`frase_de_inyeccion`): la lista de frases que estaba dentro de `GeminiDeepAnalysisService`, ahora compartida, sin cambiar su comportamiento. `RegenerateProposalUseCase` delega en la redacción de B4 con `require_ready=True`.
  - [x] Ruta (adelantada de B7): `POST /tenders/{id}/proposal/regenerate` con `{instructions}`; 400 ante inyección, como en el análisis profundo. La redacción usa `temperature: 0.4` para que regenerar dé otro texto.
  - El asistente (`AskTenderAssistantUseCase.FORBIDDEN_PROMPT_PATTERNS`) mantiene su propia lista; unificarlas queda fuera de esta HdU.
- [x] **B6. Exportar a .docx (CA3)** (§2.6)
  - [x] [Red] `tests/unit/infrastructure/test_docx_proposal_exporter.py` abre el `.docx` y verifica: H1 con el nombre de la oferta y un H2 por sección; documentos necesarios como viñetas; documento técnico solo si existe; vacíos resaltados en amarillo y seguidos de un bloque "Revisar: completar X" sombreado; advertencias al inicio como bloques "Revisar"; sin las fuentes internas; con el código de la licitación y la marca de borrador. `tests/unit/application/test_export_proposal.py`: un borrador sin redactar da 409, con la licitación cerrada se sigue exportando y el nombre de archivo se sanea.
  - [x] [Green] `python-docx==1.2.0` en `requirements.txt` (dependencia aprobada en el plan), puerto `IProposalExporter`, `DocxProposalExporter` y `ExportProposalDocxUseCase`.
  - [x] Ruta (adelantada de B7): `GET /tenders/{id}/proposal/export.docx`, que cualquier miembro puede usar, también un VIEWER.
  - **Las fuentes no se exportan:** sirven para revisar en Chiripa, pero el archivo es lo que la empresa termina enviando al comprador.
  - **La imagen de Docker hay que reconstruirla** (`docker compose up -d --build api`), porque el `requirements.txt` cambió. El contenedor con `--reload` no instala dependencias.
- [x] **B7. Router** (§2.10). Se fue armando en B2–B6: cada etapa sumó sus rutas con su e2e, para poder probarla.
  - [x] [Red] `tests/e2e/api/test_proposal_api.py`: el flujo completo (factibilidad → responder → pausa → continuar o detener y reanudar → redactar → regenerar → exportar), empresa activa compartida entre miembros, 403 sin permiso, 409 con la licitación cerrada o ante una acción que no corresponde al estado, 502 si falla la IA.
  - [x] [Green] `routers/proposal.py` con `summary`, `response_model` y `tags` en las 8 rutas (`GET` del borrador, `feasibility`, `questions/{id}/answer`, `discrepancy`, `resume`, `generate`, `regenerate` y `export.docx`), más `GET /capabilities/questions/pending`, todo cableado en `bootstrap.py`.

### Frontend (`monorepo/frontend`)

- [ ] **F1. Tipos y servicio**
  - [ ] [Red/Green] `features/proposals/types.ts`, `services/proposalService.ts` y `hooks/useProposal.ts`.
- [ ] **F2. Entrada desde la ficha**
  - [ ] [Red] En `TenderDetailView`, el botón muestra "Generar postulación", "Continuar" o "Reanudar" según el estado. Queda deshabilitado con tooltip si la licitación está cerrada y oculto sin el permiso `generate_proposal`.
  - [ ] [Green] Botón y ruta `app/(app)/matches/[id]/postulacion/page.tsx`.
- [ ] **F3. Factibilidad (CA6)**
  - [ ] [Red] `ProposalStepper` muestra "Analizando bases y experiencia" mientras carga. `FeasibilityStep` lista las exigencias con su estado, las preguntas con sus opciones, el formulario opcional de proyecto tras un "Sí" de experiencia, y los adjuntos con un botón para subir más.
  - [ ] [Green] Implementación.
- [ ] **F4. Discrepancias (CA7, CA8, CA9)**
  - [ ] [Red] `DiscrepancyModal` muestra la cláusula, la recomendación y, si el "No" es de una respuesta anterior, su origen (fecha, quién, licitación). Los botones "Actualizar respuesta", "Continuar con advertencia" y "Detener" llaman al endpoint correcto. La vista `STOPPED` ofrece "Reanudar".
  - [ ] [Green] Implementación.
- [ ] **F5. Redacción (CA6)**
  - [ ] [Red/Green] `GeneratingLoader` con la etapa "Redactando nombre, descripción y documentos".
- [ ] **F6. Borrador (CA1, CA2, CA3, CA4, CA5)**
  - [ ] [Red] `ProposalDraftViewer` muestra las secciones, con el documento técnico solo si corresponde, y los placeholders destacados.
  - [ ] [Red] Al hacer clic en un párrafo se abre `SourcePanel` con el elemento del catálogo que lo respalda: el proyecto (mandante, año, monto), la capacidad (pregunta, respuesta, quién respondió y licitación de origen) o el campo del perfil.
  - [ ] [Green] `ProposalDraftViewer`, `SourcePanel`, `RegenerateDialog` y el botón "Exportar a .docx".
  - [ ] Playwright para el flujo crítico: factibilidad → discrepancia → continuar → borrador → exportar.

---

## 4. Matriz de Cobertura de Criterios de Aceptación

| CA (issue #230) | Backend | Frontend | Test |
|---|---|---|---|
| **CA1** Nombre, descripción, documentos y documento técnico condicional | `GenerateProposalUseCase`, `requires_technical_document` | `ProposalDraftViewer` | `test_generate_con_y_sin_documento_tecnico` / `ProposalDraftViewer.test.tsx` |
| **CA2** Vacíos marcados | Parser `[[INSERTAR]]`, `placeholders` | `ProposalDraftViewer` (destacado) | `test_parser_insertar` / `ProposalDraftViewer.test.tsx` |
| **CA3** Exportar a .docx | `ExportProposalDocxUseCase` (`python-docx`) | Botón "Exportar a .docx" | `test_export_docx_titulos_y_bloques_revisar` |
| **CA4** Regenerar con instrucciones | `RegenerateProposalUseCase` + helper anti-injection | `RegenerateDialog` | `test_regenerate_incorpora_instrucciones` |
| **CA5** Fuente de cada párrafo | `sources[]` validadas contra los ids del `ExperienceCatalog`, `capability_evidence` | `SourcePanel` | `test_fuentes_inexistentes_se_descartan` / `SourcePanel.test.tsx` |
| **CA6** Etapas visibles | Fases separadas `/feasibility` y `/generate` | `ProposalStepper`, `GeneratingLoader` | `ProposalStepper.test.tsx` |
| **CA7** Pausa y pregunta ante contradicción | `StartFeasibilityUseCase`, `AnswerProposalQuestionUseCase` → `PAUSED` | `DiscrepancyModal` | `test_no_excluyente_pausa_borrador` / `DiscrepancyModal.test.tsx` |
| **CA8** Continuar con advertencia | `DecideDiscrepancyUseCase(continue)` | Botón "Continuar con advertencia" | `test_continuar_guarda_decision_y_advertencia` |
| **CA9** Detener y reanudar | `DecideDiscrepancyUseCase(stop)`, `ResumeProposalUseCase` | Botón "Detener", vista "Reanudar" | `test_stop_y_resume_permite_cambiar_respuesta` |

---

## 5. Fuera de alcance (issues futuras)

1. **Extracción de texto de los adjuntos**, persistida, junto con el registro de `usage_metadata` de Gemini para medir el ahorro de tokens.
2. **Originales en Supabase Storage** en vez del volumen de Railway.
3. **OCR asíncrono** para bases escaneadas.
4. **Fragmentos e índice híbrido** (Qdrant + `tsvector`) para el asistente.
5. **Plantilla para licitaciones públicas.**
6. **Llevar las respuestas del banco al perfil y al matching**: `keywords`, `certifications` y reindexación.
7. **Adjuntos por empresa y no por usuario.** Se refiere solo a los archivos de `tender_chat_documents`; las respuestas ya son por empresa en esta HdU (§2.1).
8. **Migrar el banner del home al banco de capacidades** y retirar `profile_question`, `smart_question_service.py` y el guardado en `keywords`. La rama `230-hu-20-1-banco-de-capacidades` ya lo tiene hecho (incluida una página de experiencia de la empresa) y sirve de referencia.
9. **Volver a preguntar las respuestas negativas antiguas:** una negativa de hace meses puede ya no ser cierta. Queda pendiente definir el plazo.
10. **Spike: experiencia desde Mercado Público.** Las órdenes de compra adjudicadas a la empresa son experiencia verificable (mandante, monto, fecha).
    - **Hoy no se puede sacar de nuestra base:** la ingesta guarda que una licitación quedó "adjudicada", pero no a quién. Hay que consultar las órdenes de compra o las adjudicaciones por proveedor en la API. El spike debe confirmar qué permite consultar y con qué identificador (RUT o código de proveedor).
    - **Si es viable:** un caso de uso o job del backend crea evidencias con `origin = mercado_publico` y sin `answer_id` (el esquema ya lo permite, §2.1). Se agregan `confirmed_at` y el código externo con restricción única. El catálogo pasa a incluir las importadas **solo una vez confirmadas** por el usuario.
    - **El endpoint `POST /questions/{capability_question_id}/evidence` no es la vía de importación.** Se mantiene para los proyectos que no están en Mercado Público (clientes privados, otros canales) y para corregir lo importado.

---

## 6. Plan de Verificación y Pruebas

```bash
# Backend (con .venv activo)
cd monorepo/backend
pytest tests/unit tests/e2e/api/test_proposal_api.py
python -m scripts.migraciones

# Frontend
cd monorepo/frontend
pnpm run test src/features/proposals/
pnpm run test:e2e
```

**Prueba manual con Gemini real:** elegir 2 o 3 Compras Ágiles reales, una sin adjuntos, una con bases que exijan certificación y una que pida documento técnico, y recorrer el flujo completo con dos miembros de la misma empresa. Revisar:

- que las preguntas no se repitan en una segunda licitación similar,
- que cada párrafo cite una fuente real,
- que el `.docx` se abra bien en Word.
