# Plan Técnico: HdU 10 — Cierre de pendientes del tablero Kanban

**Issue asociada**: Refs #223
**Estado**: Aprobado
**Fecha**: 2026-10-07

---

## 1. Contexto y Objetivo

La HdU 10 (tablero Kanban para gestión de licitaciones) ya cuenta con el núcleo implementado: columnas con colores, tarjetas, mover entre columnas, modal "Agregar licitación" con recomendadas, editor por columna. Este plan cubre los **cuatro frentes pendientes** para dar por cerrada la historia:

1. **Archivado y registro histórico** (CA4).
2. **Selector de categoría en la vista de detalle de licitación** (CA3).
3. **Modal "Agregar licitación" con guardadas**.
4. **Editor general del tablero** (complemento al editor por columna existente).

Criterios de aceptación: ver issue #223. No se repiten acá.

---

## 2. Decisiones Técnicas y Arquitectura

### Transversales
- **Backend**: Clean Architecture ya establecida en `monorepo/backend/app/{domain,application,infrastructure}/`. Rutas en `infrastructure/routers/kanban.py`, modelo SQL en `infrastructure/repositories/kanban_model.py`, casos de uso en `application/use_cases/kanban/`.
- **Frontend**: Screaming Architecture en `monorepo/frontend/src/features/kanban/`. Hook central `useKanban`, servicio `kanban.service.ts`, componentes en `components/`.
- **Migraciones**: Alembic, compatibles hacia atrás (columnas nullable, sin renombres destructivos). Verificar `alembic heads` = 1 línea antes de abrir PR.
- **Sin `any` en TypeScript** (ver SKILL.md §3).

### Elemento 1 — Archivado y registro histórico (CA4)

**Modelo BD**: soft-delete en la asociación tender ↔ columna Kanban. Añadir en `kanban_model.py`:
- `archived_at: datetime | None` (nullable, default null).
- `archived_reason: enum('manual', 'auto_3m') | None` (nullable).
- `board_entered_at: datetime` (default `now()`, se setea al crear el link y **no cambia** al mover entre columnas).

**Scheduler**: nuevo `KanbanArchiveScheduler` en `infrastructure/services/kanban/`, siguiendo el patrón de `NotificationScheduler` y `MilestoneRefreshScheduler`. Lifespan de FastAPI, sesión propia por ejecución, armado en `bootstrap/runners.py`. Frecuencia: **diaria**. Regla: archivar links con `board_entered_at < now() - 90d` y `archived_at is null`, con `archived_reason='auto_3m'`.

**Restauración**: solo si `archived_reason='manual'`. Las auto-archivadas no se pueden restaurar (regla de negocio).

**Endpoints nuevos** (ver AGENTS.md §2 sobre `summary`/`response_model`/`tags`):
- `POST /kanban/cards/{id}/archive` — archivado manual.
- `GET /kanban/archive` — lista del historial del usuario, orden desc por `archived_at`.
- `POST /kanban/archive/{id}/restore` — restaurar manual (409 si `auto_3m`).

**Frontend**: icono (reloj) junto al título del tablero → panel lateral derecho estilo "Historial de versiones" (ver imagen de referencia). Lista más reciente → más antigua, cada entrada muestra: nombre licitación, fecha ingreso al tablero, fecha salida, razón, última columna. Botón "Restaurar" solo visible si fue manual.

### Elemento 2 — Selector de categoría en detalle de licitación (CA3)

**Ubicación**: `features/matches/components/TenderDetailView.tsx`, header junto al botón "Guardar". Dropdown "Agregar al tablero" que consume `list_kanban_columns`.

**Comportamiento**:
- Sin tablero/columnas: botón CTA "Crear tablero" que navega a `/tablero`.
- No en tablero: dropdown con columnas; seleccionar → `add_tender_to_board`.
- Ya en tablero: pre-selecciona la columna actual; cambiar → `move_kanban_card`.
- Opción al final del dropdown: "Quitar del tablero" → `POST /kanban/cards/{id}/archive` (manual).

**Backend**: verificar si `add_tender_to_board` acepta `column_id` y maneja "ya existe → mover"; si no, extender o usar `move_kanban_card` desde el frontend.

### Elemento 3 — Modal "Agregar licitación" con guardadas

**UX**: en `AddTenderModal.tsx`, agregar **tabs** en la parte superior: `Guardadas` (default) / `Recomendadas` (comportamiento actual).

**Tab Guardadas**:
- Consume `useSavedTenders` existente de `features/saved-tenders/hooks/`.
- Lista completa scrolleable, orden por fecha de guardado desc.
- **Oculta** las guardadas que ya están en cualquier columna del tablero.
- Click → mismo `onAdd(tender_id, column_id, tender)` que el flujo actual.

**Buscador**: mantiene su comportamiento global actual (reemplaza la vista mientras hay query), no filtra las tabs en vivo.

### Elemento 4 — Editor general del tablero

**Decisión**: mantener `KanbanColumnConfig.tsx` (popover rápido por columna) **y agregar** un modal "Editar tablero".

**Trigger**: ícono de engranaje en el header del Kanban, junto al título.

**Capacidades del modal general**:
- Lista vertical de columnas en orden actual.
- Renombrar inline, picker de color (reusar `PALETTE` de `KanbanColumnConfig.tsx`), eliminar con confirmación si tiene tarjetas.
- Reordenar por drag & drop (verificar si `@dnd-kit` ya está instalado en el frontend; si no, pedir confirmación antes de agregar).
- Botón "+ Agregar columna" al final.
- Cambios se persisten inmediatamente (consistente con el popover actual).

**Backend**: verificar si existe endpoint para reordenar columnas; si no, agregar `PATCH /kanban/columns/reorder`.

---

## 3. Desglose de Tareas (Checklist)

### Elemento 1 — Archivado y registro histórico (CA4)

**Backend**
- [ ] Red: tests para `archive_tender_from_board`, `list_archived_tenders`, `restore_tender`, y para el scheduler.
- [ ] Modificar `kanban_model.py`: `archived_at`, `archived_reason`, `board_entered_at`.
- [ ] Alembic: `alembic revision --autogenerate -m "kanban soft-delete y timestamps"`. Revisar diff. `alembic heads` debe devolver 1 línea.
- [ ] Casos de uso: `archive_tender_from_board.py`, `list_archived_tenders.py`, `restore_tender.py`.
- [ ] `KanbanArchiveScheduler` en `infrastructure/services/kanban/archive_scheduler.py` + wiring en `bootstrap/runners.py`.
- [ ] Endpoints en `routers/kanban.py` con `summary`, `response_model`, `tags=["kanban"]`.
- [ ] Filtrar en `list_kanban_cards` las tarjetas con `archived_at is not null`.

**Frontend**
- [ ] Red: Vitest para panel historial, servicio y botón archivar.
- [ ] `kanban.service.ts`: `archiveCard`, `listArchive`, `restoreCard`.
- [ ] `HistoryPanel.tsx` (panel lateral derecho, slide-in).
- [ ] Botón ícono "reloj" en header del Kanban.
- [ ] Acción "Archivar" en `KanbanCard.tsx` (menú contextual).

### Elemento 2 — Selector de categoría en detalle (CA3)

**Backend**
- [ ] Verificar si `add_tender_to_board` acepta `column_id` y maneja "ya existe → mover". Ajustar si no.

**Frontend**
- [ ] Red: Vitest para los 4 estados (sin tablero, no en tablero, en tablero, quitar).
- [ ] Componente `TenderBoardSelector.tsx` en `features/kanban/components/`.
- [ ] Integrar en `TenderDetailView.tsx` header.

### Elemento 3 — Modal "Agregar licitación" con guardadas

**Frontend**
- [ ] Red: Vitest para tab guardadas, ocultamiento de duplicados, click agrega.
- [ ] Agregar tabs en `AddTenderModal.tsx` (Guardadas / Recomendadas).
- [ ] Consumir `useSavedTenders`, filtrar las que están en el tablero.

### Elemento 4 — Editor general del tablero

**Backend**
- [ ] Verificar/crear `PATCH /kanban/columns/reorder` con tests.

**Frontend**
- [ ] Red: Vitest para apertura modal, renombrar, color, reordenar, agregar, eliminar.
- [ ] Verificar si `@dnd-kit` está instalado; coordinar con humano si no.
- [ ] `KanbanBoardEditor.tsx` (modal general).
- [ ] Botón engranaje en header del Kanban.

---

## 4. Plan de Verificación y Pruebas

```bash
# Backend (desde monorepo/backend con .venv activo)
pytest
python -m scripts.migraciones         # alembic heads = 1 línea

# Frontend (desde monorepo/frontend)
pnpm run test
pnpm run test:e2e                     # si se toca flujo crítico del Kanban
```

Verificación manual (ver skill `verify`):
- Flujo 1: agregar licitación desde detalle → aparece en tablero.
- Flujo 2: archivar manual → aparece en panel historial con botón restaurar.
- Flujo 3: mover tarjeta → `board_entered_at` NO cambia.
- Flujo 4: forzar `board_entered_at` > 90 días → scheduler la archiva como `auto_3m`, sin botón restaurar.
- Flujo 5: editor general → renombrar, reordenar, eliminar columna con tarjetas (confirmación).
