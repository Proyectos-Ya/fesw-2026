# Chiripa Backend — FastAPI

Backend de **Chiripa**, construido con FastAPI, SQLModel, Alembic, PostgreSQL (Supabase) y Qdrant.

> **Identificadores técnicos**: El proyecto conserva internamente nombres históricos (`proyectosya_api`, `fesw-2026`, base de datos y contenedores). No renombrarlos sin acuerdo previo.

---

## Requisitos Previos

* **Python 3.12+** ([**uv**](https://docs.astral.sh/uv/) es opcional)
* **Docker Desktop** (con al menos **4 GB de RAM asignados**: los modelos de embeddings y reranker corren dentro del contenedor)
* **Supabase CLI**

> **Windows**: Trabajar dentro de **WSL2**. Si usas Windows directo, agrega `WATCHFILES_FORCE_POLLING=1` al `.env`.

---

## Configuración Inicial

1. **Variables de entorno.** Hay un solo `.env`, en `monorepo/`: lo leen tanto
   `docker compose` como la API y Alembic (`app/config.py` lo busca ahí). Desde
   `monorepo/`:
   ```bash
   cp .env.example .env
   ```
   Completa al menos `MERCADO_PUBLICO_API_KEY`, `GEMINI_API_KEY` y `GEMINI_MODEL`, que son
   obligatorias: sin ellas la API no arranca.

2. **Entorno virtual local (`.venv`)**, desde `monorepo/backend/`. Crea el entorno con
   cualquiera de estas dos opciones:
   ```bash
   python3.12 -m venv .venv           # con el Python del sistema
   uv venv --seed --python 3.12       # o con uv, si lo usas
   ```
   Después actívalo e instala las dependencias:
   ```bash
   source .venv/bin/activate    # En Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   ```
   Las dependencias viven en los `requirements*.txt` (el `Dockerfile` instala desde ahí),
   así que no se usa `uv add` ni `pyproject.toml` para gestionarlas.
   `requirements-dev.txt` incluye `requirements-test.txt` y suma los modelos en proceso
   (`sentence-transformers`, `onnxruntime`), que arrastran PyTorch. Si solo vas a correr
   tests, basta con `pip install -r requirements-test.txt`.

3. **Clave de firma de Supabase Auth**, desde la raíz del repositorio:
   ```bash
   supabase gen signing-key --algorithm ES256 > supabase/signing_keys.json
   ```

---

## Cómo Levantar el Proyecto

La API se ejecuta a través de **Docker Compose**. Postgres y Auth los pone Supabase, no el
compose:

```bash
# 1. Base de datos y Auth local (desde la raíz del repo)
supabase start

# 2. API y Qdrant (desde monorepo/)
docker compose up -d

# 3. Frontend (desde monorepo/frontend/)
pnpm dev
```

El contenedor de la API corre `alembic upgrade head` antes de arrancar `uvicorn --reload`,
así que en local no hace falta migrar a mano.

* **API / Swagger**: [http://localhost:8000](http://localhost:8000) (documentación en `/docs`)
* **Frontend**: [http://localhost:3000](http://localhost:3000)
* **Supabase Studio**: [http://localhost:54323](http://localhost:54323)
* **Qdrant Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
* **Mailpit (correos locales)**: [http://localhost:54324](http://localhost:54324)

**Espera a que la API esté lista antes de abrir el navegador.** El primer arranque
descarga los modelos (`bge-m3`, ~2 GB, y el reranker ONNX, ~1,3 GB) a un volumen que se
conserva entre reinicios; los siguientes solo los cargan en memoria. Si entras antes, el
frontend muestra `Failed to fetch`:

```bash
curl http://localhost:8000/health    # En PowerShell: curl.exe ...
```

Cuando responda `{"status":"healthy"}`, entra a http://localhost:3000.

### Modelos: local vs. producción

| | Local (compose) | Producción |
|---|---|---|
| `EMBEDDING_PROVIDER` | `local` (bge-m3 en proceso) | `huggingface` (por API) |
| `RERANKER_PROVIDER` | `local` (ONNX en proceso) | `pinecone` (por API) |
| Imagen (`Dockerfile`) | target `dev`: con torch y onnxruntime, `--reload`, root | target `runtime` (por defecto): sin modelos, usuario `app` |

El compose fija los dos proveedores en `local` a propósito, aunque el `.env` diga otra
cosa: en local no hace falta ninguna cuenta de terceros ni se gastan créditos. Si la
máquina no tiene RAM para el reranker, `DISABLE_RERANKER=true` lo apaga.

### Crear tu cuenta

No hay script de siembra de usuarios: las cuentas las emite Supabase Auth. Regístrate en
`/register`, confirma el correo desde Mailpit (http://localhost:54324) y completa el
onboarding de la empresa.

---

## Base de Datos y Datos de Prueba

### Migraciones con Alembic
El esquema se gestiona **únicamente con Alembic** (ver [AGENTS.md](../../AGENTS.md) y la [Guía Operativa de Alembic](../../docs/guides/alembic-migraciones.md)). Desde `monorepo/backend/` con el `.venv` activo:
```bash
alembic upgrade head
alembic revision --autogenerate -m "descripcion"
```
* **Cabezas múltiples**: Antes de abrir un PR, ejecuta `python -m scripts.migraciones` (el mismo chequeo que corre el CI). Si hay más de una cabeza, te dice cómo resolverlo y con `--arreglar` repunta tu migración a la cabeza de `develop` (ver [SKILL.md](../../SKILL.md) §1).
* **Guía Completa y Troubleshooting**: Consulta la [Guía Operativa de Migraciones con Alembic](../../docs/guides/alembic-migraciones.md) para resolver cabezas múltiples, revisiones huérfanas, drift o errores de `EsquemaSinMigrar`.

### Cargar Datos desde el Dump
Para sembrar licitaciones de prueba (`project-data/chiripa_tenders.xlsx`, en la raíz del
repo) en PostgreSQL y Qdrant:
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

Para vaciar licitaciones o resetear usuarios y empresas sin borrar el catálogo, ver la
[Guía de Scripts Utilitarios](../../docs/guides/scripts-utilitarios.md).

### Ingestar desde Mercado Público

La ingesta **no corre dentro de la API**: la hacen dos crons, que también se pueden
lanzar a mano.

Con la infraestructura arriba y `MERCADO_PUBLICO_API_KEY` en `monorepo/.env`:

```bash
python -m scripts.sync_diaria --limite 100
```

Es el mismo script que corre el cron nocturno de Railway: lista lo publicado
desde la última corrida buena, baja el detalle de lo nuevo (y de lo reencolado)
y registra la corrida en `ingestion_run`. `--limite` acota cuántas se listan;
con él la corrida termina `partial` (código 1), que es lo esperado en una
prueba. El script se niega a correr contra una base que no sea local salvo con
`--confirmar-produccion`.

Las licitaciones **ya guardadas** las mantiene al día otro cron,
`sync_estados`, que corre cada hora:

```bash
python -m scripts.sync_estados --ventana-horas 0.25
```

Lista lo que cambió en la API en la ventana (sin pedir el detalle), escribe
estado y fecha de cierre, saca del índice vectorial lo que dejó de estar activo,
reencola las publicadas que cambiaron para que el nocturno baje su detalle, y al
final marca las vencidas. La ventana, el tope de ítems y el tope de tiempo se
ajustan con `SYNC_ESTADOS_VENTANA_HORAS`, `SYNC_ESTADOS_LIMITE` y
`SYNC_ESTADOS_TIMEOUT_MINUTOS` (ver `monorepo/.env.example`). A mediodía hay del
orden de 1.600 cambios por hora, así que en local conviene una ventana corta.

Las dos ventanas se mandan a la API en hora de Chile aunque lleven "Z": la API
guarda y compara hora de pared de Chile con etiqueta UTC (medido el 2026-09-29).
Eso lo resuelve `mercado_publico_client.py`; el resto del sistema trabaja en UTC.

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

Tres bucles `asyncio` arrancan en el lifespan de la API (`app/main.py`), si
`RUN_NOTIFICATION_SCAN=true`
(`app/infrastructure/services/notifications/notification_scheduler.py`). Leen lo que ya
está en la base, venga de los crons de ingesta o del dump:

| Bucle | Cada cuánto | Qué hace |
|---|---|---|
| Escaneo | `NOTIFICATION_SCAN_INTERVAL_SECONDS` (300 s) | Ejecuta el matching por empresa y crea un aviso por cada licitación sobre el umbral del usuario |
| Entrega | 30 s | Vacía la cola de correos pendientes y reintenta los que fallaron |
| Resumen | Diario, `NOTIFICATION_DIGEST_HOUR` (hora de Chile) | Agrupa en un correo los avisos de quienes eligieron resumen diario |

La tabla `notification` tiene una constraint única `(user_id, tender_id, kind)`: es el
registro de "ya avisé de esta licitación", y sin ella cada ciclo repetiría los mismos
avisos. El escaneo solo mira los avisos `kind = 'match'`; los `date_changed` son los de
"Fecha modificada" de la HU-16 (ver la sección siguiente).

La cola de correos vive en `notification_delivery`. Si el servidor de correo no responde,
la fila queda en `pending` con un backoff exponencial (2, 4, 8… minutos, con tope de 60) y
sale sola cuando el servicio vuelve. Si el proveedor rechaza la dirección de forma
definitiva, la entrega queda en `failed_permanent`, se apaga
`notification_preference.email_delivery_enabled` y el usuario ve el motivo en
`/configuracion/notificaciones`, donde puede reactivarlo.

> Esto asume **una sola instancia** de la API. Con dos
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

## Hitos y sincronización con Google Calendar (HU-16)

La ficha de cada licitación muestra sus hitos: publicación y cierre oficiales, más los que
Gemini extrae de las bases que el usuario sube al asistente. Los elegidos se sincronizan
con su Google Calendar y, si Mercado Público mueve una fecha, el evento se actualiza solo y
llega un aviso **Fecha modificada** (en la app y por correo). Los hitos a 5 días o menos se
destacan en la tabla, y cada uno admite un **recordatorio** propio —1, 3 o 7 días antes—
que avisa en la app y por correo sin depender de haber sincronizado el calendario.

La guía completa —cómo crear el cliente OAuth en Google Cloud, la llave de cifrado, los
endpoints, las migraciones y cómo comprobar cada criterio a mano— está en
[`monorepo/TESTING-HU16.md`](../TESTING-HU16.md). Lo mínimo para activarlo:

| Variable | Qué es |
|---|---|
| `GOOGLE_CALENDAR_CLIENT_ID` / `GOOGLE_CALENDAR_CLIENT_SECRET` | Cliente OAuth web; redirect `APP_BASE_URL` + `/calendario/callback/google` |
| `TOKEN_ENCRYPTION_KEY` | Llave Fernet con que se cifran los tokens en la base |
| `RUN_MILESTONE_REFRESH` / `MILESTONE_REFRESH_INTERVAL_SECONDS` | Bucle que revisa cambios de fecha (por defecto cada 6 h) |

Sin `GOOGLE_CALENDAR_CLIENT_ID` la sincronización queda apagada y el resto funciona igual.
Con el ID puesto, el secreto y la llave son obligatorios: sin ellos la API no arranca.

Los bucles de la HU-16 se suman a los de alertas, con la misma premisa de
**una sola instancia**:

| Bucle | Cada cuánto | Qué hace |
|---|---|---|
| Cambios de fecha | `MILESTONE_REFRESH_INTERVAL_SECONDS` (6 h) | Refresca en Mercado Público las licitaciones abiertas con hitos sincronizados; si cambió la publicación o el cierre, actualiza el evento y avisa |
| Recordatorios | fijo, 1 h (`REMINDER_LOOP_SECONDS`) | Busca los hitos cuya anticipación ya se cumplió y deja el aviso; la anticipación se elige en días, así que revisar cada hora alcanza |

Los correos de "Fecha modificada" y de los recordatorios salen por la cola de las alertas,
así que necesitan `RUN_NOTIFICATION_SCAN=true` — que además enciende el bucle de
recordatorios.

---

## Calidad de Código y Pruebas

Desde `monorepo/backend/` con el `.venv` activo. Ruff cubre linting y formateo; su
configuración está en `pyproject.toml`.

```bash
ruff check .          # detectar problemas
ruff check . --fix    # corregir los que se pueden automáticamente
ruff format .         # formatear
pytest                                        # suite completa
pytest -m "not integration and not network"   # sin Postgres real ni DNS público
```

* **TDD** es obligatorio para el código de producción; los experimentos en `spikes/` no requieren tests (ver [AGENTS.md](../../AGENTS.md)).
* **OpenAPI**: Toda ruta de la API debe definir `summary`, `tags` y `response_model` para la documentación en `/docs`.

---

## Endpoints principales
- `GET /` — Mensaje de bienvenida
- `GET /health` — Estado del servicio (lo usa el `HEALTHCHECK` del `Dockerfile`)
- `GET /docs` — Documentación interactiva (Swagger UI) con el resto de las rutas

---

## Estructura del Proyecto (Clean Architecture)

```text
app/
├── domain/                  # Núcleo de negocio (entities, models, errors, services)
├── application/             # Casos de uso (use_cases, schemas, repositories, rules, services)
├── infrastructure/          # Detalles técnicos (routers, repositories, services, auth, db)
├── bootstrap/               # Composition root: arma servicios, repositorios, rutas y runners
├── shared/                  # Constantes y utilidades comunes
├── config.py                # Settings (lee monorepo/.env)
└── main.py                  # Fábrica de la app y lifespan (bucles en segundo plano)
scripts/                     # Crons y utilidades (`python -m scripts.<nombre>`)
alembic/                     # Migraciones
```
* Las dependencias van en una sola dirección: `infrastructure` → `application` → `domain`.
* Los casos de uso dependen de interfaces abstractas; las implementaciones de base de datos van en `infrastructure/repositories/`. `bootstrap/` es el único lugar que conoce las implementaciones concretas y las inyecta.

---

## Despliegue

Railway construye `monorepo/backend/Dockerfile` (target `runtime`) y corre
`alembic upgrade head` como `preDeployCommand` (`railway.toml`). Por eso las migraciones
deben ser compatibles hacia atrás. Esa configuración **caduca el 2026-12-01**: ver
[AGENTS.md](../../AGENTS.md) §3.

La imagen corre **un solo worker**: los bucles de alertas, hitos y exportaciones viven en
el proceso de la API y se duplicarían con más de una instancia.

---

## Documentación Relacionada

* [AGENTS.md](../../AGENTS.md) — Reglas para agentes y decisiones de arquitectura.
* [SKILL.md](../../SKILL.md) — Convenciones de Git, commits y checklist pre-PR.
* [docs/README.md](../../docs/README.md) — Índice de ADRs, planes y guías técnicas.
* [docs/guides/scripts-utilitarios.md](../../docs/guides/scripts-utilitarios.md) — Scripts de mantenimiento y reseteo.
* [monorepo/TESTING-HU16.md](../TESTING-HU16.md) y [monorepo/TESTING-HU19.md](../TESTING-HU19.md) — Guías de prueba de hitos/calendario y de compartir/exportar.
