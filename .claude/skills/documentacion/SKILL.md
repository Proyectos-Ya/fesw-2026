---
name: documentacion
description: Guía paso a paso para crear o actualizar la documentación de Chiripa. Úsala siempre que vayas a empezar una historia de usuario o cambio no trivial (plan técnico), tomar o registrar una decisión de arquitectura (ADR), cerrar un sprint o redactar un changelog, o editar AGENTS.md, CLAUDE.md o GEMINI.md.
---

# Skill de Documentación — Chiripa

Esta skill estandariza el proceso de documentación técnica en el repositorio. Garantiza que cualquier agente de IA o desarrollador registre el progreso de forma consistente y estructurada.

---

## 1. Tabla de Decisión

Consulta esta tabla para saber qué documento crear y qué referencia consultar según tu tarea:

| Situación / Evento | Tipo de Documento | Ubicación | Guía de Referencia |
|---|---|---|---|
| Vas a empezar una HdU o cambio no trivial | **Plan Técnico** | `docs/plans/<issue>-<slug>.md` | [plan-tecnico.md](./references/plan-tecnico.md) |
| Se toma una decisión técnica o de diseño importante | **ADR** | `docs/decisions/<NNNN>-<slug>.md` | [adr.md](./references/adr.md) |
| Se cierra un sprint o ciclo de trabajo | **Changelog** | `docs/changelogs/sprint-<N>.md` | [changelog-sprint.md](./references/changelog-sprint.md) |
| Creación de endpoint o ruta de API | **OpenAPI / Swagger** | Parámetros en el router FastAPI | [api-openapi.md](./references/api-openapi.md) |
| Actualización de reglas operativas de agentes | **Reglas de Agentes** | `AGENTS.md` / `SKILL.md` | [AGENTS.md](../../../AGENTS.md) |

---

## 2. Reglas Transversales

1. **Separación de roles (QUÉ vs CÓMO)**:
   - Las **GitHub Issues** contienen el **QUÉ** (los requerimientos y criterios de aceptación acordados con negocio).
   - Los documentos en **`docs/`** contienen el **CÓMO** (el diseño técnico, dependencias y pasos de implementación).
   - **Nunca copies y pegues** los criterios de aceptación en un documento: enlaza siempre la issue usando `Refs #NNN` o `Closes #NNN`.

2. **Uso de Plantillas Oficiales**:
   - Siempre utiliza las plantillas predefinidas ubicadas en [assets/](./assets/):
     - [plantilla-plan.md](./assets/plantilla-plan.md)
     - [plantilla-adr.md](./assets/plantilla-adr.md)
     - [plantilla-changelog.md](./assets/plantilla-changelog.md)

3. **Revisión Humana Obligatoria**:
   - Los planes técnicos en `docs/plans/` deben ser revisados y aprobados por un desarrollador humano **antes** de comenzar a escribir código de producción.

4. **Commits de Documentación**:
   - Los commits que agreguen o modifiquen documentación deben seguir Conventional Commits:  
     `docs(<alcance>): <descripción>` con la marca obligatoria `[AI Generated]`.

---

## 3. Checklist de Cierre

Antes de finalizar una tarea de documentación:
- [ ] El nuevo archivo sigue la convención de nombres establecida.
- [ ] Todos los enlaces relativos resuelven correctamente sin errores 404.
- [ ] Si se creó un documento clave, se referenció en [docs/README.md](../../../docs/README.md).
- [ ] No se incluyeron credenciales, tokens ni datos sensibles.
