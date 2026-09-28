# Chiripa — Contexto y reglas para agentes de IA

Fuente única de reglas para cualquier agente (Claude Code, Gemini, Cursor, Copilot) y
para quien desarrolla. `CLAUDE.md` y `monorepo/GEMINI.md` importan este archivo; las
reglas de git y commits están en [SKILL.md](./SKILL.md).

> El repositorio y algunos identificadores técnicos (base de datos, correos, CI)
> conservan el nombre anterior del producto, ProyectosYA. No renombrarlos sin acordarlo.

---

## 1. Resumen ejecutivo

- **Propósito**: Chiripa ayuda a MiPymes chilenas a ganar licitaciones de ChileCompra y
  Compra Ágil. Bajada de marca: *Licitaciones inteligentes*. Indexa las licitaciones de
  Mercado Público y las cruza con el perfil de cada empresa mediante matching semántico.
- **Alcance**: módulos en `monorepo/frontend/src/features/`: `auth`, `company-profile`,
  `search`, `matches`, `notifications`, `saved-tenders`, `tender-assistant`.
- **Dónde está el QUÉ**: la especificación de cada tarea vive en GitHub Issues (ver
  `SKILL.md` §5). Este repo guarda el CÓMO.

---

## 2. Reglas directivas

### Stack y estilo

- **Frontend (`monorepo/frontend`)**: Next.js 16 (App Router), React 19, TypeScript,
  TailwindCSS v4.
  - Gestor de dependencias obligatorio: **`pnpm`**. Nunca `npm` ni `yarn`, por
    seguridad y consistencia del árbol de dependencias.
  - **Prohibido el tipo `any`**. Usar tipos específicos, interfaces, genéricos o
    `unknown`.
  - Antes de crear un componente, revisa `src/features/shared/components/`. La
    documentación de diseño y marca del frontend está pendiente.
- **Backend (`monorepo/backend`)**: FastAPI, Python 3.12+, SQLModel y Alembic.

### Pruebas y TDD

Es obligatorio el flujo **TDD (Red-Green-Refactor)** al escribir código de producción.

- Backend (`monorepo/backend`, con `.venv` activo): `pytest`
- Frontend (`monorepo/frontend`): `pnpm run test` (Vitest) y `pnpm run test:e2e`
  (Playwright) si se tocan flujos críticos.

#### Excepción: los spikes no necesitan tests

TDD es obligatorio para el código de producción (`monorepo/`). **El código de un
spike no necesita tests**: no es obligatorio escribirlos, ni en `spikes/` ni en
`monorepo/backend/tests/` ni en `monorepo/frontend/`. No es una prohibición: si a
quien hace el spike le sirven —por ejemplo, para no gastar cuota real de una API
mientras ajusta un arnés—, puede escribirlos.

- Un spike es una investigación desechable (pruebas de concepto, arneses de
  medición, benchmarks, notebooks). Su resultado es el informe, no el código, así
  que exigirle tests es trabajo que no protege nada del producto.
- Un PR de spike **no se bloquea** por no tener tests.
- Si un test de spike se vuelve lento o inestable en CI, se borra sin discutirlo:
  vale menos que el ruido que mete.
- Si algo de un spike pasa a producción, se reescribe dentro de `monorepo/`
  siguiendo TDD, y recién ahí los tests son obligatorios.

### Estrategia de documentación

Aquí se dice **cuándo** documentar. El **cómo**, paso a paso y con plantillas, está en
la skill [`documentacion`](./.claude/skills/documentacion/SKILL.md). Cualquier agente
que no cargue skills debe leer ese archivo antes de documentar.

| Situación | Documento | Dónde |
|---|---|---|
| Empezar una HdU o un cambio no trivial | Plan técnico, revisado por un humano **antes** de codificar | `docs/plans/<issue>-<slug>.md` |
| Tomar o cambiar una decisión de arquitectura | ADR | `docs/decisions/NNNN-<slug>.md` |
| Crear o modificar una ruta de la API | `summary`, `response_model` y `tags` en la ruta (Swagger en `/docs`) | el router |
| Cerrar un sprint | Changelog con sección para usuarios y sección técnica | `docs/changelogs/sprint-N.md` |
| Cambiar reglas para agentes | Editar este archivo; no duplicar en `CLAUDE.md` ni `GEMINI.md` | `AGENTS.md` |

Las issues no se copian en `docs/`: un plan enlaza su issue con `Refs #NNN` y no repite
los criterios de aceptación.

### Git y commits

Ver [SKILL.md](./SKILL.md): Conventional Commits, marca `[AI Generated]`, trazabilidad
con issues y **prohibición de `git push` sin confirmación explícita del usuario**.

---

## 3. Arquitectura y restricciones

### Frontend: Screaming Architecture

- La lógica de negocio se organiza por característica en `src/features/<feature>/`.
- Cada feature agrupa sus componentes, hooks, servicios y pruebas (co-localizadas en
  `__tests__/`).
- `src/app/` contiene solo enrutamiento ligero, sin lógica de negocio.
- Un componente sube a `src/features/shared/` solo cuando lo usan dos features.

### Backend: Clean Architecture

- Tres capas dentro de `app/`:
  1. `domain/`: núcleo de negocio. No depende de frameworks ni de base de datos.
  2. `application/`: casos de uso e interfaces abstractas de repositorios. No depende
     de infraestructura.
  3. `infrastructure/`: implementaciones técnicas, base de datos, routers y clientes
     externos.
- Dirección única de dependencia: las capas externas conocen a las internas, nunca al
  revés. Inversión de dependencias para el acceso a datos.

### Base de datos y migraciones

El backend usa **SQLModel** para los modelos y **Alembic** para el esquema. Son
responsabilidades separadas y no intercambiables.

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

- **Cabezas múltiples.** Ocurre cuando dos ramas paralelas crean migraciones
  desde la misma revisión base (`down_revision`). Al integrarse ambas ramas, el
  grafo de Alembic queda con dos finales concurrentes y `alembic upgrade head`
  **aborta con error sin aplicar nada**: el despliegue en Railway se cae en el
  `preDeployCommand` y el código mergeado no llega a producción.

  **Regla estricta antes de abrir PR (ver [SKILL.md](./SKILL.md) §1)**:
  Ejecutar `python -m scripts.migraciones`, que además de detectar el conflicto
  dice cuál de los dos caminos de abajo corresponde y con `--arreglar` aplica el
  primero. El CI corre ese mismo comando. Si prefieres verlo crudo, `alembic
  heads` debe devolver **una sola línea**. Si devuelve más de una cabeza,
  resolverlo antes de mergear:
  - **Todavía no se aplicó en ninguna parte** (lo habitual: sigue solo en tu
    rama local): repuntar el `down_revision` de tu archivo de migración para que
    apunte a la cabeza actual de `develop`. Es seguro porque nadie la ha
    aplicado y conserva el historial lineal.
  - **Ya se aplicó en algún entorno** (está en `main`/`develop` y se desplegó, o
    alguien la corrió contra una base compartida): `alembic merge heads -m "merge heads"`.
    Editar el `down_revision` de una migración que otros ya aplicaron rompe su historial.

  Este conflicto ha ocurrido repetidamente al mergear ramas largas en secuencia:
  `git log --grep=encadenar` muestra cinco re-encadenados, dos de ellos sobre la
  misma migración porque la cabeza se movió mientras el PR seguía abierto. El job
  de CI lo bloquea antes del merge, pero la causa de fondo es la rama larga: si
  el cambio de esquema es compatible hacia atrás, conviene mergearlo en un PR
  propio y temprano, en vez de arrastrarlo dentro de la feature.

Crear una migración (desde `monorepo/backend`, con el entorno virtual activo):

```bash
alembic revision --autogenerate -m "descripcion corta"
alembic upgrade head
```

Revisar siempre el archivo generado antes de commitear: el autogenerado no
detecta renombres ni cambios de tipo con datos. Para el manual operativo completo
y recetas de resolución de incidentes, consultar la
[Guía Operativa de Migraciones con Alembic](./docs/guides/alembic-migraciones.md).

### Integraciones

- **Supabase**: provee Postgres y Auth, en local (Supabase CLI) y en producción.
- **Qdrant**: base vectorial para el matching semántico. El modelo de embeddings se
  carga al arrancar la API (~3 GB de memoria; ver `monorepo/backend/README.md`).
- **Railway**: despliega el backend desde `monorepo/backend/Dockerfile`. La
  configuración versionada está en `monorepo/backend/railway.toml`
  (`preDeployCommand = ["alembic upgrade head"]`), leída desde el root directory
  `monorepo/backend`. **Caduca el 2026-12-01**: Config as Code está deprecado y ese día
  las migraciones dejan de correr en cada despliegue sin que nada falle (despliegue
  verde contra un esquema viejo). El reemplazo es Infrastructure as Code
  (`.railway/railway.ts`). Mientras tanto, un servicio nuevo se configura por el panel,
  no por archivo.
- **Vercel**: despliega el frontend.
