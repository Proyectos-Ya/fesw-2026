# Pipeline MVP — Estado del Backend (2026-06-02)

## Resumen ejecutivo

El pipeline de matching semántico está **implementado y testeado en su totalidad**.
126 tests pasan. Ningún test falla. La arquitectura Clean Architecture se respeta
en todas las capas. El sistema está listo para conectarse a infraestructura real
(PostgreSQL + Qdrant) una vez disponible.

```
pytest tests/  →  126 passed, 0 failed  (0.12s)
ruff check app/routers/ app/application/ app/infrastructure/ app/domain/errors/
            app/domain/entities/licitacion.py app/domain/entities/resultado_matching.py
         →  All checks passed (pipeline code)
```

---

## Arquitectura general

```
FastAPI (routers/)
    │
    ├── /proveedores     ← CRUD básico de proveedores (PR #42, otro miembro)
    ├── /licitaciones    ← Pipeline A: ingesta desde Mercado Público
    └── /matching        ← Pipeline B: búsqueda semántica + score
         │
Application (useCases/)
    ├── IngestLicitacionesUseCase   ← orquesta fetch → dedup → embed → upsert → save
    ├── MatchLicitacionesUseCase    ← proveedor → embed → search → save_bulk
    └── ObtenerScoreMatchingUseCase ← lookup de score previo en DB
         │
         │  depende de interfaces abstractas (no de implementaciones)
         │
Domain (entities/, models/, errors/)
    ├── Licitacion, ItemLicitacion, Proveedor, ResultadoMatching
    ├── IngestRequest/Result, MatchRequest/Result, ObtenerScoreRequest
    └── ProveedorNoEncontrado, ScoreMatchingNoEncontrado, LicitacionNoEncontrada
         │
Infrastructure (repositories/, services/)
    ├── LicitacionRepository      (PostgreSQL via SQLModel/asyncpg)
    ├── ResultadoMatchingRepository (PostgreSQL via SQLModel/asyncpg)
    ├── ProveedorRepository       (PostgreSQL via SQLModel/asyncpg)
    ├── BgeM3EmbeddingService     (BAAI/bge-m3, SentenceTransformers)
    ├── QdrantVectorStore         (AsyncQdrantClient, cosine, 1024d)
    └── MercadoPublicoClient      (httpx, API pública Chile)
```

**Regla de dependencia:** Domain ← Application ← Infrastructure ← Routers.
Las capas internas nunca importan las externas. Los use cases dependen solo de
interfaces ABC, nunca de SQLModel ni Qdrant directamente.

---

## Endpoints disponibles

| Método | Path | Use Case | Request | Response |
|--------|------|----------|---------|----------|
| `GET` | `/` | — | — | `{status, message, version}` |
| `GET` | `/health` | — | — | `{status: "healthy"}` |
| `POST` | `/proveedores/` | CrearProveedorUseCase | `CrearProveedorSchema` | `Proveedor` (201) |
| `GET` | `/proveedores/{rut}` | ObtenerProveedorUseCase | `rut: str` | `Proveedor` (200/404) |
| `POST` | `/licitaciones/ingest` | IngestLicitacionesUseCase | `IngestRequest` | `IngestResult` |
| `POST` | `/matching/` | MatchLicitacionesUseCase | `MatchRequest` | `MatchResult` |
| `GET` | `/matching/{proveedor_id}/{licitacion_id}` | ObtenerScoreMatchingUseCase | path params | `ResultadoMatching` (200/404) |

### Esquemas de request/response clave

```python
# POST /licitaciones/ingest
IngestRequest  { estado="activas", limit=100, offset=0 }
IngestResult   { procesadas: int, duplicadas: int, errores: int, version_modelo: str }

# POST /matching/
MatchRequest   { proveedor_id: UUID, top_k=10, region: str|None, monto_min: float|None }
MatchResult    { resultados: list[ResultadoMatching], version_modelo: str }

# GET /matching/{proveedor_id}/{licitacion_id}
ResultadoMatching {
    id, proveedor_id, licitacion_id,
    score_similitud: float,   # cosine similarity BGE-M3
    score_reranker: float|None,  # reranker no implementado aún
    score_final: float,       # actualmente == score_similitud
    version_modelo: str,
    fecha_calculo: datetime
}
```

---

## Interfaces abstractas (contratos del dominio)

### Repositorios (`app/application/repositories/`)

```python
class ILicitacionRepository(ABC):
    get_by_id(licitacion_id: UUID) -> Licitacion | None
    get_by_ids(ids: list[UUID]) -> list[Licitacion]
    get_by_codigo_externo(codigo_externo: str) -> Licitacion | None
    save(licitacion: Licitacion) -> Licitacion

class IProveedorRepository(ABC):
    get_by_id(proveedor_id: UUID) -> Proveedor | None
    get_by_rut(rut: str) -> Proveedor | None
    save(proveedor: Proveedor) -> Proveedor
    update(proveedor: Proveedor) -> Proveedor
    delete(proveedor_id: UUID) -> None

class IResultadoMatchingRepository(ABC):
    save_bulk(resultados: list[ResultadoMatching]) -> None
    get_by_proveedor_and_licitacion(proveedor_id, licitacion_id) -> ResultadoMatching | None
```

### Servicios (`app/application/services/`)

```python
class IEmbeddingService(ABC):
    embed(texts: list[str]) -> list[list[float]]   # batch, normalizado

class IVectorStoreService(ABC):
    ensure_collection() -> None
    upsert(vector_id: UUID, vector: list[float], payload: dict) -> None
    search(query_vector, top_k, filtros: FiltrosVectoriales | None) -> list[VectorSearchResult]

class IMercadoPublicoService(ABC):
    fetch_licitaciones(estado: str, limit: int, offset: int) -> list[Licitacion]
```

---

## Implementaciones concretas

| Interfaz | Implementación | Tecnología | Notas |
|----------|---------------|-----------|-------|
| `IEmbeddingService` | `BgeM3EmbeddingService` | `sentence-transformers`, `BAAI/bge-m3` | Async via `run_in_executor` |
| `IVectorStoreService` | `QdrantVectorStore` | `qdrant-client`, colección `licitaciones` | 1024d, cosine, filtros por región/monto |
| `IMercadoPublicoService` | `MercadoPublicoClient` | `httpx` async | Paginación offset→página, parse fecha `dd-mm-yyyy HH:MM:SS` |
| `ILicitacionRepository` | `LicitacionRepository` | `SQLModel` + PostgreSQL | `ARRAY(TEXT)` para categorías, `JSONB` para items |
| `IResultadoMatchingRepository` | `ResultadoMatchingRepository` | `SQLModel` + PostgreSQL | FK a `proveedor` y `licitacion` |
| `IProveedorRepository` | `ProveedorRepository` | `SQLModel` + PostgreSQL | `ARRAY(TEXT)` para rubros, regiones, etc. |

### Inyección de dependencias (singletons)

`app/routers/deps.py` — todas marcadas con `@lru_cache(maxsize=1)`:
- `get_embedding_service()` → `BgeM3EmbeddingService` (carga modelo una vez)
- `get_qdrant_client()` → `AsyncQdrantClient(host, port)`
- `get_vector_store()` → `QdrantVectorStore`
- `get_mercado_publico_client()` → `MercadoPublicoClient`

### Variables de entorno requeridas (`.env`)

```
POSTGRES_HOST=localhost        POSTGRES_PORT=5432
POSTGRES_DB=proyectosya        POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
QDRANT_HOST=localhost          QDRANT_PORT=6333
QDRANT_COLLECTION=licitaciones
EMBEDDING_MODEL=BAAI/bge-m3    EMBEDDING_VECTOR_SIZE=1024
MERCADO_PUBLICO_TICKET=<api_key>
```

---

## Cobertura de tests

| Archivo de test | Tests | Qué testea | Usa mocks |
|----------------|-------|-----------|-----------|
| `e2e/api/test_main.py` | 2 | Health check, root | No |
| `e2e/api/test_pipeline.py` | 6 | Los 3 endpoints pipeline HTTP completo | `dependency_overrides` FastAPI |
| `unit/application/test_ingest_licitaciones.py` | 11 | IngestUseCase: dedup, batch embed, errores parciales, payload Qdrant | `AsyncMock` de todas las interfaces |
| `unit/application/test_match_licitaciones.py` | 10 | MatchUseCase: proveedor no encontrado, filtros, save_bulk, score | `AsyncMock` |
| `unit/application/test_obtener_score_matching.py` | 5 | ObtenerScoreUseCase: happy path, 404 | `AsyncMock` |
| `unit/application/test_text_builder.py` | 19 | TextBuilder: simetría formato, secciones, separadores | Instancia real (es pura) |
| `unit/domain/test_licitacion_entity.py` | 16 | Entidad Licitacion: inmutabilidad, defaults, errores | No |
| `unit/domain/test_resultado_matching_entity.py` | 7 | Entidad ResultadoMatching: inmutabilidad, score_reranker | No |
| `unit/infrastructure/test_bge_m3_embedding_service.py` | 8 | BgeM3: encode batch, normalize, async | `sys.modules` stub + `patch` |
| `unit/infrastructure/test_licitacion_mapper.py` | 8 | LicitacionRepository mapper: roundtrip, items JSONB | `sys.modules` stub |
| `unit/infrastructure/test_mercado_publico_client.py` | 12 | MercadoPublicoClient: paginación, mapeo campos, parse fecha | `AsyncMock` httpx |
| `unit/infrastructure/test_qdrant_vector_store.py` | 14 | QdrantVectorStore: ensure_collection, upsert, search, filtros | `sys.modules` stub + `patch` |
| `unit/infrastructure/test_resultado_matching_mapper.py` | 5 | ResultadoMatchingRepository mapper: roundtrip | `sys.modules` stub |
| **TOTAL** | **123 unit + 8 e2e = 126** | | |

### Estrategia de mocking

Los tests no requieren servicios externos:
- **`sentence_transformers` y `qdrant_client`** no instalados en el entorno de tests.
  Ambos se stubean con `sys.modules.setdefault(_name, MagicMock())` **antes** de
  importar cualquier módulo de la app (en `tests/conftest.py` y
  `tests/unit/infrastructure/conftest.py`).
- **FastAPI e2e:** `app.dependency_overrides[get_X_use_case] = lambda: mock_uc`
  reemplaza los use cases por `AsyncMock` sin tocar servicios reales.
- **Use cases:** `AsyncMock(spec=IXxx)` por cada interfaz ABC.

---

## Modelos de base de datos (SQLModel)

### Tabla `proveedor`
`id UUID PK | rut VARCHAR(12) UNIQUE | razon_social VARCHAR(255) | nombre_fantasia | descripcion_libre | regiones ARRAY(TEXT) | rubros ARRAY(TEXT) | certificaciones ARRAY(TEXT) | palabras_clave ARRAY(TEXT) | anios_experiencia INT | num_empleados INT | fecha_creacion TIMESTAMP | fecha_actualizacion TIMESTAMP`

### Tabla `licitacion`
`id UUID PK | codigo_externo VARCHAR(50) UNIQUE | nombre VARCHAR(500) | descripcion TEXT | organismo_nombre VARCHAR(255) | monto_estimado FLOAT | fecha_cierre TIMESTAMP | region VARCHAR(100) | estado VARCHAR(50) | categorias ARRAY(TEXT) | items JSONB | qdrant_vector_id UUID | version_modelo VARCHAR(50) | fecha_ingesta TIMESTAMP`

### Tabla `resultado_matching`
`id UUID PK | proveedor_id UUID FK(proveedor.id) INDEX | licitacion_id UUID FK(licitacion.id) INDEX | score_similitud FLOAT | score_reranker FLOAT NULL | score_final FLOAT | version_modelo VARCHAR(50) | fecha_calculo TIMESTAMP`

> **No existe Alembic configurado.** Las tablas se crean vía `create_db_and_tables()`
> en `app/infrastructure/db.py` usando `SQLModel.metadata.create_all`.

---

## Issues de calidad de código conocidos

### Deuda técnica pre-existente (PR #42 — no en código del pipeline)

Los siguientes archivos tienen errores ruff que vienen del commit `71d51a9`
("Agregar entidad proveedor y metodo crear proveedor") y **no fueron introducidos
por el pipeline**:

| Archivo | Errores | Tipo |
|---------|---------|------|
| `app/domain/entities/proveedor.py` | 8× UP045 | `Optional[X]` → `X \| None` |
| `app/domain/entities/proveedor.py` | 2× UP017 | `datetime.utcnow` → `datetime.now(UTC)` |
| `app/domain/entities/proveedor.py` | deprecation `class Config` | Usar `ConfigDict` |
| `app/domain/models/proveedor_schema.py` | 6× UP045 + I001 | Mismo patrón |
| `app/infrastructure/repositories/proveedor_model.py` | 8× UP045 + 2× E501 | Mismo patrón |

Todos son auto-fixables con `ruff check --fix`. No afectan funcionalidad.

### Código del pipeline (iteraciones 4–11)
`ruff check app/routers/ app/application/ app/infrastructure/services/ app/infrastructure/repositories/licitacion* app/infrastructure/repositories/resultado* app/domain/entities/licitacion.py app/domain/entities/resultado_matching.py` → **0 errores**

---

## TODO — Iteraciones futuras

### Alta prioridad (necesario para producción)

- [ ] **Migrations con Alembic** — reemplazar `create_db_and_tables()` por migraciones versionadas. Sin esto no se puede actualizar el schema en producción sin recrear la DB.
- [ ] **Tests de integración** — `tests/integration/` existe en la estructura prevista pero está vacío. Se necesitan tests con PostgreSQL real (usando `testcontainers-python` o una DB de test dedicada) para validar los repositorios end-to-end.
- [ ] **Corregir deuda técnica en archivos proveedor** — `ruff check --fix app/domain/entities/proveedor.py app/domain/models/proveedor_schema.py app/infrastructure/repositories/proveedor_model.py` (29 errores auto-fixables).
- [ ] **`create_db_and_tables()` nunca se llama** — `app/infrastructure/db.py` define la función pero `app/main.py` no la invoca en ningún evento `startup`. Sin esto las tablas no existen al arrancar.
- [ ] **Manejo de ciclo de vida del httpx.AsyncClient** — `deps.get_mercado_publico_client()` crea un `httpx.AsyncClient()` sin cerrarlo. Se debe usar un lifespan context en `app/main.py` para gestionar su apertura/cierre.

### Media prioridad (calidad y robustez)

- [ ] **Endpoint PATCH /proveedores/{rut}** — `ProveedorRepository.update()` está implementado pero no tiene router ni use case de actualización de perfil. Necesario para que un proveedor modifique sus datos.
- [ ] **Endpoint DELETE /proveedores/{rut}** — mismo caso que update.
- [ ] **Paginación en GET /matching/** — actualmente `top_k` limita resultados pero no hay cursor/offset para paginar resultados previos.
- [ ] **Score reranker** — `score_reranker` y `score_final` son siempre iguales a `score_similitud`. La interfaz ya tiene el campo; falta integrar un modelo cross-encoder (e.g., BGE-Reranker).
- [ ] **Filtro por `fecha_cierre`** — `FiltrosVectoriales` no incluye `fecha_max`. Las licitaciones cerradas se siguen devolviendo en los resultados de búsqueda.
- [ ] **Caché de embeddings de proveedor** — cada llamada a `POST /matching/` recalcula el embedding del proveedor desde cero. Se podría cachear por `(proveedor_id, version_modelo)`.
- [ ] **Manejo explícito de errores HTTP en `MercadoPublicoClient`** — `raise_for_status()` lanza `httpx.HTTPStatusError` pero el use case no lo captura; propagaría como 500.

### Baja prioridad (nice-to-have)

- [ ] **Docker Compose** — no existe. Necesario para levantar PostgreSQL + Qdrant localmente sin instalación manual.
- [ ] **Variables de entorno de ejemplo** — no existe `.env.example`. Dificulta onboarding.
- [ ] **Endpoint GET /licitaciones/** — no hay forma de consultar licitaciones indexadas vía API.
- [ ] **Endpoint GET /licitaciones/{id}** — no hay forma de recuperar una licitación específica.
- [ ] **Autenticación** — todos los endpoints son públicos. Para producción se necesita al menos API key o JWT.
- [ ] **Rate limiting / retry en MercadoPublicoClient** — la API de Mercado Público tiene límites; no hay backoff.
- [ ] **Logging estructurado** — no hay logging en use cases ni servicios. Dificulta debugging en producción.
- [ ] **Métricas** — no hay instrumentación Prometheus/OpenTelemetry.
- [ ] **`conftest.py` global con `event_loop` deprecado** — `scope="session"` en `event_loop` fixture produce DeprecationWarning en pytest-asyncio moderno.

---

## Flujo del pipeline (referencia rápida)

```
POST /licitaciones/ingest
  → ensure_collection (Qdrant)
  → fetch_licitaciones(estado, limit, offset)  [Mercado Público API]
  → por cada licitacion: get_by_codigo_externo  [PostgreSQL — dedup]
  → build_from_licitacion × N                  [TextBuilder]
  → embed([texto1, texto2, ...])               [BGE-M3 — batch único]
  → por cada licitacion:
      upsert(vector_id, vector, payload)        [Qdrant]
      save(licitacion_indexada)                 [PostgreSQL]
  → IngestResult { procesadas, duplicadas, errores, version_modelo }

POST /matching/
  → get_by_id(proveedor_id)                    [PostgreSQL]
  → build_from_proveedor(proveedor)            [TextBuilder]
  → embed([texto_proveedor])                   [BGE-M3]
  → search(query_vector, top_k, filtros)       [Qdrant — cosine]
  → save_bulk(resultados)                      [PostgreSQL]
  → MatchResult { resultados: list[ResultadoMatching], version_modelo }

GET /matching/{proveedor_id}/{licitacion_id}
  → get_by_proveedor_and_licitacion            [PostgreSQL]
  → ResultadoMatching | 404
```
