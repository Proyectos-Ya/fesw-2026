# Referencia: Cómo Redactar un Plan Técnico

Esta guía describe el procedimiento que un agente o desarrollador debe seguir para elaborar un plan técnico en `docs/plans/` antes de implementar una historia de usuario.

---

## Procedimiento Paso a Paso

1. **Inspeccionar la Issue**:
   - Lee el requerimiento y criterios de aceptación usando GitHub CLI:
     ```bash
     gh issue view <número-issue>
     ```
   - Identifica el alcance estricto de la tarea.

2. **Explorar el Código Existente**:
   - Localiza los archivos del frontend y backend que serán impactados.
   - Revisa contratos de API, schemas y entidades involucradas.

3. **Crear el Archivo del Plan**:
   - Copia la plantilla oficial [plantilla-plan.md](../assets/plantilla-plan.md) a:
     `docs/plans/<número-issue>-<slug>.md`
   - Ejemplo: `docs/plans/180-asistente-licitaciones-chat.md`.

4. **Desglosar la Implementación**:
   - **Contexto y Objetivo**: Resume brevemente el propósito de la HdU y enlaza con `Refs #<número-issue>`.
   - **Decisiones Técnicas**: Especifica si se introducen nuevas librerías, dependencias o endpoints.
   - **Checklist de Tareas**: Desglosa las tareas atómicas a realizar en Backend, Frontend y Pruebas (siguiendo TDD).

5. **Revisión y Aprobación**:
   - Presenta el plan al usuario para su revisión y validación **antes** de comenzar la codificación.

6. **Actualización al Concluir**:
   - Al finalizar la implementación y pasar todos los tests, actualiza el plan marcando los checkboxes completados e incluye el enlace al plan en el cuerpo del Pull Request.
