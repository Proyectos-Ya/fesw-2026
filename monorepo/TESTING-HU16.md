# HU-16 — Extraer calendario de hitos y sincronizar con agenda personal

Rama `feat/HU-16-extraccion-hitos-calendario`, sobre `develop` (`776007c`). Alcance de esta
entrega: **Google Calendar**. Outlook queda pendiente (ver [Limitaciones](#limitaciones)); el
diseño ya lo contempla como un proveedor más, sin migraciones nuevas.

> Como representante de empresa, necesito que el sistema extraiga automáticamente el
> calendario de hitos de las bases guardadas y me permita sincronizarlo con mi calendario
> personal, para evitar olvidos o descalificaciones por retrasos en entregas.

## Uso

1. Abrir el detalle de una licitación. La sección **Hitos y fechas importantes** muestra de
   entrada la publicación y el cierre oficiales de Mercado Público.
2. Adjuntar las bases (PDF, XLSX o PNG) en el **asistente** de la licitación y pulsar
   **Extraer hitos de las bases**. La IA agrega visitas técnicas, consultas, entregas,
   adjudicación, etc., cada uno con el párrafo de las bases de donde salió.
3. Los plazos se destacan en rojo (3 días o menos) o amarillo (7 días o menos).
4. Elegir los hitos y pulsar **Sincronizar con Google Calendar**:
   - si algún hito no tiene hora exacta, se pide confirmar una (propone 09:00);
   - la primera vez, lleva a Google a autorizar el acceso y, al volver, termina la
     sincronización pedida;
   - los hitos sincronizados quedan marcados **En Google Calendar**.
5. Si Mercado Público mueve la publicación o el cierre, el evento se actualiza solo y llega
   un aviso **Fecha modificada** en `/alertas` y por correo.

Cada evento lleva el título del hito y de la licitación, la fecha y hora en hora de Chile,
el enlace de vuelta a la ficha (en la descripción y como enlace del evento) y recordatorios
1 día y 1 hora antes. Volver a sincronizar actualiza el mismo evento; si el usuario lo borró
en Google, se vuelve a crear.

## Configuración

Sin configurar, la app funciona igual: la tabla de hitos y la extracción con IA están
disponibles y el botón de sincronizar no aparece. Para activarlo:

### 1. Cliente OAuth en Google Cloud

1. En [console.cloud.google.com](https://console.cloud.google.com), crear un proyecto y
   habilitar la **Google Calendar API** (*APIs y servicios → Biblioteca*).
2. **Pantalla de consentimiento** (*Google Auth Platform*):
   - Tipo **Externo**, estado **Testing**.
   - En *Acceso a los datos*, agregar los scopes
     `https://www.googleapis.com/auth/calendar.events`, `openid` y
     `https://www.googleapis.com/auth/userinfo.email`. **No** el scope completo
     `.../auth/calendar`: con `calendar.events` alcanza y da menos acceso.
   - En *Público*, agregar como **test users** los correos que van a probar (máx. 100).
3. **Credenciales → Crear ID de cliente OAuth**, tipo *Aplicación web*:

   | Campo | Valor |
   |---|---|
   | Orígenes autorizados de JavaScript | `http://localhost:3000` (y la URL de producción) |
   | URIs de redireccionamiento autorizados | `http://localhost:3000/calendario/callback/google` (y su equivalente de producción) |

   El redirect tiene que coincidir **exactamente** con `APP_BASE_URL` +
   `/calendario/callback/google`, que es lo que manda el backend.

### 2. Llave de cifrado de los tokens

```bash
docker run --rm python:3.12-slim sh -c "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
```

### 3. Variables en `monorepo/.env`

```bash
GOOGLE_CALENDAR_CLIENT_ID=<id>.apps.googleusercontent.com
GOOGLE_CALENDAR_CLIENT_SECRET=<secreto>
TOKEN_ENCRYPTION_KEY=<llave generada>
APP_BASE_URL=http://localhost:3000
# Opcionales
RUN_MILESTONE_REFRESH=true
MILESTONE_REFRESH_INTERVAL_SECONDS=21600
```

Con el ID puesto y sin secreto o sin llave, la API **no arranca** y dice cuál falta; una
llave con formato inválido también corta el arranque. El secreto y la llave nunca se
commitean. Para rotar la llave: `TOKEN_ENCRYPTION_KEY=nueva,anterior` (la primera cifra,
todas descifran).

Después de cambiar el `.env`: `docker compose up -d --force-recreate api` (el reinicio
simple no relee las variables).

## Cómo funciona

| Pieza | Dónde |
|---|---|
| Normalización de fechas (criterio 5) | `app/domain/services/milestone_date_normalizer.py` |
| Extracción con Gemini | `app/infrastructure/services/gemini_milestone_extraction_service.py` |
| Hitos y urgencia | `app/application/use_cases/milestones/` |
| OAuth, conexión y sincronización | `app/application/use_cases/calendar/`, `app/infrastructure/services/calendar/google_calendar_client.py` |
| Cambios de fecha (criterio 4) | `refresh_synced_tender_dates.py` + `MilestoneRefreshScheduler` |
| Frontend | `src/features/tender-milestones/`, ruta `/calendario/callback/[provider]` |

- **Hitos oficiales**: publicación y cierre se toman de la licitación y se guardan al
  consultar, para que tengan id y se puedan sincronizar.
- **Extracción**: se envían a Gemini los documentos que el usuario subió al asistente, junto
  con las fechas oficiales como referencia para resolver fechas relativas ("el día 20"). La
  respuesta es JSON con esquema; cada fecha se valida (`YYYY-MM-DD` y `HH:MM` estrictos) y se
  convierte de hora de Chile a UTC. Las inválidas se descartan y se informa cuántas. Al
  volver a extraer, un hito equivalente (mismo tipo y título, sin importar tildes ni
  mayúsculas) conserva su id, así el evento ya sincronizado se actualiza en vez de
  duplicarse. Si Gemini falla, quedan igual los hitos oficiales.
- **Sincronización**: el token se refresca antes de vencer; si Google lo rechaza, se
  refresca una vez y se reintenta; si el refresh fue revocado, la conexión queda marcada y
  el frontend lleva a reconectar. Un hito que falla no detiene a los demás: la respuesta
  informa el resultado por hito y el reintento reenvía solo los fallidos.
- **Cambios de fecha**: cada `MILESTONE_REFRESH_INTERVAL_SECONDS` se revisan solo las
  licitaciones **abiertas** que alguien tiene sincronizadas. Se refrescan con la misma
  ingesta de siempre (SQL y Qdrant quedan alineados) y se comparan publicación y cierre.
  Si cambiaron: se actualizan los hitos oficiales, el evento en Google de cada usuario
  vinculado, y se deja un aviso `date_changed` con correo inmediato (aunque el usuario use
  resumen diario). Un nuevo cambio reemplaza el aviso y lo marca sin leer.

> El correo de "Fecha modificada" lo despacha el bucle de entrega de las alertas (HdU 08),
> que solo corre con `RUN_NOTIFICATION_SCAN=true`. El aviso en `/alertas` aparece igual.

## API y migraciones

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/tenders/{id}/milestones` | Hitos con urgencia y calendarios donde están sincronizados |
| `POST` | `/tenders/{id}/milestones/extract` | Extrae con IA desde los documentos del asistente |
| `POST` | `/tenders/{id}/milestones/sync` | Sincroniza `{provider, milestone_ids, default_time?}`; devuelve el resultado por hito |
| `GET` | `/calendar/connections` | Estado de la conexión (nunca devuelve tokens) |
| `POST` | `/calendar/{provider}/authorize` | Guarda la sincronización pedida y devuelve la URL de Google |
| `POST` | `/calendar/{provider}/callback` | Valida el `state`, intercambia el código y guarda la conexión |
| `DELETE` | `/calendar/connections/{provider}` | Revoca en Google y borra la conexión |

Errores: 401 sin sesión · 404 licitación o hitos ajenos · 409 hay que (re)conectar el
calendario · 422 falta la hora por defecto o el cuerpo es inválido · 502 Google no
respondió · 503 IA o calendario no disponibles/configurados.

Migraciones, ambas compatibles hacia atrás y en una sola cabeza:

- `b16c4e1a7d20` (después de `a227c0150001`): tablas `tender_milestone`,
  `calendar_connection`, `calendar_oauth_state` y `calendar_event_link`.
- `c16d5f2a8b31`: `notification` gana `kind` (default `'match'`) y `payload`, `score` pasa a
  nullable y el unique pasa a `(user_id, tender_id, kind)`. El escaneo y el resumen diario
  de HdU 08 siguen mirando solo los avisos `match`. El downgrade borra los avisos
  `date_changed`, que no tienen score.

## Seguridad (criterio 8)

- Tokens de Google cifrados con Fernet (AES + HMAC) en `calendar_connection`; en el dominio
  viajan como `SecretStr`, así que no se filtran en logs ni en respuestas.
- El `state` de OAuth es aleatorio (32 bytes), se guarda solo su SHA-256, vence a los 10
  minutos, está ligado al usuario y se consume con `DELETE … RETURNING` (un solo uso).
- Solo se piden los permisos `calendar.events` y `email`; si el usuario desmarca el de
  calendario en la pantalla de Google, la conexión se rechaza con un mensaje claro.
- Desconectar revoca el token en Google antes de borrarlo.
- El prompt de extracción trata los documentos como datos e ignora instrucciones que
  traigan.

## Verificación por criterio

| # | Criterio | Evidencia automatizada | Prueba manual |
|---|---|---|---|
| 1 | La IA extrae hitos a una tabla | `test_extract_tender_milestones.py`, `test_gemini_milestone_extraction_service.py`, `MilestonesSection.test.tsx` | Subir las bases y pulsar *Extraer hitos* |
| 2 | "Sincronizar" redirige a la autenticación del proveedor | `test_calendar_authorization.py`, `useCalendarSync.test.ts`, `CalendarOAuthCallback.test.tsx` | Sincronizar sin conexión previa |
| 3 | Evento con título, fecha exacta y enlace de retorno | `test_sync_milestones.py`, `test_google_calendar_client.py` (payload verificado) | Abrir el evento en Google Calendar |
| 4 | Cambio en Mercado Público → evento actualizado + "Fecha modificada" | `test_refresh_synced_tender_dates.py`, `test_dispatch_pending_deliveries.py`, `NotificationPanel.test.tsx` | Ver abajo |
| 5 | Fechas normalizadas a formato estándar | `test_milestone_date_normalizer.py` | — |
| 6 | Falla del proveedor → mensaje y reintento manual | `test_sync_milestones.py` (fallo parcial, refresh revocado), `SyncErrorAlert.test.tsx`, `MilestonesSection.test.tsx` | Revocar el acceso en Google (abajo) |
| 7 | Sin hora → confirmar hora por defecto | `test_sync_milestones.py`, `DefaultTimeDialog.test.tsx`, `MilestonesSection.test.tsx` | Sincronizar un hito "Sin hora exacta" |
| 8 | Tokens cifrados y nunca compartidos | `test_fernet_token_cipher.py`, `test_milestone_calendar_repositories.py` (columna ≠ texto plano), `test_calendar_router.py` (sin tokens en la respuesta) | `SELECT access_token_encrypted FROM calendar_connection` |

### Criterio 4 a mano

Mercado Público no cambia fechas a pedido, así que se simula corriendo la fecha en la base
local: el refresco la compara con la oficial y la ve "movida".

1. En `.env`: `MILESTONE_REFRESH_INTERVAL_SECONDS=60` y `RUN_NOTIFICATION_SCAN=true`;
   recrear el contenedor `api`.
2. Elegir una licitación **abierta** y correr su cierre un día, contra la base local
   (Postgres de Supabase en el puerto 54322):
   ```sql
   UPDATE tender SET closing_at = closing_at - interval '1 day' WHERE code = '<código>';
   ```
3. Abrir su detalle (los hitos oficiales toman la fecha corrida), elegir **Cierre de
   recepción de ofertas** y sincronizarlo. En Google Calendar el evento queda un día antes.
4. En el siguiente minuto el refresco trae la fecha real: el evento vuelve a su día, aparece
   **Fecha modificada** en `/alertas` y el correo llega a Mailpit (http://localhost:54324).

### Criterio 6 a mano

En [myaccount.google.com/permissions](https://myaccount.google.com/permissions), quitar el
acceso de la app y volver a sincronizar: el refresh es rechazado, la conexión queda
marcada y el frontend lleva a autorizar de nuevo. La caída de Google (5xx, timeout) se
cubre con los tests: muestra "La sincronización no pudo completarse" con **Reintentar**,
que reenvía solo los hitos fallidos.

## Verificación reproducible

Backend (sin Python 3.12 local, en un contenedor desde `monorepo/backend`, en Git Bash).
Se omite `sentence-transformers`, que el conftest reemplaza y arrastraría torch:

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/app" -w /app -e POSTGRES_PASSWORD=x -e MERCADO_PUBLICO_API_KEY=x -e GEMINI_API_KEY=x -e GEMINI_MODEL=x python:3.12-slim sh -c "cat requirements.txt requirements-test.txt | grep -v -e sentence-transformers -e '^-r' > /tmp/r.txt && pip install -q -r /tmp/r.txt huggingface_hub && pytest -q -m 'not integration and not network'"
```

Con un Postgres disponible se agregan `tests/integration/test_milestone_calendar_repositories.py`
y `tests/integration/test_migraciones.py`; `alembic heads` debe mostrar solo
`c16d5f2a8b31`.

Frontend:

```bash
pnpm test
pnpm exec tsc --noEmit
pnpm lint
```

## Limitaciones

- **Outlook** no está incluido. Sumarlo es un adaptador de `ICalendarProviderClient` con
  Microsoft Graph (tenant `common`), su entrada en `build_calendar_providers` y las variables
  `MICROSOFT_CALENDAR_*`; las tablas ya tienen la columna `provider`.
- Mientras la app de Google esté en **Testing**, los refresh tokens vencen a los 7 días: la
  app lo detecta y pide reconectar. En producción hay que publicar (y verificar) la app.
- Los documentos los sube el usuario al asistente: la API de Compra Ágil no entrega las
  bases. Los hitos extraídos son por usuario, como los documentos.
- Solo se vigilan en Mercado Público la publicación y el cierre; los hitos extraídos por IA
  no tienen fuente oficial con la que compararse.
- Como los demás loops, el refresco asume **una sola instancia** de la API.
