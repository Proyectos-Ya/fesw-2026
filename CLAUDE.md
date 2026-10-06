# Chiripa — Instrucciones para Claude Code

Las reglas del proyecto viven en `AGENTS.md` (arquitectura, pruebas, documentación) y
`SKILL.md` (git y commits). Este archivo solo agrega lo específico de Claude Code.

@AGENTS.md

@SKILL.md

---

## Skills del proyecto

Viven en `.claude/skills/` y están versionadas.

| Skill | Cuándo |
|---|---|
| `documentacion` | Plan técnico de una HdU, ADR, changelog de sprint, documentar un endpoint o editar AGENTS/CLAUDE/GEMINI. |
| `fastapi` | Rutas, dependencias y modelos del backend. Ver "qué manda cuando choca" abajo. |

---

## Supabase — uso obligatorio de skills

Siempre que la tarea involucre **Supabase** (Database, Auth, Edge Functions, Realtime, Storage, Vectors, Cron, Queues, `supabase-js`, `@supabase/ssr`, CLI o MCP de Supabase), se debe invocar primero la skill `supabase` antes de escribir código o responder.

Además, antes de crear o modificar cualquier cosa que viva en Postgres (tablas, columnas, tipos, migraciones, esquema declarativo, políticas RLS, índices, triggers, funciones, pg_cron/pgmq, pgvector) o de diagnosticar problemas de base de datos (queries lentas, timeouts, locking, filas visibles para el tenant equivocado), se debe invocar la skill `supabase-postgres-best-practices`.

Reglas:
- Invocar la skill **antes** de editar archivos, no después.
- Aplica aunque el cambio parezca trivial (una sola columna, una sola query).
- Si el MCP de Supabase requiere autorización y no está disponible, avisar al humano en vez de improvisar.

---

## Railway — uso obligatorio de skill y MCP

Siempre que la pregunta o la tarea mencione **Railway** —o hable de lo que Railway
opera aquí sin nombrarlo: el despliegue del backend, el servicio en producción, sus
variables de entorno, dominios, logs de build o de runtime, métricas, reinicios,
rollbacks o el `Dockerfile` que se despliega— se debe invocar primero la skill
`use-railway` antes de responder o de tocar nada.

Reglas:
- Invocar la skill **antes** de responder, no después. Aplica también a preguntas
  que solo piden una explicación, no un cambio.
- Preferir el **MCP de Railway** al CLI para leer estado, logs, servicios y
  variables: no depende de que la carpeta esté vinculada ni de la sesión local del
  CLI, y deja registro de lo que se consultó.
- Si el MCP de Railway requiere autorización y no está disponible, decirlo y usar el
  CLI como respaldo, **avisando explícitamente de que se está usando el respaldo**.
  Nunca inventar el estado de un servicio ni el contenido de un log.
- **Nunca ejecutar `railway run`, `railway up`, `railway down`, `railway redeploy`,
  `railway restart`, `railway delete` ni ninguna escritura de variables sin pedir
  confirmación explícita al humano en el mismo turno.** Leer (`status`, `logs`,
  `variables`, `list`) no necesita confirmación.
- No activar hooks de auto-aprobación de comandos `railway`: aprueban cualquier línea
  que empiece por `railway` sin revisar el resto del comando.

Qué despliega Railway, `railway.toml` y su caducidad el 2026-12-01: ver
`AGENTS.md` §3. Lo que **no** está en el repositorio (root directory, variables de
entorno, dominios) vive solo en el dashboard: hay que consultarlo, no deducirlo.

---

## Skill oficial de FastAPI — qué manda cuando choca

En `.claude/skills/fastapi` está instalada la skill oficial del repositorio de
FastAPI. Es buena referencia para rutas, `Annotated`, dependencias, modelos Pydantic
y respuestas, y coincide con este proyecto en lo grande (SQLModel para los modelos,
Ruff para lint). Pero da por supuesto un proyecto FastAPI estándar, y este no lo es
del todo. Cuando choque, **manda el proyecto**:

- **Dependencias**: la skill propone `uv` y `uv add <paquete>`. Acá las dependencias
  viven en `monorepo/backend/requirements.txt` y `requirements-dev.txt`, y el
  `Dockerfile` instala desde el primero. `uv` es opcional: no todo el equipo lo usa,
  y quien lo usa lo hace solo para crear el entorno (`uv venv`); la alternativa es
  `python -m venv .venv`. No migrar a `pyproject.toml` ni ejecutar `uv add`.
- **Arranque**: la skill prefiere `fastapi dev` / `fastapi run` y un
  `[tool.fastapi] entrypoint`. Acá se arranca con `uvicorn app.main:app`, declarado
  en el `Dockerfile`, y `pyproject.toml` solo tiene configuración de Ruff.
- **Dependencias nuevas**: la skill recomienda Asyncer por encima de asyncio y AnyIO.
  No está instalado. Cualquier dependencia nueva que sugiera la skill se consulta
  con el humano antes de añadirla.

Lo que la skill sí aporta y conviene aprovechar: `Annotated` en los `Depends()` que
aún usan el estilo antiguo, y los metadatos de OpenAPI (medido el 2026-09-15: de 32
rutas, 1 tiene `summary=` y 27 tienen `response_model`). Cómo documentarlas: skill
`documentacion`.

---

## Notas locales

Lo que solo aplica a una máquina va en `CLAUDE.local.md`, que está en `.gitignore`.
