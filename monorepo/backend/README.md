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
El esquema se gestiona **únicamente con Alembic** (ver [AGENTS.md](../../AGENTS.md) y la [Guía Operativa de Alembic](../../docs/guides/alembic-migraciones.md)):
```bash
alembic upgrade head
alembic revision --autogenerate -m "descripcion"
```
* **Cabezas múltiples**: Antes de abrir un PR, ejecuta `alembic heads`. Debe devolver una sola línea. Si hay conflicto entre ramas, repunta `down_revision` a la cabeza de `develop` (ver [SKILL.md](../../SKILL.md) §1).
* **Guía Completa y Troubleshooting**: Consulta la [Guía Operativa de Migraciones con Alembic](../../docs/guides/alembic-migraciones.md) para resolver cabezas múltiples, revisiones huérfanas, drift o errores de `EsquemaSinMigrar`.

### Cargar Datos desde el Dump
Para sembrar licitaciones vigentes de prueba en PostgreSQL y Qdrant:
```bash
# Desde monorepo/backend/ con .venv activo:
python tests/matching_evaluation/load_postgres_robust.py
python tests/matching_evaluation/load_dataset.py
```

Las licitaciones del dump que ya cerraron se cargan con sus fechas corridas un mes
hacia adelante (los meses que hagan falta si el dump es más viejo), manteniendo la
separación entre publicación, cierre y último cambio. Es lo que mantiene el corpus de
prueba visible en la app: sin eso el dump caducaría a las pocas semanas y el
dashboard saldría vacío. Las fechas dejan de ser las reales de cada licitación, que
para probar la aplicación da lo mismo.

**3.** Crea tu cuenta desde la aplicación. Ya no hay script de siembra: las
cuentas las emite Supabase Auth, así que hay que registrarse en `/register`,
confirmar el correo desde Mailpit (http://localhost:54324) y completar el
onboarding de la empresa. Ver el pendiente **5.3** para el script que lo
automatizaría.

**4.** Levanta la aplicación:

```bash
cd monorepo && docker compose up -d
cd frontend && pnpm dev
```

**Espera a que la API esté lista antes de abrir el navegador** — tarda porque carga
el modelo de embeddings. Si entras antes, el frontend muestra `Failed to fetch`:

```bash
curl http://localhost:8000/health
```

En Windows (PowerShell), `curl` es un alias de `Invoke-WebRequest`:

```powershell
curl.exe http://localhost:8000/health
```

Cuando responda `{"status":"healthy"}`, entra a http://localhost:3000.

### Ingestar desde Mercado Público (Modo B)

Con la infraestructura arriba y `MERCADO_PUBLICO_API_KEY` en `monorepo/.env`:

```bash
python -m scripts.sync_diaria --limite 100
```

Es el mismo script que corre el cron de Railway: marca las vencidas, lista lo
publicado en las últimas 24 h, baja el detalle y registra la corrida en
`ingestion_run`. `--limite` acota cuántas se listan; con él la corrida termina
`partial` (código 1), que es lo esperado en una prueba. El script se niega a
correr contra una base que no sea local salvo con `--confirmar-produccion`.

No hay que deshacer nada del dump: los dos modos escriben en las mismas tablas e
insertan con `ON CONFLICT DO NOTHING`, así que la ingesta agrega licitaciones nuevas
sobre las que ya cargaste. Lo único que pierdes es la reproducibilidad.

Si quieres partir solo con lo que traiga la API:

```bash
docker exec supabase_db_fesw-2026 psql -U postgres -c "truncate tender_item, tender, tender_metadata, matching_result, buyer_institution cascade;"
curl -X DELETE http://localhost:6333/collections/tenders
```

### Regenerar el dump

Lo hace **una sola persona**, porque consume cuota compartida del ticket.

**No es parte del día a día.** El dump es un corpus de prueba y las compras ágiles
duran unos diez días, así que sus licitaciones se cierran solas; para eso está el
desplazamiento de fechas al cargarlo, que las mantiene visibles en la app
indefinidamente. Regenerar sirve cuando quieres **otro** corpus: más licitaciones,
de otras regiones o de otros rubros.

**1. Infraestructura arriba.** `generar_dataset.py` no es autónomo: escribe en la
base del `.env`, indexa en Qdrant y necesita `MERCADO_PUBLICO_API_KEY`.

```bash
supabase start              # desde la raíz del repositorio
docker compose up -d qdrant # desde monorepo/
alembic upgrade head        # desde monorepo/backend/
```

**2. Base limpia (opcional).** El export saca del `.env` todo lo que tenga
`closing_at > now()`, así que si ahí quedó un dump cargado, sus licitaciones —con la
fecha ya desplazada— entran también al xlsx nuevo. Para un corpus de prueba eso no
molesta; solo ten en cuenta que cada ciclo de cargar y volver a exportar les corre
otro mes. Vacía la base si quieres el corpus nuevo limpio, o sáltate este paso si
prefieres acumular sobre lo que ya tienes.

```bash
docker exec supabase_db_fesw-2026 psql -U postgres -c "truncate tender_item, tender, tender_metadata, matching_result, buyer_institution cascade;"
curl -X DELETE http://localhost:6333/collections/tenders
```

**3. Traer licitaciones y volcarlas al xlsx.**

```bash
python tests/matching_evaluation/generar_dataset.py --limite 300
python tests/matching_evaluation/export_dataset.py
```

El primero trae compras ágiles vigentes desde la API (~1 petición por licitación) y
las deja en la base y en Qdrant. Al terminar imprime cuántas quedaron vigentes; si
son 0, no sigas: el xlsx saldría vacío. El segundo lee la base del `.env` y
**sobrescribe** el xlsx solo con las vigentes, sin acumular cerradas.

Ese es el único script que escribe el dump. La dirección contraria —dump a base— es
de `load_postgres_robust.py` y `load_dataset.py`, que nunca tocan el archivo.

**4. Compartirlo por git.**

```bash
git add project-data/chiripa_tenders.xlsx
git commit -m "data(dataset): actualizar dump de licitaciones vigentes"
```

### Comprobar que el corpus sirve

Lo único que importa es cuántas están vigentes:

```bash
docker exec supabase_db_fesw-2026 psql -U postgres -c "select count(*) total, count(*) filter (where closing_at > now()) vigentes from tender;"
```

Si `vigentes` es 0, el dashboard saldrá vacío por más filas que haya. Cargando el
dump no debería pasar, porque las cerradas entran con la fecha corrida; si pasa,
revisa que la carga haya sido con `load_postgres_robust.py`.

Y si el dashboard sale vacío con licitaciones vigentes, casi siempre es el **filtro
por región**, que es estricto: un proveedor solo ve licitaciones de las regiones que
declaró.

```bash
docker exec supabase_db_fesw-2026 psql -U postgres -c "select r.name, count(*) from tender t join buyer_institution b on b.rut=t.buyer_rut join region r on r.id=b.region_id group by r.name order by 2 desc;"
```

> **Sobre los porcentajes.** Con la calibración actual del reranker, un perfil bien
> completado alcanza compatibilidades sobre el umbral verde (70%). Si ves un corpus
> entero en porcentajes de un dígito, revisa que el perfil tenga rubros y palabras
> clave cargados: la mitad del puntaje sale de esas coincidencias.


---

## Alertas de nuevas licitaciones (HdU 08)

La aplicación revisa en segundo plano si aparecieron licitaciones compatibles con cada
empresa y avisa por dos canales: un aviso en la plataforma y un correo.

### Cómo funciona

Tres bucles `asyncio` arrancan con la API, igual que los de ingesta
(`app/infrastructure/services/notifications/notification_scheduler.py`):

| Bucle | Cada cuánto | Qué hace |
|---|---|---|
| Escaneo | `NOTIFICATION_SCAN_INTERVAL_SECONDS` (300 s) | Ejecuta el matching por empresa y crea un aviso por cada licitación sobre el umbral del usuario |
| Entrega | 30 s | Vacía la cola de correos pendientes y reintenta los que fallaron |
| Resumen | Diario, `NOTIFICATION_DIGEST_HOUR` (hora de Chile) | Agrupa en un correo los avisos de quienes eligieron resumen diario |

La tabla `notification` tiene una constraint única `(user_id, tender_id)`: es el registro
de "ya avisé de esta licitación", y sin ella cada ciclo repetiría los mismos avisos.

La cola de correos vive en `notification_delivery`. Si el servidor de correo no responde,
la fila queda en `pending` con un backoff exponencial (2, 4, 8… minutos, con tope de 60) y
sale sola cuando el servicio vuelve. Si el proveedor rechaza la dirección de forma
definitiva, la entrega queda en `failed_permanent`, se apaga
`notification_preference.email_delivery_enabled` y el usuario ve el motivo en
`/configuracion/notificaciones`, donde puede reactivarlo.

> Como el scheduler de ingesta, esto asume **una sola instancia** de la API. Con dos
> réplicas ambas escanearían y los correos saldrían duplicados.

### Correo en desarrollo

`supabase start` levanta un servidor de correo de prueba. No hace falta configurar nada:
los valores por defecto ya apuntan ahí.

| Qué | Dónde |
|---|---|
| Bandeja de entrada | [http://localhost:54324](http://localhost:54324) |
| Puerto SMTP | `54325` (declarado en `supabase/config.toml`) |

Si los correos no llegan, revisa que `smtp_port = 54325` esté **descomentado** en
`supabase/config.toml` y reinicia con `supabase stop && supabase start`.

Para ver el criterio del servicio caído: baja Supabase, provoca avisos nuevos, mira la
fila en "Pendiente" en `/configuracion/notificaciones`, y vuelve a levantarlo.

### Correo en producción

El servicio es SMTP genérico (`SmtpEmailService`), así que cambiar de entorno es cambiar
variables:

| Variable | Local | Brevo | SendGrid |
|---|---|---|---|
| `SMTP_HOST` | `host.docker.internal` | `smtp-relay.brevo.com` | `smtp.sendgrid.net` |
| `SMTP_PORT` | `54325` | `587` | `587` |
| `SMTP_USER` | *(vacío)* | login SMTP | `apikey` (literal) |
| `SMTP_PASSWORD` | *(vacío)* | SMTP key | API key |
| `SMTP_USE_TLS` | `false` | `true` | `true` |
| `SMTP_FROM` | cualquiera | remitente verificado | remitente verificado |
| `APP_BASE_URL` | `http://localhost:3000` | URL pública del frontend | ídem |

**Hay que verificar el remitente antes de la demo** o el proveedor rechaza todo envío. No
requiere dominio propio: ambos permiten verificar una sola dirección que ya controles,
confirmando desde un correo que te llega. `SMTP_PASSWORD` es un secreto y va en las
variables del proveedor de despliegue, nunca en el repositorio.

> Si el remitente verificado es un `@gmail.com`, los correos enviados en su nombre chocan
> con la política DMARC de Gmail y suelen caer en spam. Llegan, pero hay que mirar esa
> carpeta antes de concluir que falló.

### Cómo comprobar los criterios de aceptación

Cuatro de los siete se ven levantando la aplicación y usándola. Los otros tres describen
situaciones que el sistema está diseñado para que **no** ocurran, así que hay que
provocarlas: de eso se encarga `scripts/demo_alertas.py`.

Dos cosas que conviene tener presentes antes de empezar:

- **Reiniciar la API fuerza un escaneo inmediato.** `start_scan_loop` ejecuta antes de
  dormir, así que no hay que esperar los 5 minutos del intervalo:
  `docker compose restart api`.
- **`uvicorn --reload` no relee el `.env`.** Cualquier cambio de variable exige reiniciar
  el contenedor. Es el error más habitual al probar esto.

El script se ejecuta dentro del contenedor, que ya tiene las dependencias:

```bash
docker compose exec api python -m scripts.demo_alertas estado
```

| Criterio | Cómo se comprueba |
|---|---|
| Detecta y avisa (correo + panel) | Baja el umbral en `/configuracion/notificaciones`, reinicia la API. El aviso aparece en `/alertas` y el correo en http://localhost:54324 |
| El enlace lleva al detalle | Clic en el aviso, y clic en el enlace del correo desde Mailpit |
| Umbral y frecuencia configurables | Se cambian en `/configuracion/notificaciones`. Para ver **llegar** el resumen diario sin esperar a las 08:00: `demo_alertas resumen-ahora` |
| Licitación ya cerrada | `demo_alertas cerrar-licitacion` y abre ese aviso |
| Servicio de correo caído | Ver más abajo |
| Correo inexistente | Solo con proveedor real; `demo_alertas marcar-rebote` reproduce el estado visible, no la detección |
| Pide sesión antes de mostrar datos | Cierra sesión y abre el enlace del correo en una ventana privada |

#### El criterio del servicio caído

**No uses `supabase stop`.** Mailpit vive dentro del stack de Supabase, así que ese comando
se lleva también a Postgres: el bucle de entrega no puede ni leer su propia cola y verías
un error de base de datos, que es otro problema distinto.

La forma correcta es dejar el SMTP apuntando a un puerto muerto, en `monorepo/.env`:

```bash
SMTP_PORT=59999
```

```bash
docker compose restart api
```

Da *connection refused* inmediato. Genera avisos nuevos bajando el umbral y míralos quedar
en **Pendiente**, con su contador de intentos, en `/configuracion/notificaciones`. Después
restaura `SMTP_PORT=54325`, reinicia, y para no esperar el backoff exponencial:

```bash
docker compose exec api python -m scripts.demo_alertas reintentar-ahora
```

Es la misma maniobra que en producción, donde se cambia `SMTP_HOST` en el panel del
proveedor de despliegue.

#### Lo que no se puede comprobar en local

Que el sistema **detecte** un correo inexistente y desactive el envío necesita un
proveedor real: Mailpit acepta cualquier destinatario por diseño y jamás devuelve un
rechazo definitivo. Apuntando el `.env` a Brevo o SendGrid se comprueba sin desplegar
nada, y las cuentas demo ya usan direcciones `@demo.invalid` —un TLD reservado que nunca
resuelve—, así que el rebote es inmediato y genuino.

---

## Compartir y exportar licitaciones (HdU 19)

Desde la ficha de una licitación se puede compartir un **enlace público de 7 días**
(revocable, sin cuenta para quien lo abre) y **exportar a PDF o Excel**. La guía completa
—uso, API, migraciones y cómo comprobar cada criterio a mano— está en
[`monorepo/TESTING-HU19.md`](../TESTING-HU19.md).

| Variable | Default | Qué es |
|---|---|---|
| `EXPORT_INLINE_TIMEOUT_SECONDS` | `10` | Si generar el archivo tarda más, se responde de inmediato y se avisa por correo cuando esté listo |

- El PDF se genera con **ReportLab** (`reportlab` en `requirements.txt`): es un wheel puro y
  no necesita paquetes del sistema en la imagen.
- Las exportaciones que pasan a segundo plano se guardan en la tabla `export_job` (el disco
  del contenedor es efímero) y vencen a los 7 días. Como los bucles de alertas, asumen
  **una sola instancia** de la API; al arrancar se marcan fallidas las que quedaron a medias.
- El correo de "archivo listo" usa el mismo `SmtpEmailService` que las alertas, pero se
  envía directo: no depende de `RUN_NOTIFICATION_SCAN` ni de las preferencias de alertas.

---

## Calidad de código

Ruff cubre el linting y el formateo. La configuración está en `pyproject.toml`.

```bash
ruff check .          # detectar problemas
ruff check . --fix    # corregir los que se pueden automáticamente
ruff format .         # formatear
```

Ambos vienen en `requirements-dev.txt`, así que están disponibles con el venv activado.

---

## Endpoints principales
- `GET /` — Mensaje de bienvenida
- `GET /health` — Estado del servicio
- `GET /docs` — Documentación interactiva (Swagger UI)
---

## Estructura de Carpetas

La arquitectura del backend sigue los principios de **Clean Architecture** (Arquitectura Limpia), separando la lógica de negocio de los detalles tecnológicos e infraestructura. La estructura del directorio `app/` es la siguiente:
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
