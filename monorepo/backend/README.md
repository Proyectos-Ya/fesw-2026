# Chiripa Backend — FastAPI

Backend de **Chiripa**, construido con FastAPI, SQLModel, Alembic, PostgreSQL (Supabase) y Qdrant.

> **Identificadores técnicos**: El proyecto conserva internamente nombres históricos (`proyectosya_api`, `fesw-2026`, base de datos y contenedores). No renombrarlos sin acuerdo previo.

---

## Requisitos Previos

* **Python 3.12+**
* **Docker Desktop** (con al menos **4 GB de RAM asignados** para los modelos de embeddings)
* **Supabase CLI**

> **Windows**: Trabajar dentro de **WSL2**. Si usas Windows directo, agrega `WATCHFILES_FORCE_POLLING=1` al `.env`.

---

## Configuración Inicial

1. **Variables de entorno**:
   ```bash
   cp .env.example .env
   ```
   Genera el secreto de JWT y agrégalo al `.env`:
   ```bash
   python -c "import secrets; print(f'JWT_SECRET_KEY={secrets.token_urlsafe(48)}')" >> .env
   ```

2. **Entorno virtual local (`.venv`)**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate    # En Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   ```

3. **Clave de firma Supabase Auth**:
   ```bash
   echo '[]' > supabase/signing_keys.json
   supabase gen signing-key --algorithm ES256 --append
   ```

---

## Cómo Levantar el Proyecto

El backend se ejecuta siempre a través de **Docker Compose**:

```bash
# 1. Base de datos y Auth local (desde la raíz del repo)
supabase start

# 2. API y Qdrant (desde monorepo/)
docker compose up -d
```

* **API / Swagger**: [http://localhost:8000](http://localhost:8000) (documentación en `/docs`)
* **Supabase Studio**: [http://localhost:54323](http://localhost:54323)
* **Qdrant Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
* **Mailpit (correos locales)**: [http://localhost:54324](http://localhost:54324)

> **Nota**: El primer arranque descarga los modelos de embeddings (`bge-m3` y reranker, ~4.9 GB). Comprueba que la API esté lista con:
> `curl http://localhost:8000/health` (responderá `{"status":"healthy"}`).

---

## Base de Datos y Datos de Prueba

### Migraciones con Alembic
El esquema se gestiona **únicamente con Alembic** (ver [AGENTS.md](../../AGENTS.md)):
```bash
alembic upgrade head
alembic revision --autogenerate -m "descripcion"
```
* **Cabezas múltiples**: Antes de abrir un PR, ejecuta `alembic heads`. Debe devolver una sola línea. Si hay conflicto entre ramas, repunta `down_revision` a la cabeza de `develop` (ver [SKILL.md](../../SKILL.md) §1).

### Cargar Datos desde el Dump
Para sembrar licitaciones vigentes de prueba en PostgreSQL y Qdrant:
```bash
# Desde monorepo/backend/ con .venv activo:
python tests/matching_evaluation/load_postgres_robust.py
python tests/matching_evaluation/load_dataset.py
```
Las licitaciones del archivo `project-data/chiripa_tenders.xlsx` se cargan con fechas desplazadas hacia el futuro para que aparezcan siempre vigentes en la plataforma.

### Limpieza y Reseteo
Existen utilidades para vaciar licitaciones o resetear usuarios y perfiles de empresa sin borrar el catálogo. Consulta la guía detallada:
👉 [Guía de Scripts Utilitarios](../../docs/guides/scripts-utilitarios.md)

---

## Estructura del Proyecto (Clean Architecture)

```text
app/
├── domain/                  # Núcleo de negocio (entities, models, errors)
├── application/             # Casos de uso (use_cases, schemas, repositories, rules)
├── infrastructure/          # Detalles técnicos (routers, repositories, services, db)
└── shared/                  # Constantes y utilidades comunes
```
* Las dependencias van en una sola dirección: `infrastructure` → `application` → `domain`.
* Los casos de uso dependen de interfaces abstractas; las implementaciones de base de datos van en `infrastructure/repositories/`.

---

## Pruebas y Calidad

* **Linter y formato**: `ruff check . --fix && ruff format .`
* **Tests**: `pytest` (o `pytest -m "not integration and not network"` para pruebas rápidas unitarias).
* **Spikes**: Los experimentos en `spikes/` no requieren tests obligatorios (ver [AGENTS.md](../../AGENTS.md)).
* **OpenAPI**: Toda ruta de la API debe definir `summary`, `tags` y `response_model` para la documentación en `/docs` (ver [AGENTS.md](../../AGENTS.md)).

---

## Documentación Relacionada

* [AGENTS.md](../../AGENTS.md) — Reglas para agentes y decisiones de arquitectura.
* [SKILL.md](../../SKILL.md) — Convenciones de Git, commits y checklist pre-PR.
* [docs/README.md](../../docs/README.md) — Índice de ADRs, planes y guías técnicas.
* [docs/guides/scripts-utilitarios.md](../../docs/guides/scripts-utilitarios.md) — Scripts de mantenimiento y reseteo.
