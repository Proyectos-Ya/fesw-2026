# Chiripa Backend — FastAPI

Backend de **Chiripa**, construido con FastAPI, SQLModel, Alembic, PostgreSQL (Supabase) y Qdrant. Proporciona los servicios de ingesta, indexación vectorial, matching semántico híbrido, alertas por correo y asistencia interactiva mediante IA.

> **Nota sobre identificadores técnicos**: El repositorio y algunos identificadores internos (nombres de servicios en Docker como `proyectosya_api`, base de datos y correos) conservan el nombre histórico del producto (`ProyectosYA` / `fesw-2026`). No renombrarlos sin acuerdo previo.

---

## 1. Requisitos Previos

* **Python 3.12+**
* **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**: Instalado y en ejecución, con al menos **4 GB de memoria RAM asignados** (el modelo de embeddings `bge-m3` y el reranker consumen ~3 GB al arrancar; con menos memoria, Docker puede finalizar el contenedor silenciosamente).
* **[Supabase CLI](https://supabase.com/docs/guides/local-development)**: Provee la base de datos PostgreSQL y el servicio de autenticación (GoTrue) en local.

> **Usuarios de Windows**: Se recomienda clonar el repositorio dentro de **WSL2** para que los eventos de archivos del hot reload funcionen correctamente y el rendimiento de I/O sea óptimo. Si trabajas directamente sobre Windows, define `WATCHFILES_FORCE_POLLING=1` en tu archivo `.env`.

---

## 2. Configuración Inicial

Estos pasos se ejecutan una sola vez al configurar el entorno:

### A. Variables de Entorno (`.env`)
Desde la carpeta `monorepo/`:
```bash
cp .env.example .env
```
Completa las variables requeridas en `.env`:
* `DATABASE_URL`: Conexión a la base de datos (con Supabase local: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`).
* `JWT_SECRET_KEY`: Secreto para validar sesiones. Genera uno con:
  ```bash
  python -c "import secrets; print(f'JWT_SECRET_KEY={secrets.token_urlsafe(48)}')" >> .env
  ```
* `GEMINI_API_KEY`: Clave para los servicios de análisis asistido.
* `MERCADO_PUBLICO_API_KEY`: Ticket de la API de Mercado Público (para ingestas o consultas externas).

### B. Entorno Virtual Local (`.venv`)
Aunque la aplicación corra dentro de Docker, el entorno virtual local es imprescindible para ejecutar los tests (`pytest`), linters (`ruff`), chequeo de tipos y soporte del editor:
```bash
# Desde monorepo/backend/
python -m venv .venv

# Activar en macOS/Linux:
source .venv/bin/activate

# Activar en Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Instalar dependencias de desarrollo y producción:
pip install -r requirements-dev.txt
```

### C. Autenticación Local con Supabase
Supabase Auth emite los JWT firmados con algoritmo asimétrico (ES256). Antes del primer arranque de Supabase, inicializa la llave de firma:
```bash
# Desde la raíz del repositorio:
echo '[]' > supabase/signing_keys.json
supabase gen signing-key --algorithm ES256 --append
```

---

## 3. Cómo Levantar el Proyecto

### Flujo Principal: Con Docker Compose (Recomendado)

```bash
# 1. Desde la raíz del repositorio: levantar base de datos y auth local
supabase start

# 2. Desde monorepo/: levantar API y Qdrant
docker compose up -d

# 3. (Opcional) Desde monorepo/frontend/: levantar el cliente web
pnpm dev
```

#### Servicios Disponibles

| Servicio | URL | Descripción |
|---|---|---|
| **API Backend** | [http://localhost:8000](http://localhost:8000) | Documentación interactiva Swagger en `/docs` |
| **Supabase Studio** | [http://localhost:54323](http://localhost:54323) | Panel de administración de Postgres y Auth |
| **PostgreSQL** | `127.0.0.1:54322` | Usuario: `postgres`, Contraseña: `postgres` |
| **Qdrant Dashboard** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Consola visual de colecciones vectoriales |
| **Mailpit** | [http://localhost:54324](http://localhost:54324) | Bandeja de entrada local para correos de prueba |

> **Primer arranque**: La primera vez que se levanta el backend tardará varios minutos en descargar los modelos de embeddings y reranking (`bge-m3` ~4.3 GB y reranker ~588 MB). Estos se guardan en un volumen persistente de Docker, por lo que los arranques posteriores tomarán ~20 segundos.
>
> Puedes verificar cuándo la API está lista con:
> ```bash
> curl http://localhost:8000/health
> # Responderá {"status":"healthy"} cuando los modelos estén cargados
> ```

#### Comandos Útiles de Docker
```bash
docker compose logs -f api    # Ver logs en tiempo real
docker compose ps             # Estado de los contenedores
docker compose restart api    # Reiniciar la API (necesario al cambiar .env)
docker compose down           # Detener contenedores (sin borrar volúmenes)
supabase stop                 # Detener Supabase
```

---

### Flujo Alternativo: Ejecución Local Directa (`uvicorn`)

Si prefieres ejecutar el proceso de FastAPI directamente en tu máquina:
```bash
# Asegúrate de que Supabase y Qdrant estén activos:
supabase start
docker compose up -d qdrant

# Con el entorno virtual activo (.venv) y desde monorepo/backend/:
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

---

## 4. Cómo Cargar y Gestionar la Base de Datos

### A. Migraciones de Esquema (Alembic)
El esquema de la base de datos se gestiona **exclusivamente con Alembic**. Está prohibido usar `SQLModel.metadata.create_all` (ver [ADR 0001](../../docs/decisions/0001-esquema-solo-con-alembic.md)).

```bash
# Aplicar todas las migraciones pendientes:
alembic upgrade head

# Crear una nueva migración tras modificar modelos:
alembic revision --autogenerate -m "descripcion corta"
```

#### Prevención de Cabezas Múltiples (`multiple heads`)
Cuando dos ramas concurrentes generan migraciones desde el mismo punto base, el grafo se bifurca y el comando `alembic upgrade head` abortará el despliegue en Railway:
1. **Comprueba siempre con `alembic heads`** antes de abrir un PR: debe devolver **una sola línea**.
2. **Si hay más de una cabeza**:
   * Si tu migración solo existe localmente en tu rama: edita el campo `down_revision` en tu archivo de migración para que apunte al último head de `develop`.
   * Si la migración ya fue aplicada en un entorno compartido: ejecuta `alembic merge heads -m "merge heads"`.

---

### B. Carga de Datos desde el Dump del Repositorio

Para contar con licitaciones de prueba en desarrollo sin depender de la API de Mercado Público ni consumir cuotas, se utiliza el dump oficial versionado en `project-data/chiripa_tenders.xlsx`.

Con la infraestructura arriba (`supabase start` y `docker compose up -d qdrant`) y desde `monorepo/backend/`:

```bash
# 1. Cargar las licitaciones en PostgreSQL
python tests/matching_evaluation/load_postgres_robust.py

# 2. Generar embeddings e indexar los vectores en Qdrant (~1-2 minutos)
python tests/matching_evaluation/load_dataset.py
```

> **Desplazamiento automático de fechas**: `load_postgres_robust.py` desplaza automáticamente hacia el futuro las fechas de las licitaciones vencidas del dump. Esto garantiza que aparezcan siempre vigentes en la aplicación y que el dashboard de matching no se muestre vacío.

Una vez cargadas las licitaciones:
1. Regístrate como usuario en la aplicación web (`http://localhost:3000/register`).
2. Confirma el enlace de verificación en Mailpit (`http://localhost:54324`).
3. Completa el asistente de perfil de empresa para que el sistema calcule el matching semántico.

---

### C. Mantenimiento y Reseteo de Datos

Existen procedimientos y scripts específicos según lo que necesites reiniciar:

* **Eliminar perfiles de empresas y cuentas de usuario**: Se utiliza el script `reset_cuentas.py`, el cual borra en cascada los usuarios, empresas y datos asociados en PostgreSQL y limpia los vectores en Qdrant, **sin tocar el catálogo de licitaciones**.
* **Vaciar y recargar el catálogo de licitaciones**: Se realiza truncando las tablas de licitaciones en PostgreSQL y borrando la colección `tenders` de Qdrant, para luego recargar con el dump.
* **Verificar consistencia vectorial**: Se utiliza `check_tender_vector_orphans.py` para detectar diferencias entre Postgres y Qdrant.

> Consulta la guía completa con ejemplos y comandos paso a paso en:
> 👉 [`docs/guides/scripts-utilitarios.md`](../../docs/guides/scripts-utilitarios.md)

---

## 5. Estructura del Proyecto (Clean Architecture)

El backend implementa **Clean Architecture**, asegurando que la lógica de negocio permanezca desacoplada de frameworks y bases de datos:

```text
monorepo/backend/
├── alembic/                         # Historial de migraciones de esquema
├── app/
│   ├── main.py                      # Punto de entrada FastAPI, lifespan y guardias
│   ├── config.py                    # Configuración centralizada vía pydantic-settings
│   ├── domain/                      # CAPA DE DOMINIO (Núcleo de negocio, sin dependencias externas)
│   │   ├── entities/                # Entidades con identidad propia y lógica interna
│   │   ├── models/                  # Modelos de dominio y tipos de datos
│   │   └── errors/                  # Excepciones de negocio personalizadas
│   ├── application/                 # CAPA DE APLICACIÓN (Casos de uso y orquestación)
│   │   ├── use_cases/               # Casos de uso (matching, tender, auth, supplier, etc.)
│   │   ├── schemas/                 # Esquemas Pydantic de entrada/salida (DTOs)
│   │   ├── repositories/            # Interfaces abstractas de repositorios
│   │   └── rules/                   # Validaciones de aplicación
│   ├── infrastructure/              # CAPA DE INFRAESTRUCTURA (Detalles técnicos y adaptadores)
│   │   ├── routers/                 # Endpoints HTTP FastAPI
│   │   ├── repositories/            # Implementaciones SQLModel/Postgres y Qdrant
│   │   └── services/                # Clientes externos (Supabase, Mercado Público, Gemini)
│   └── shared/                      # Constantes y utilidades compartidas
├── scripts/                         # Scripts de mantenimiento y simulación
└── tests/                           # Suite de pruebas Pytest (unitarias, integración, e2e)
```

### Reglas de Dependencia
* **Dirección única**: Las capas externas dependen de las internas (`infrastructure` → `application` → `domain`). El dominio nunca importa de la infraestructura.
* **Inversión de dependencias**: Los casos de uso interactúan con interfaces abstractas (`app/application/repositories/`); las implementaciones concretas residen en `app/infrastructure/repositories/`.

---

## 6. Calidad de Código, Pruebas y Buenas Prácticas

### Linters y Formato (Ruff)
```bash
ruff check .          # Revisar errores y buenas prácticas
ruff check . --fix    # Corregir incidencias automáticas
ruff format .         # Formatear código
```

### Pruebas Automatizadas (Pytest)
```bash
# Ejecutar todas las pruebas locales (omitiendo las que requieren DB en vivo)
pytest -m "not integration and not network"

# Ejecutar suite completa con base de datos de integración corriendo
pytest

# Ejecutar una prueba específica
pytest tests/unit/infrastructure/test_openapi_metadata.py
```

> **Excepción de pruebas en spikes**: Los spikes (`spikes/`) son investigaciones desechables y **no requieren tests obligatorios**. Si un desarrollo de un spike pasa a producción en `monorepo/`, se reescribe adoptando TDD (ver [AGENTS.md](../../AGENTS.md)).

### Metadatos OpenAPI y Documentación de la API
* La documentación interactiva (Swagger UI) está disponible en `/docs` cuando `ENABLE_API_DOCS=true` o en entorno de desarrollo (`IS_DEV=true`).
* **Guardia de CI**: Toda ruta expuesta en FastAPI debe incluir obligatoriamente `summary`, `tags` y `response_model`. El test `tests/unit/infrastructure/test_openapi_metadata.py` valida esto automáticamente en cada PR.

---

## 7. Mapa de Documentación

* [AGENTS.md](../../AGENTS.md): Reglas de arquitectura, testing y directrices generales del proyecto.
* [SKILL.md](../../SKILL.md): Reglas de Git, validación pre-commit/pre-PR y convenciones de commits.
* [docs/README.md](../../docs/README.md): Índice maestro de planes técnicos, decisiones de arquitectura (ADRs) y guías.
* [docs/decisions/](../../docs/decisions/): Decisiones de Arquitectura ([ADR 0001](../../docs/decisions/0001-esquema-solo-con-alembic.md) sobre Alembic, [ADR 0003](../../docs/decisions/0003-migraciones-en-predeploy-de-railway.md) sobre Railway).
* [docs/guides/scripts-utilitarios.md](../../docs/guides/scripts-utilitarios.md): Catálogo detallado de scripts de mantenimiento y simulación.
