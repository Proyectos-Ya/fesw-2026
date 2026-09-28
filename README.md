# Chiripa — Monorepo

**Chiripa** ayuda a MiPymes chilenas a ganar licitaciones de ChileCompra y Compra Ágil:
indexa las licitaciones de Mercado Público y las cruza con el perfil de cada empresa
mediante matching semántico.

> El repositorio y algunos identificadores técnicos conservan el nombre anterior del
> producto, **ProyectosYA**.

```
monorepo/frontend   Next.js 16 · React 19 · TypeScript · Tailwind v4   (Vercel)
monorepo/backend    FastAPI · Python 3.12 · SQLModel · Alembic         (Railway)
supabase/           configuración de Supabase (Postgres y Auth)
spikes/             investigaciones desechables
docs/               planes técnicos, decisiones, changelogs y guías
```

---

## Cómo empezar

- **Backend**: [monorepo/backend/README.md](./monorepo/backend/README.md): entorno
  virtual, Supabase local, Docker y cómo levantar la API.
- **Frontend**: [monorepo/frontend/README.md](./monorepo/frontend/README.md): `pnpm`
  y servidor de desarrollo.

## Mapa de la documentación

| Qué buscas | Dónde |
|---|---|
| Qué hay que construir y sus criterios de aceptación | GitHub Issues (fuente vigente) |
| Reglas de arquitectura, pruebas y documentación | [AGENTS.md](./AGENTS.md) |
| Reglas de git, commits y PRs | [SKILL.md](./SKILL.md) |
| Planes técnicos, decisiones (ADR), changelogs y guías | [docs/](./docs/README.md) |
| Cómo se documenta, paso a paso | [skill `documentacion`](./.claude/skills/documentacion/SKILL.md) |
| Referencia de la API | `/docs` (Swagger) con la API corriendo en local |
| Historias de usuario originales (histórico) | [user-story/](./user-story/user-stories-mvp.md) |

## Asistentes de IA

Todas las reglas están en [AGENTS.md](./AGENTS.md). Cada herramienta lo carga así:

- **Claude Code**: automático, vía [CLAUDE.md](./CLAUDE.md), que también trae las skills
  de `.claude/skills/`.
- **Gemini CLI**: automático, vía [monorepo/GEMINI.md](./monorepo/GEMINI.md), que importa
  `AGENTS.md` y `SKILL.md`.
- **Cursor, Copilot, Codex y otros**: leen `AGENTS.md` de la raíz. Si tu herramienta no
  lo hace, agrégalo a sus instrucciones de workspace.

Los agentes **no hacen `git push` sin autorización explícita**: dejan los commits locales y solicitan tu confirmación antes de subir cambios.
