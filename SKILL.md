# ProyectosYA - Reglas de Operación y Git para Agentes de IA

Este documento describe las instrucciones que todos los agentes de IA deben seguir estrictamente cuando interactúan con el repositorio de **ProyectosYA**, especialmente en lo relativo al ciclo de vida de desarrollo, commits y control de versiones.

---

## 1. Validación Previa al Commit (TDD Obligatorio)

Antes de realizar cualquier commit, el agente debe verificar que todo el código modificado pase las pruebas correspondientes y no cause regresiones.
* **Backend**: Ejecutar `pytest` y asegurar un estado exitoso (verde).
* **Frontend**: Ejecutar `pnpm run test` y verificar que las pruebas unitarias pasen. Si se alteraron flujos críticos de la interfaz, ejecutar `pnpm run test:e2e` para validar la integridad visual y funcional.

---

## 2. Reglas para los Commits (Git)

Al realizar un commit, los agentes de IA deben seguir las siguientes directrices:

### A. Frecuencia y Alcance
- Realizar commits atómicos y enfocados (un commit por cada tarea completada).
- Seguir la convención de **Conventional Commits** (`feat(scope): ...`, `fix(scope): ...`, etc.).

### B. Identificación del Autor de IA
- Cada commit realizado por un agente de IA **debe indicar explícitamente en su mensaje que fue generado por un agente**.
- **Formato del Mensaje**:
  ```text
  <tipo>(<alcance>): <descripción corta en minúsculas>

  [AI Generated] Commit realizado por el agente de IA <Nombre-Agente>.
  [Cuerpo opcional con más detalles si es necesario]
  ```

---

## 3. Calidad de Código y Tipado Estricto (Prohibición de `any`)

- Para mantener la robustez y seguridad del proyecto, **está estrictamente prohibido utilizar el tipo `any` en TypeScript**.
- Si el tipo de datos no se conoce de antemano o es dinámico, se debe utilizar `unknown`, genéricos (`<T>`) o crear la definición/interfaz de tipos adecuada.

---

## 4. Regla Crítica: PROHIBIDO HACER PUSH AL ORIGEN

Por motivos de seguridad, auditoría y control de calidad, **los agentes de IA tienen estrictamente prohibido ejecutar `git push` hacia cualquier repositorio remoto (origin o similares).**

### Procedimiento a seguir:
1. El agente debe realizar los commits necesarios de forma local.
2. Al finalizar su tarea, el agente debe informar al desarrollador humano que su trabajo local ha concluido.
3. El agente debe solicitar explícitamente al humano que realice el push de su rama e indicarle el comando sugerido para facilitarle la acción.

**Ejemplo de respuesta esperada del agente al finalizar:**
> "He completado las tareas y guardado los cambios en la rama local. Por favor, sube los cambios al repositorio remoto ejecutando el siguiente comando:
> ```bash
> git push origin mi-rama-de-trabajo
> ```"
