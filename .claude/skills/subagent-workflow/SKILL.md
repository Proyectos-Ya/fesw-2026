---
name: subagent-workflow
description: Reglas de orquestación de subagentes para planificación e implementación de tareas. Úsala siempre que el usuario hable de planificar o diseñar un plan técnico (delegando a Claude Code CLI 'claude-code') o cuando se pase a la fase de implementación de código (preguntando obligatoriamente si usar 'claude-code-writer' o 'worker').
---

# Flujo de Orquestación de Subagentes: Planificación e Implementación

Esta skill estandariza el uso de subagentes delegados en Pi para las dos etapas fundamentales del ciclo de desarrollo: **Planificación** e **Implementación**.

---

## 1. Regla de Oro: Separación de Etapas y Elección de Agentes

| Etapa | Acción del Agente Principal | Subagente a Emplear | Modelo / Perfil |
|---|---|---|---|
| **Planificación** | Diseñar, analizar o revisar el plan técnico de una issue/HdU | `claude-code` (CLI) | Claude Code CLI (Opus:high / Plan mode) |
| **Implementación** | Escribir código, modificar archivos o ejecutar tareas de producción | **Preguntar obligatoriamente al usuario** mediante `ask_user_question` | `claude-code-writer` (Sonnet) o `worker` (Gemini 4 Argon) |

---

## 2. Fase de Planificación (Planning)

Cuando el usuario pida planificar, estructurar, diseñar o evaluar una historia de usuario o cambio técnico:
1. Usar el subagente de análisis y asesoría: **`claude-code`**.
2. `claude-code` opera en modo de solo lectura (`plan`), examinando el repositorio y recomendando la arquitectura, riesgos y diseño sin modificar archivos.
3. El resultado se consolida en el plan técnico del proyecto (en `docs/`).

---

## 3. Fase de Implementación (Coding)

### ⚠️ Regla Estricta: Confirmación Previa Obligatoria

**Está terminantemente prohibido empezar a escribir código o delegar la implementación sin antes preguntar al usuario qué subagente desea usar.**

Cada vez que se vaya a pasar a la fase de implementación de código (o al comenzar un bloque/tarea), debes llamar a la herramienta `ask_user_question` con la siguiente estructura:

* **Header**: `"Subagente motor"`
* **Pregunta**: `"¿Qué subagente deseas utilizar para implementar esta tarea?"`
* **Opciones**:
  1. **Label**: `"claude-code-writer (Recomendado)"`  
     **Description**: `"Usa Claude Code CLI con Sonnet para realizar las modificaciones de código en disco con TDD."`
  2. **Label**: `"worker"`  
     **Description**: `"Usa el subagente nativo worker con Gemini 4 Argon para escribir el código y tests."`

### Ejecución tras la respuesta
- Si el usuario selecciona **`claude-code-writer`**:
  Lanzar la tarea mediante:
  ```json
  {
    "agent": "claude-code-writer",
    "task": "Descripción clara de la tarea atómica (TDD Red-Green), archivos a tocar y criterios."
  }
  ```
- Si el usuario selecciona **`worker`**:
  Lanzar la tarea mediante:
  ```json
  {
    "agent": "worker",
    "task": "Descripción clara de la tarea atómica (TDD Red-Green), archivos a tocar y criterios."
  }
  ```
