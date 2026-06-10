# ProyectosYA - Guía de Configuración y Reglas para Agentes de IA

Este documento sirve como referencia rápida para cualquier agente de IA (coding assistant) que colabore en el desarrollo de **ProyectosYA**. Aquí se consolidan las reglas fundamentales de arquitectura, herramientas y dependencias del repositorio.

---

## 1. Tecnologías y Estructura del Monorepo

El proyecto está organizado en un monorepo bajo el directorio `monorepo/`:

* **Frontend (`monorepo/frontend`)**: Next.js 16 (App Router), React 19, TypeScript, TailwindCSS v4.
  - **Gestor de dependencias obligatorio**: `pnpm` (Nunca usar `npm` o `yarn` por seguridad y consistencia).
  - **Regla estricta de tipado**: Está estrictamente prohibido utilizar el tipo `any` en TypeScript. Se deben definir tipos específicos, interfaces, genéricos o, en su defecto, `unknown`.
* **Backend (`monorepo/backend`)**: FastAPI, Python 3.12+.


---

## 2. Reglas de Arquitectura

### Frontend: Screaming Architecture
- La lógica de negocio está organizada por características en `src/features/<nombre-feature>/`.
- Cada feature agrupa sus propios componentes, hooks, servicios y pruebas (co-localizadas en `__tests__/`).
- El directorio `src/app/` contiene únicamente enrutamiento ligero; no debe tener lógica de negocio.

### Backend: Clean Architecture
- Dividido en tres capas dentro de `app/`:
  1. `domain/`: Núcleo de negocio. No depende de frameworks ni base de datos.
  2. `application/`: Casos de uso e interfaces abstractas de repositorios. No depende de infraestructura.
  3. `infrastructure/`: Implementaciones técnicas, base de datos y clientes externos.
- Dirección única de dependencia: Las capas externas conocen a las internas, nunca al revés.
- Inversión de dependencias para accesos a datos.

---

## 3. Pruebas y TDD (Test-Driven Development)

Es obligatorio adoptar el flujo **TDD (Red-Green-Refactor)** al escribir código de producción.

- **Comandos de Prueba en Backend (`monorepo/backend`)**:
  ```bash
  # Activar entorno virtual (.venv) e iniciar:
  pytest
  ```
- **Comandos de Prueba en Frontend (`monorepo/frontend`)**:
  ```bash
  # Pruebas unitarias/de componentes (Vitest):
  pnpm run test
  
  # Pruebas E2E (Playwright):
  pnpm run test:e2e
  ```

---

## 4. Flujo de Trabajo en Git y Commits

Verifica el archivo [SKILL.md](file:///d:/ProyectosYA/SKILL.md) para conocer las reglas estrictas sobre el ciclo de vida de Git, convenciones de commits hechas por agentes de IA, y la prohibición de hacer Push directamente.