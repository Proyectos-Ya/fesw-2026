# Scripts Utilitarios y Mantenimiento de Datos

Esta guía detalla los scripts existentes en `monorepo/backend/scripts/` y `monorepo/backend/tests/matching_evaluation/`, sus propósitos, parámetros y cómo ejecutarlos de forma segura.

---

## 1. Mantenimiento, Reseteo y Limpieza de Datos

### A. Eliminar Cuentas de Usuario y Perfiles de Empresa: `reset_cuentas.py`

* **Ruta**: `monorepo/backend/scripts/reset_cuentas.py`
* **Propósito**: Borrar usuarios (`users`), perfiles de empresa/proveedores (`supplier`) y todas sus dependencias en cascada (historiales de chat, análisis de IA, resultados de matching, licitaciones guardadas y preferencias de alertas).
* **Comportamiento seguro**:
  * **Conserva las licitaciones**: Las tablas de licitaciones (`tender`, `tender_item`), instituciones compradoras (`buyer_institution`), regiones y comunas **no se tocan**.
  * **Conserva los anexos compartidos** (`attachment_file` sin empresa); sus extracciones se recalculan.
  * **Limpia Qdrant**: Elimina los puntos correspondientes a los proveedores borrados en la colección `suppliers`, previniendo vectores huérfanos.
* **Uso**:
  ```bash
  # 1. Modo simulación (Dry-Run): muestra lo que va a borrar sin modificar nada
  docker compose exec api python -m scripts.reset_cuentas

  # 2. Modo ejecución real: realiza el truncado y borrado de vectores
  docker compose exec api python -m scripts.reset_cuentas --ejecutar
  ```
  *(Con el entorno virtual `.venv` activado en tu máquina local: `python -m scripts.reset_cuentas [--ejecutar]`)*

---

### B. Vaciar y Recargar el Catálogo de Licitaciones

Cuando se desea reiniciar por completo el entorno local con el dump del repositorio:

```bash
# Con el entorno virtual del backend activo (.venv):
python -m scripts.dump cargar
```

**Borra todo el entorno local sin preguntar**: el catálogo, las cuentas (también
los logins de Supabase Auth), las empresas y lo que cuelga de ellas (guardadas,
kanban, chats, cotizaciones, alertas, vectores de `suppliers`). Después de
cargar hay que registrarse de nuevo en `/register`; si el navegador tenía una
sesión abierta, cierra sesión primero.

Luego carga el dump del repositorio e indexa. Solo corre contra una base y un
Qdrant locales. Para borrar solo las cuentas y conservar el catálogo, usa
`reset_cuentas` (arriba).

---

### C. Detección y Reparación de Vectores Huérfanos: `check_tender_vector_orphans.py`

* **Ruta**: `monorepo/backend/scripts/check_tender_vector_orphans.py`
* **Propósito**: Detectar inconsistencias entre PostgreSQL y Qdrant (licitaciones que están en la base de datos pero no tienen vector en Qdrant, o vectores en Qdrant cuya licitación fue eliminada de la base de datos).
* **Uso**:
  ```bash
  # Solo auditar y reportar huérfanos
  docker compose exec api python -m scripts.check_tender_vector_orphans

  # Auditar y limpiar/reparar automáticamente
  docker compose exec api python -m scripts.check_tender_vector_orphans --reparar
  ```

---

## 2. Simulación y Testing de Alertas: `demo_alertas.py`

* **Ruta**: `monorepo/backend/scripts/demo_alertas.py`
* **Propósito**: Forzar y evaluar estados del sistema de alertas y correos (HdU 08) que normalmente requieren esperar intervalos temporales o cron jobs diarios.
* **Comandos disponibles**:
  ```bash
  # Ver estado de la cola de notificaciones y entregas de correo
  docker compose exec api python -m scripts.demo_alertas estado

  # Forzar envío del resumen diario inmediatamente (sin esperar a las 08:00 AM)
  docker compose exec api python -m scripts.demo_alertas resumen-ahora

  # Forzar reintento inmediato de correos pendientes (salta el backoff exponencial)
  docker compose exec api python -m scripts.demo_alertas reintentar-ahora

  # Cerrar licitaciones asociadas a alertas para comprobar comportamiento de licitaciones vencidas
  docker compose exec api python -m scripts.demo_alertas cerrar-licitacion

  # Simular rebote permanente para verificar desactivación de entrega de correo
  docker compose exec api python -m scripts.demo_alertas marcar-rebote
  ```

---

## 3. Backfills y Utilidades de Base de Datos

* **`backfill_buyer_comuna.py`**: Asigna comunas a instituciones compradoras en registros antiguos que no tenían ese dato.
  ```bash
  docker compose exec api python -m scripts.backfill_buyer_comuna
  ```
* **`backfill_tender_payloads.py`**: Actualiza los metadatos almacenados en los puntos vectoriales de Qdrant sin tener que re-calcular embeddings.
  ```bash
  docker compose exec api python -m scripts.backfill_tender_payloads
  ```
* **`migrate_tender_dates_to_utc.py`**: Estandariza las fechas históricas de licitaciones a formato UTC.
  ```bash
  docker compose exec api python -m scripts.migrate_tender_dates_to_utc
  ```
* **`sql.py`**: Permite ejecutar sentencias SQL rápidas contra la base configurada en `.env` directamente desde la terminal.
  ```bash
  docker compose exec api python -m scripts.sql "SELECT COUNT(*) FROM tender;"
  ```

---

## 4. Scripts de Carga y Evaluación del Matching (`tests/matching_evaluation/`)

* **`python -m scripts.dump`** (en `scripts/`, no aquí): `exportar` escribe el dump (`project-data/chiripa_tenders.xlsx`) desde la base de `DATABASE_URL`; `cargar` reemplaza el catálogo local por el dump e indexa `tenders`, `tender_items` y `tender_lexical`; `revivir` corre las fechas del catálogo cargado para que vuelva a estar vigente, sin recalcular vectores.
* **`generar_dataset.py`**: Trae compras ágiles desde la API de Mercado Público a la base local, para armar un dump sin acceso a producción. Consume cuota del ticket.
* **`evaluate_matching_profiles.py`** y **`run_calibrated_benchmark.py`**: Scripts de benchmark y evaluación cuantitativa de la precisión del motor de matching semántico.

---

## 5. Herramientas de Desarrollo

A diferencia de los anteriores, estos scripts no tocan datos: ayudan durante el
desarrollo y son los mismos que corre el CI.

### A. Diagnóstico de Cabezas de Alembic: `migraciones.py`

* **Ruta**: `monorepo/backend/scripts/migraciones.py`
* **Propósito**: Resolver el choque de cabezas múltiples (Problema A de la
  [guía de migraciones](./alembic-migraciones.md)). Compara el grafo de
  `alembic/versions/` con lo que tu rama agrega respecto de `develop` y decide
  **cuál de las dos soluciones** corresponde: repuntar el `down_revision`, si la
  migración solo existe en tu rama, o `alembic merge heads`, si ya está aplicada
  en algún entorno. Nombra el archivo y la revisión de destino.
* **Comportamiento seguro**:
  * **No abre conexión a la base** ni ejecuta `env.py`: solo lee archivos y
    consulta a git. No necesita variables de entorno.
  * **`--arreglar` no commitea ni empuja nada**: reescribe una línea y te deja
    revisarla.
  * **Se abstiene cuando no está seguro**: con más de dos cabezas, con dos
    migraciones propias, o si no puede comparar contra la rama base, no propone
    repuntar y manda a resolverlo a mano.
* **Uso**:
  ```bash
  # Desde monorepo/backend, con el entorno virtual activo:
  python -m scripts.migraciones                    # diagnostica
  python -m scripts.migraciones --arreglar         # y lo corrige si es seguro
  python -m scripts.migraciones --base origin/main # comparar contra otra rama
  ```
