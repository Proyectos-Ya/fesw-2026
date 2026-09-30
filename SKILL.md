# Chiripa - Reglas de Operación y Git para Agentes de IA

Este documento describe las instrucciones que todos los agentes de IA deben seguir estrictamente cuando interactúan con el repositorio de **Chiripa**, especialmente en lo relativo al ciclo de vida de desarrollo, commits y control de versiones.

---

## 1. Validación Previa al Commit y Pre-PR (TDD y Migraciones Obligatorias)

Antes de realizar cualquier commit o abrir un PR, el agente debe verificar que todo el código modificado pase las pruebas correspondientes, no cause regresiones y mantenga el esquema de base de datos íntegro.

* **Backend**: Ejecutar `pytest` y asegurar un estado exitoso (verde).
* **Frontend**: Ejecutar `pnpm run test` y verificar que las pruebas unitarias pasen. Si se alteraron flujos críticos de la interfaz, ejecutar `pnpm run test:e2e` para validar la integridad visual y funcional.
* **Base de Datos y Migraciones (Alembic)**:
  Si la tarea creó o modificó modelos de base de datos (`SQLModel`):
  1. Generar la migración: `alembic revision --autogenerate -m "descripcion corta"` (desde `monorepo/backend/`, con `.venv` activo).
  2. Revisar el archivo generado: verificar compatibilidad hacia atrás (columnas nuevas deben ser nullable o tener default; no borrar ni renombrar en el mismo despliegue).
  3. **Comprobar cabezas con `alembic heads` (Obligatorio)**: Debe devolver **exactamente una sola línea**.
  4. **Resolución de múltiples cabezas**: Si dos ramas paralelas generaron migraciones desde el mismo punto, el grafo de Alembic se bifurca y el despliegue en Railway aborta. Cómo resolverlo:
     - **Migración local aún no desplegada ni mergeada** (lo habitual): Repuntar el `down_revision` de tu migración para que apunte a la cabeza actual de `develop` (mantiene el grafo lineal).
     - **Migración ya aplicada o mergeada en entorno compartido**: Ejecutar `alembic merge heads -m "merge heads"`.

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

## 4. Regla para Push al Remoto: Prohibido hacer push sin confirmación explícita

Por motivos de seguridad, auditoría y control de calidad, **los agentes de IA tienen prohibido ejecutar `git push` de manera autónoma sin preguntar previamente y contar con una confirmación explícita del usuario.**

### Procedimiento a seguir:
1. El agente debe realizar los commits necesarios de forma local.
2. Si la tarea requiere subir los cambios, el agente debe informar al desarrollador humano que el trabajo local ha concluido y **preguntar si desea que se realice el push**, indicando la rama de destino.
3. **Solo si el usuario otorga una confirmación explícita en ese momento**, el agente puede proceder a ejecutar el `git push`. En su defecto, también puede facilitarle el comando sugerido para que el usuario lo ejecute manualmente si lo prefiere.

**Ejemplo de flujo esperado:**
> "He completado las tareas y guardado los cambios en la rama local `mi-rama-de-trabajo`. ¿Deseas que suba los cambios al repositorio remoto (`git push origin mi-rama-de-trabajo`) o prefieres hacerlo tú mismo?"

---

## 5. Trazabilidad con GitHub Issues

La especificación de cada tarea vive en una issue del repositorio, no en el código.

- **Antes de implementar**, leer la issue correspondiente con `gh issue view <n>`.
  Los criterios de aceptación están en su cuerpo y definen qué significa "terminado".
  No inferir el alcance leyendo el código.
- Las ramas llevan el número de la issue al inicio (`155-spike-1-...`).
- La descomposición de una historia usa **sub-issues nativas** de GitHub
  (`gh issue create --parent <n>`), no campos de texto en el cuerpo.
- Todo PR referencia su issue con `Closes #NNN`, o `Refs #NNN` si no la cierra
  del todo. La plantilla de PR lo pide junto con la evidencia de cómo se probó
  cada criterio.
- **Si el PR modifica modelos o esquema de base de datos**: Es obligatorio verificar
  y dejar constancia de que `alembic heads` devuelve una sola línea (grafo lineal).
