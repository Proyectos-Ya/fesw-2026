# Plan Técnico: Gestión y Revocación de Acceso de Miembros del Equipo (HU-13)

**Issue asociada**: Refs #255  
**Estado**: En Progreso  
**Fecha**: 2026-09-28  

---

## 1. Contexto y Objetivo
Permitir a los administradores de una empresa registrada en Chiripa visualizar la actividad reciente (último acceso registrado) de los representantes vinculados a su organización y revocar su acceso en cualquier momento, garantizando que un miembro cuyo acceso sea revocado pierda inmediatamente la visibilidad sobre los recursos de la empresa (incluso si mantiene una sesión activa) y que los representantes regulares visualicen la nómina del equipo únicamente en modo lectura.

---

## 2. Decisiones Técnicas y Arquitectura
- **Registro de último acceso (`supplier_members.last_access_at`)**:
  - Se incorpora la columna nullable `last_access_at` (`DateTime`) en la tabla `supplier_members` mediante una migración de Alembic compatible hacia atrás (`down_revision = 'f1e2d3c4b5a6'`), poblando inicialmente las filas existentes con `updated_at`.
  - Para evitar escrituras redundantes en cada petición HTTP concurrente, `build_get_current_workspace_context` aplica una ventana de *throttling* de 5 minutos: solo ejecuta `UPDATE` sobre `last_access_at` cuando el campo es `NULL` o han transcurrido al menos 5 minutos desde la última marca registrada (además de actualizarse al aceptar una invitación o conmutar de espacio de trabajo).
- **Baja lógica en revocación de membresía (`MemberStatus.INACTIVE`)**:
  - La revocación actualiza `status = MemberStatus.INACTIVE` en `supplier_members` en lugar de eliminar físicamente la fila. Esto permite distinguir de forma determinista una membresía revocada frente a una cookie antigua de una empresa inexistente y preserva la posibilidad de re-invitar al usuario en el futuro sin violar `uq_supplier_member_user_supplier`.
  - Se prohíbe en dominio (`CannotRevokeOwnMembership`) y en interfaz que un administrador revoque su propio acceso.
- **Bloqueo en caliente ante sesiones activas (`403 Forbidden`)**:
  - En backend, `build_get_current_workspace_context` verifica en tiempo real el estado de la membresía en PostgreSQL para el espacio de trabajo solicitado (cookie `active_workspace_id` o cabecera `X-Workspace-Id`). Si el estado es distinto de `ACTIVE`, responde inmediatamente `403 Forbidden` incluso en rutas con contexto opcional (`/suppliers/me`, `/tenders/recommended`, `/tenders/search`).
  - Se expone `POST /workspaces/clear-active` para limpiar la cookie `httponly` `active_workspace_id` cuando el usuario revocado es redirigido al inicio.
  - En frontend, `apiFetch` (`src/features/shared/api/client.ts`) notifica mediante inversión de dependencias a `WorkspaceProvider` cuando recibe un `403` de acceso revocado, desplegando una vista bloqueante con acción directa para volver al inicio (`/`).

---

## 3. Desglose de Tareas (Checklist)

### Backend
- [ ] Agregar `last_access_at` a `SupplierMember`, `SupplierMemberModel` y `WorkspaceMemberDetailSchema`, junto con su migración Alembic lineal (`f1e2d3c4b5a6` $\rightarrow$ nueva cabeza).
- [ ] Escribir pruebas unitarias y E2E en rojo (`tests/unit/application/test_hu13_member_revocation.py` y `tests/e2e/api/test_workspace_invitations_api.py`) cubriendo registro de último acceso, revocación por administrador, bloqueo de auto-revocación, rechazo a no-administradores y bloqueo en caliente (`403 Forbidden`).
- [ ] Implementar `RevokeSupplierMemberUseCase`, actualizar `build_get_current_workspace_context` con *throttling* de `last_access_at` y validación estricta de membresía inactiva, y documentar las rutas `DELETE /workspaces/{supplier_id}/members/{member_id}` y `POST /workspaces/clear-active` en OpenAPI/Swagger.

### Frontend
- [ ] Escribir pruebas unitarias en Vitest (`CompanyTeamSection.test.tsx` y `WorkspaceContext` / `HomeDashboard`) para la columna de último acceso, confirmación de revocación, botón deshabilitado para el propio administrador, vista solo-lectura para miembros y pantalla bloqueante ante error `403`.
- [ ] Actualizar `types.ts`, `workspaceService.ts`, `client.ts`, `WorkspaceContext.tsx` y `CompanyTeamSection.tsx` cumpliendo las pruebas con tipado estricto (cero `any`).

---

## 4. Plan de Verificación y Pruebas
Comandos exactos para verificar la solución:
```bash
# Backend (Pruebas unitarias, E2E y verificación de cabeza única en Alembic)
pytest tests/unit/application/test_hu13_member_revocation.py tests/e2e/api/test_workspace_invitations_api.py -v
alembic heads
ruff check .

# Frontend (Pruebas unitarias y verificación de tipos)
pnpm exec vitest run src/features/company-profile/components/__tests__/CompanyTeamSection.test.tsx
pnpm exec tsc --noEmit
```
