# Plan Técnico: [Nombre Breve de la Historia o Cambio]

**Issue asociada**: Refs #[Número de Issue]  
**Estado**: Borrador / En Revisión / Aprobado / Completado  
**Fecha**: AAAA-MM-DD  

---

## 1. Contexto y Objetivo
Breve resumen de la necesidad de negocio o requerimiento técnico que motiva este trabajo.  
*(No copies los criterios de aceptación de la issue; referencia directamente la issue).*

---

## 2. Decisiones Técnicas y Arquitectura
- Componentes o capas afectadas (Frontend Screaming Arch / Backend Clean Arch).
- Nuevas librerías, dependencias o variables de entorno requeridas (si aplica).
- Consideraciones de seguridad, rendimiento o compatibilidad.

---

## 3. Desglose de Tareas (Checklist)

### Backend
- [ ] Tarea 1 (Red: escribir pruebas unitarias en `monorepo/backend/tests/`)
- [ ] Tarea 2 (Green: implementar lógica en domain/application/infrastructure)
- [ ] Tarea 3 (Refactor y documentación de endpoints con summary/tags/response_model)

### Frontend
- [ ] Tarea 1 (Red: tests unitarios con Vitest en `src/features/<feature>/__tests__/`)
- [ ] Tarea 2 (Green: implementar componentes, hooks o servicios)
- [ ] Tarea 3 (Verificación visual o tests E2E con Playwright si es crítico)

---

## 4. Plan de Verificación y Pruebas
Comandos exactos para verificar la solución:
```bash
# Backend
pytest

# Frontend
pnpm run test
```
