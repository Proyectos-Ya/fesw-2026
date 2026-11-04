# Plan Técnico: HU-18 — Integración Workspaces

**Issue asociada**: Refs #313  
**Estado**: Aprobado  
**Fecha**: 2026-10-27  

---

## 1. Contexto y Objetivo

El tablero kanban, las licitaciones guardadas y las preferencias de match actualmente
están vinculadas a `user_id`, por lo que cada usuario tiene su propia vista
independiente. La HU-18 exige que operen a nivel de *workspace* (supplier): todos los
miembros del mismo espacio comparten un tablero único, ven las mismas licitaciones
guardadas y están sujetos al mismo umbral de match.

La infraestructura de workspaces (membresías, invitaciones, `WorkspaceContext`) ya
existe; el trabajo es propagar ese contexto a las entidades que todavía viven en
`user_id`. Fuera del alcance: no hay edición colaborativa en tiempo real ni carpetas
privadas por documento.

---

## 2. Diagnóstico de Estado Actual

| Entidad | Scoping actual | Target | Esfuerzo |
|---|---|---|---|
| `kanban_column` | `user_id` (personal) | `supplier_id` (workspace) | Alto |
| `kanban_card` | `user_id` (personal) | `supplier_id` (workspace) | Alto |
| `saved_tender` | `user_id` (personal) | `supplier_id` (workspace) | Medio |
| `export_job` | lista por `user_id` | lista por `supplier_id` | Bajo |
| `deep_analysis` | `supplier_id` ✓ | sin cambio | Ninguno |
| `quotation` | `supplier_id` ✓ | sin cambio | Ninguno |
| `notification_preference.threshold` | per-user | umbral global editable por admin | Medio |
| historial kanban | no existe | nueva tabla `kanban_event` | Medio |
| notificaciones kanban | no existe | nuevo kind + toggle per-user | Medio |

---

## 3. Decisiones Técnicas (confirmadas)

### 3.1 Kanban: agregar `supplier_id`, conservar `user_id` como autoría

`kanban_column` y `kanban_card` reciben `supplier_id UUID NOT NULL FK supplier`. El
campo `user_id` se conserva en ambas tablas con semántica de "quién lo creó / agregó"
(autoría, no propiedad). El workspace es el propietario lógico del tablero; el usuario
es el autor de cada elemento.

El constraint único en `kanban_card` cambia de
`(user_id, tender_id) WHERE archived_at IS NULL` a
`(supplier_id, tender_id) WHERE archived_at IS NULL`: una licitación no puede estar
activa dos veces en el mismo tablero de workspace.

**Estrategia de migración de datos:**
1. ADD COLUMN `supplier_id UUID NULLABLE`
2. UPDATE: para cada fila, asignar el `supplier_id` de la membresía activa más reciente
   del `user_id` correspondiente (`SELECT supplier_id FROM supplier_member WHERE
   user_id = ... AND status = 'active' ORDER BY updated_at DESC LIMIT 1`).
3. Filas sin membresía activa (huérfanas) → **eliminar** en la misma migración.
4. Si quedan duplicados por el nuevo constraint `(supplier_id, tender_id)` (dos
   usuarios del mismo workspace tenían la misma licitación), conservar el más
   reciente y archivar el otro con `archived_reason = 'migration_dedup'`.
5. ALTER COLUMN `supplier_id` SET NOT NULL.

### 3.2 Historial kanban: tabla `kanban_event`

Nueva tabla con los siguientes campos:

```
id           UUID PK default gen_random_uuid()
supplier_id  UUID NOT NULL FK supplier(id) ON DELETE CASCADE
user_id      UUID NOT NULL FK "user"(id) ON DELETE RESTRICT
event_type   VARCHAR(50) NOT NULL
entity_type  VARCHAR(20)          -- 'column' | 'card'
entity_id    UUID
tender_id    UUID
tender_title TEXT                 -- desnormalizado para display
details      JSONB                -- {from_column, to_column, old_name, new_name, ...}
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
```

`event_type` enum: `column_created`, `column_renamed`, `column_recolored`,
`column_reordered`, `column_deleted`, `card_added`, `card_moved`, `card_archived`,
`card_restored`, `card_removed`.

Los eventos se escriben **sincrónicamente dentro del mismo caso de uso** (mismo
commit de transacción): si falla el evento, falla la operación entera. Índices:
`(supplier_id, created_at DESC)`.

### 3.3 Notificaciones kanban

Se agrega `kanban_notifications_enabled: bool = False` a `notification_preference`
(nueva columna con `server_default = 'false'`). Se agrega `kanban_change` al enum
`NotificationKind`.

Cada mutación del kanban genera notificaciones vía `BackgroundTasks` para todos los
miembros del workspace con `kanban_notifications_enabled = True`, excluyendo al
actor.

### 3.4 Saved tenders: unicidad por workspace, operaciones idempotentes

La tabla `saved_tender` recibe `supplier_id UUID NOT NULL FK supplier`. La clave
única cambia a `(supplier_id, tender_id)`: una licitación se guarda una sola vez por
workspace. Se conserva `user_id` como auditoría ("quién la guardó primero").

**Comportamiento de los endpoints:**
- `POST /tenders/{id}/saved` — **idempotente**: si la licitación ya está guardada para
  el workspace (por cualquier miembro), devuelve 200 sin error. Implementar con
  `INSERT ... ON CONFLICT DO NOTHING`.
- `DELETE /tenders/{id}/saved` — desguarda para todo el workspace; cualquier miembro
  puede ejecutarlo sin restricción de autoría.
- `GET /tenders/saved` — retorna todas las guardadas del workspace; todos los miembros
  ven la misma lista.

**Migración:** para filas sin workspace activo → eliminar. Si dos usuarios del mismo
workspace tenían la misma licitación guardada, conservar la más antigua y eliminar
la otra.

### 3.5 Export jobs: visibilidad compartida

`ExportJobModel` ya tiene `supplier_id`. Solo se cambia el filtro del `LIST` de
`user_id == ctx.user_id` a `supplier_id == ctx.active_supplier_id`.

### 3.6 Umbral de match: campo en `supplier` + fallback

Se agrega `match_threshold: float | None` a `Supplier` / `SupplierModel` (nullable;
`CHECK (match_threshold > 0 AND match_threshold <= 1)`).

En `scan_supplier_for_alerts`, la resolución del threshold es:
1. Si `supplier.match_threshold` is not null → usar ese valor para todo el workspace.
2. Sino → usar `preference.threshold` del usuario individual (comportamiento actual).

Nuevo endpoint `PATCH /workspaces/{supplier_id}/match-threshold` (solo admin).

### 3.7 Deep analysis y quotations — sin cambio de schema

Ambas ya usan `supplier_id`. Se verifican los endpoints para confirmar que usan
`active_supplier_id` de `WorkspaceContext` de forma consistente y se cubren con tests
de integración multi-usuario.

---

## 4. Estrategia de Ejecución Agéntica

La historia se implementa con un **agente Opus como Scrum Master** que orquesta el
trabajo y toma decisiones de integración, más **agentes Sonnet** para desarrollo
atómico y revisión.

### Roles

| Rol | Modelo | Responsabilidad |
|---|---|---|
| **Scrum Master (SM)** | Opus | Lee este plan, descompone en worktrees, lanza agentes de cada ola, valida criterios de salida antes de pasar a la siguiente ola, resuelve conflictos de integración |
| **Dev Sonnet** | Sonnet | Tarea atómica con contexto self-contained: escribe tests primero (Red), implementa (Green), refactoriza |
| **Reviewer Sonnet** | Sonnet | Revisa el output de una ola: coherencia con AGENTS.md, convenciones del proyecto, ausencia de `any` en TS, no `create_all`, OpenAPI en routers |

### Olas de trabajo y paralelización

Las olas respetan el grafo de dependencias. Dentro de cada ola, los agentes corren
en paralelo en worktrees aislados.

```
OLA 1 (paralelo) ─────────────────────────────────────────────────────────
  [Dev-A] Migraciones Alembic (A1–A5)
  [Dev-B] Entidades de dominio (B1–B7)

    ↓ SM valida: alembic heads == 1 línea; entidades tienen supplier_id

OLA 2 (paralelo) ─────────────────────────────────────────────────────────
  [Dev-C1] Use cases kanban (existentes + record_event + list_events)
  [Dev-C2] Use case notify_kanban_change
  [Dev-C3] Use cases saved tenders
  [Dev-C4] Use case set_workspace_match_threshold

    ↓ SM valida: pytest tests/ verde; interfaces de repo consistentes

OLA 3 (paralelo) ─────────────────────────────────────────────────────────
  [Dev-D1] Infra: modelos SQLModel + repos kanban/kanban_event/notif/saved/supplier
  [Dev-D2] Contratos de API frontend (tipos TS, schemas actualizados)

    ↓ SM valida: modelos coherentes con entidades de dominio

OLA 4 (paralelo) ─────────────────────────────────────────────────────────
  [Dev-E1] Router kanban (WorkspaceContext + GET /kanban/events + BackgroundTasks)
  [Dev-E2] Routers notification / saved tenders / exports / workspace threshold
  [Dev-F1] Frontend: kanban service + HistoryPanel workspace-aware
  [Dev-F2] Frontend: workspace admin settings (umbral de match)
  [Dev-F3] Frontend: notificaciones kanban (toggle + display)
  [Dev-F4] Frontend: saved tenders hook + estado compartido por workspace
  [Dev-G]  Verificación CA5 (deep analysis) + CA6 (quotations) con tests multi-usuario

    ↓ SM valida: pnpm run test verde; OpenAPI en cada ruta

OLA 5 — Revisión y verificación ─────────────────────────────────────────
  [Rev-1] Revisión de migraciones: seguridad del data-migration, backward compat
  [Rev-2] Revisión backend domain/application: TDD, clean arch, convenciones
  [Rev-3] Revisión infra/routers: WorkspaceContext en todos los endpoints, no any
  [Rev-4] Revisión frontend: no any TS, pnpm run test:e2e flujos críticos

    ↓ SM genera resumen de observaciones; Dev agents hacen fix-ups
```

### Criterios de salida por ola (SM los verifica antes de lanzar la siguiente)

| Ola | Criterio de salida |
|---|---|
| 1 | `alembic heads` = 1 línea; todos los campos nuevos presentes en entidades de dominio; tests de entidades pasan |
| 2 | `pytest tests/kanban/ tests/saved_tenders/ tests/workspaces/` verde; interfaces de repo abstractas completas |
| 3 | Modelos SQLModel coherentes con entidades de dominio; repos implementan las interfaces |
| 4 | `pytest` completo verde; `pnpm run test` verde; OpenAPI (summary + tags + response_model) en todas las rutas nuevas o modificadas |
| 5 | Cero observaciones bloqueantes de los reviewers; `pnpm run test:e2e` verde en los 5 escenarios de integración |

### Briefing base para agentes Dev Sonnet

Cada agente Dev recibe en su prompt:
1. Ruta exacta a este plan técnico.
2. Extracto de `AGENTS.md` §2 (stack, TDD, clean arch) y `SKILL.md` §1–2 (TDD pre-commit, Conventional Commits).
3. La lista de tareas de **su ola** (solo las suyas).
4. Los archivos específicos a leer antes de escribir (`Read` obligatorio).
5. La instrucción explícita: "No hagas `git push`. Commitea localmente con `[AI Generated]`. No uses `any` en TS. No llames `SQLModel.metadata.create_all`."

---

## 5. Desglose de Tareas

### Ola 1-A — Migraciones Alembic (Dev-A, worktree aislado)

- [ ] **A1** Migración `kanban_workspace_scoping`:
  - ADD `supplier_id UUID NULLABLE` a `kanban_column` y `kanban_card`
  - UPDATE data-migration (membresía activa más reciente)
  - DELETE filas huérfanas (sin membresía activa)
  - Resolver duplicados en `(supplier_id, tender_id)` → archivar el más reciente con `archived_reason='migration_dedup'`
  - ALTER SET NOT NULL
  - DROP INDEX `uq_kanban_card_user_tender_active`
  - CREATE UNIQUE INDEX `uq_kanban_card_supplier_tender_active` ON `kanban_card(supplier_id, tender_id) WHERE archived_at IS NULL`

- [ ] **A2** Migración `kanban_event_table`:
  - CREATE TABLE `kanban_event` con esquema de §3.2
  - CREATE INDEX `ix_kanban_event_supplier_created` ON `kanban_event(supplier_id, created_at DESC)`

- [ ] **A3** Migración `kanban_notification_pref`:
  - ADD `kanban_notifications_enabled BOOLEAN NOT NULL DEFAULT FALSE` a `notification_preference`
  - Agregar `'kanban_change'` al enum `notificationkind` en Postgres

- [ ] **A4** Migración `saved_tender_workspace_scoping`:
  - ADD `supplier_id UUID NULLABLE` + data migration + DELETE huérfanas
  - Resolver duplicados: conservar el más antiguo, eliminar el resto
  - ALTER SET NOT NULL
  - DROP constraint único existente `(user_id, tender_id)`
  - CREATE UNIQUE `(supplier_id, tender_id)` en `saved_tender`
  - CREATE INDEX `ix_saved_tender_supplier_id`

- [ ] **A5** Migración `supplier_match_threshold`:
  - ADD `match_threshold FLOAT NULL CHECK (match_threshold > 0 AND match_threshold <= 1)` a `supplier`

- [ ] Verificar `alembic heads` → exactamente 1 línea antes de commitear

### Ola 1-B — Dominio (Dev-B, worktree aislado)

- [ ] **B1** RED: tests para `KanbanColumn` y `KanbanCard` con campo `supplier_id`
- [ ] **B2** GREEN: `domain/entities/kanban.py` — agregar `supplier_id: UUID` a ambas entidades
- [ ] **B3** RED + GREEN: `domain/entities/kanban_event.py` — nueva entidad `KanbanEvent` y enum `KanbanEventType`
- [ ] **B4** GREEN: `domain/entities/notification.py` — agregar `kanban_change` a `NotificationKind`; agregar `kanban_notifications_enabled: bool = False` a `NotificationPreference`
- [ ] **B5** RED + GREEN: `domain/entities/saved_tender.py` — agregar `supplier_id: UUID`; actualizar equals/hash si aplica
- [ ] **B6** GREEN: `domain/entities/supplier.py` — agregar `match_threshold: float | None = None`

### Ola 2-C1 — Use cases kanban (Dev-C1)

- [ ] Crear `application/repositories/kanban_event_repository.py` — interfaz `IKanbanEventRepository` (`save`, `list_by_supplier`)
- [ ] RED + GREEN: use case `record_kanban_event.py`
- [ ] RED + GREEN: use case `list_kanban_events.py` (paginado por `supplier_id`)
- [ ] Actualizar use cases existentes para aceptar `supplier_id` y llamar a `record_kanban_event` en cada mutación:
  - Todos los de columnas: create, update, delete, reorder
  - Todos los de tarjetas: add, move, remove, archive, restore
  - `list_archived_tenders.py` (filtrar por `supplier_id`)

### Ola 2-C2 — Use case notificaciones kanban (Dev-C2)

- [ ] RED + GREEN: `application/use_cases/kanban/notify_kanban_change.py`
  - Busca miembros activos del workspace con `kanban_notifications_enabled = True`
  - Excluye al actor
  - Crea `Notification` de kind `kanban_change` para cada uno
- [ ] Actualizar `application/use_cases/notifications/` si expone toggle de preferencia
- [ ] Tests unitarios con mocks de repos

### Ola 2-C3 — Use cases saved tenders (Dev-C3)

- [ ] RED + GREEN: actualizar `save_tender` para aceptar y persistir `supplier_id`
- [ ] RED + GREEN: actualizar `unsave_tender` para filtrar por `supplier_id`
- [ ] RED + GREEN: actualizar `list_saved_tenders` para filtrar por `supplier_id` (no por `user_id`)
- [ ] `save_tender` usa `INSERT ... ON CONFLICT DO NOTHING` — idempotente (200) si ya está guardada para el workspace

### Ola 2-C4 — Use case match threshold (Dev-C4)

- [ ] RED + GREEN: `application/use_cases/workspace/set_workspace_match_threshold.py`
  - Valida rol admin
  - Actualiza `supplier.match_threshold`
- [ ] Actualizar `scan_supplier_for_alerts.py` — resolver threshold: workspace → user fallback
- [ ] Tests unitarios con los dos caminos de fallback

### Ola 3-D1 — Infraestructura backend (Dev-D1)

- [ ] `infrastructure/repositories/kanban_model.py` — agregar `supplier_id` a `KanbanColumnModel` y `KanbanCardModel`
- [ ] Crear `infrastructure/repositories/kanban_event_model.py` — `KanbanEventModel` SQLModel
- [ ] Crear `infrastructure/repositories/kanban_event_repository.py` — implementación SQL de `IKanbanEventRepository`
- [ ] `infrastructure/repositories/kanban_repository.py` — todas las queries cambian `WHERE user_id =` a `WHERE supplier_id =`
- [ ] `infrastructure/repositories/notification_model.py` — agregar `kanban_notifications_enabled`
- [ ] `infrastructure/repositories/saved_tender_model.py` y `saved_tender_repository.py` — agregar `supplier_id`, cambiar queries
- [ ] `infrastructure/repositories/supplier_model.py` — agregar `match_threshold`
- [ ] Registrar `KanbanEventRepository` en DI / bootstrap
- [ ] `pytest` verde con los nuevos repos

### Ola 3-D2 — Contratos API / tipos frontend (Dev-D2)

- [ ] `monorepo/frontend/src/features/kanban/kanbanTypes.ts` — agregar tipos para `KanbanEvent`, `KanbanEventType`
- [ ] `monorepo/frontend/src/features/workspaces/types.ts` — agregar `matchThreshold?: number`
- [ ] `monorepo/frontend/src/features/saved-tenders/` — verificar que `SavedTender` no necesita campos nuevos en el frontend
- [ ] Tests de tipos (si existen en la feature)

### Ola 4-E1 — Router kanban (Dev-E1)

- [ ] Todos los endpoints de `/kanban/*` usan `Depends(workspace_context_dep)` y pasan `supplier_id = ctx.active_supplier_id`
- [ ] Nuevo endpoint `GET /kanban/events` → `list_kanban_events` con paginación (`limit`, `offset`)
- [ ] Endpoints de mutación agregan `BackgroundTasks.add_task(notify_kanban_change, ...)`
- [ ] `summary=`, `tags=["kanban"]`, `response_model=` en todas las rutas nuevas o modificadas

### Ola 4-E2 — Routers notification / saved tenders / exports / workspace (Dev-E2)

- [ ] `routers/notification.py` — exponer y aceptar `kanban_notifications_enabled` en GET/PATCH preferences
- [ ] `routers/tender.py` (saved tenders) — `GET /tenders/saved` filtra por `supplier_id`; POST/DELETE incluyen `supplier_id`
- [ ] `routers/exports.py` — `GET /exports` filtra por `supplier_id`; verificar que el endpoint de **descarga** individual también autorice a cualquier miembro activo del workspace (no solo al `user_id` que generó el job)
- [ ] `routers/workspace.py` — `PATCH /workspaces/{supplier_id}/match-threshold` (require_admin)
- [ ] OpenAPI en todas las rutas tocadas

### Ola 4-F1 — Frontend kanban (Dev-F1)

- [ ] `kanban.service.ts` — agregar `fetchEvents()` → `GET /kanban/events`
- [ ] `HistoryPanel.tsx` — extender (o crear pestaña separada) para mostrar `kanban_event[]`: tipo de evento, nombre de licitación, usuario autor, fecha
- [ ] `useKanban.ts` — sin cambio funcional si el API es backward-compatible
- [ ] Tests unitarios actualizados

### Ola 4-F2 — Frontend workspace admin (Dev-F2)

- [ ] Componente o sección en configuración de workspace para ajustar umbral de match (visible solo si `isAdmin`)
- [ ] Integrar con `workspaceService.setMatchThreshold()`
- [ ] Tests unitarios del componente

### Ola 4-F4 — Frontend saved tenders (Dev-F4)

- [ ] `savedTenders.service.ts` — verificar que `GET /tenders/saved` no necesita cambios en la llamada; actualizar si el endpoint devuelve campos nuevos
- [ ] `useSavedTenders.ts` — el estado "¿está guardada?" actualmente se deriva de `user_id`; cambiar para trabajar a nivel de workspace: una licitación está guardada si aparece en la lista del workspace, independientemente de quién la guardó
- [ ] Verificar que el botón guardar/desguardar refleja correctamente el estado compartido (si B la guardó, A la ve como guardada)
- [ ] Tests unitarios del hook actualizados

### Ola 4-F3 — Frontend notificaciones kanban (Dev-F3)

- [ ] Toggle "Notificaciones del tablero kanban" en la vista de preferencias de notificaciones
- [ ] Mostrar notificaciones de tipo `kanban_change` en el feed existente
- [ ] Tests unitarios

### Ola 4-G — Verificación CA5 y CA6 (Dev-G, paralelo con F)

- [ ] **CA5 — Deep analysis (análisis de compatibilidad)**: leer los endpoints de `deep_analysis` router y confirmar que todos usan `active_supplier_id` del `WorkspaceContext`; escribir test de integración con dos usuarios del mismo workspace donde usuario A genera el análisis y usuario B puede consultarlo
- [ ] **CA6 — Quotations (borrador de cotización)**: mismo check para el router de `quotation`; test de integración equivalente
- [ ] Si algún endpoint filtra adicionalmente por `user_id`, eliminar ese filtro y agregar el test correspondiente

### Ola 5 — Revisión (Reviewers paralelos)

- [ ] **Rev-1** Revisión de migraciones: seguridad del data-migration, backward compat, `alembic heads` == 1
- [ ] **Rev-2** Revisión domain/application: TDD completo, clean arch (no deps hacia infra), convenciones
- [ ] **Rev-3** Revisión infra/routers: `WorkspaceContext` en todos los endpoints modificados, no `create_all`, OpenAPI completo
- [ ] **Rev-4** Revisión frontend: no `any` TS, `pnpm run test` verde, `pnpm run test:e2e` en flujos críticos

---

## 6. Plan de Verificación y Pruebas

```bash
# Backend (desde monorepo/backend, con .venv activo)
alembic heads                          # debe devolver exactamente 1 línea
pytest tests/kanban/                   # board scoping + events + notify
pytest tests/saved_tenders/            # workspace-level list + unicidad
pytest tests/workspaces/               # match threshold endpoint
pytest                                 # suite completa, sin regresiones

# Frontend (desde monorepo/frontend)
pnpm run test                          # unitarios (Vitest)
pnpm run test:e2e                      # flujos críticos
```

### Escenarios de integración clave (Ola 5)

1. **Kanban compartido**: usuario A crea columna → usuario B (mismo workspace) la ve.
2. **Historial**: usuario A mueve tarjeta → `GET /kanban/events` retorna evento con `user_id` de A; usuario B lo ve.
3. **Notificación kanban**: B tiene `kanban_notifications_enabled=true` → después de acción de A, B recibe notificación `kanban_change`.
4. **Guardadas del workspace**: A guarda licitación → B la ve en su lista de guardadas; A intenta guardar la misma licitación del mismo workspace = idempotente (200).
5. **Umbral de match**: admin sube umbral a 85% → `scan_supplier_for_alerts` usa 0.85 para el workspace; usuario sin workspace sigue usando su umbral personal.

---

## 7. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Conflicto de unique constraint tras migración (duplicados `(supplier_id, tender_id)`) | Alta | La migración A1/A4 incluye paso explícito de deduplicación antes de crear el constraint |
| Cabezas múltiples de Alembic (5 migraciones en esta rama) | Media | Las migraciones A1–A5 se crean en cadena lineal; Dev-A verifica `alembic heads` al final |
| Agente Dev sobreescribe archivo que otro agente también modifica en paralelo | Media | SM asigna archivos sin solapamiento entre worktrees; `kanban.py` (domain) es de Dev-B, `kanban_repository.py` (infra) es de Dev-D1 |
| Regresión en notificaciones existentes al agregar `kanban_change` | Baja | Tests de `scan_supplier_for_alerts` cubren todos los kinds existentes antes del cambio |
| Frontend asume usuario único en kanban (estado de `useKanban`) | Media | Dev-F1 revisa si el hook necesita invalidar caché cuando otro miembro hace cambios; fuera de alcance el push en tiempo real, pero el refetch manual debe funcionar |
