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

## 3. Base de Datos y Migraciones

El backend usa **SQLModel** para los modelos y **Alembic** para el esquema. Son
responsabilidades separadas y no intercambiables.

### Reglas

- **El esquema se gestiona solo con Alembic.** Está prohibido usar
  `SQLModel.metadata.create_all` para crear o actualizar tablas. `create_all`
  agrega las tablas que faltan pero **no altera las existentes**, así que una
  columna o restricción nueva queda fuera en silencio. Ver el comentario en
  `app/main.py`, donde se explica por qué se quitó.

- **Las migraciones deben ser compatibles hacia atrás.** Corren en el
  `preDeployCommand` de `railway.toml`, o sea *antes* de levantar la versión
  nueva: durante ese momento la versión vieja convive con el esquema nuevo.
  En la práctica: agregar columnas nullable, y no renombrar ni borrar en el
  mismo despliegue que deja de usarlas.

- **Cabezas múltiples.** Cuando dos ramas crean migraciones desde el mismo
  punto, el grafo de Alembic queda con dos finales y `alembic upgrade head`
  **aborta sin aplicar nada**: el despliegue se cae y el código mergeado no
  llega a producción. Cómo se arregla depende de si tu migración ya se aplicó
  en algún entorno:

  - **Todavía no se aplicó en ninguna parte** (lo habitual: sigue solo en tu
    rama): repuntar el `down_revision` de tu migración a la cabeza actual.
    Es seguro porque nadie la ha aplicado, y deja el grafo lineal.
  - **Ya se aplicó en algún entorno** (está en `main` y se desplegó, o alguien
    la corrió contra una base compartida): `alembic merge heads`. Editar el
    `down_revision` de una migración que otros ya aplicaron rompe su historial.

  Antes de abrir el PR, comprobar con `alembic heads`: si devuelve más de una
  línea, resolverlo antes de mergear. Ha ocurrido dos veces (30-ago-2026 y
  2-sep-2026), las dos con la misma forma: dos ramas largas desde el mismo
  ancestro, mergeadas en secuencia.

### Crear una migración

```bash
# desde monorepo/backend, con el entorno virtual activo
alembic revision --autogenerate -m "descripcion corta"
alembic upgrade head
```

Revisar siempre el archivo generado antes de commitear: el autogenerado no
detecta renombres ni cambios de tipo con datos.

---

## 4. Pruebas y TDD (Test-Driven Development)

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

## 5. Flujo de Trabajo en Git y Commits

Verifica el archivo [SKILL.md](./SKILL.md) para conocer las reglas estrictas sobre el ciclo de vida de Git, convenciones de commits hechas por agentes de IA, y la prohibición de hacer Push directamente.
