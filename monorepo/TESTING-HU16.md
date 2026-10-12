# HU-16 — Extracción y sincronización del calendario de hitos con agenda personal

Guía para probar la HdU 16 (Sprint 2). Está en `develop`; Outlook Calendar y el último ajuste
del criterio 1 llegan con los PRs de `fix/hu-16-ca1-extraccion-consistente` y
`feat/hu-16-outlook-calendar`. Sincroniza con **Google Calendar** y **Outlook Calendar**.

> Como representante de empresa, necesito extraer los hitos de una licitación (fechas de
> postulación, adjudicación, visitas técnicas y entregables) y sincronizarlos con mi
> calendario personal (Google Calendar u Outlook), para evitar olvidos o descalificaciones
> por retrasos en las entregas.

## Uso

1. Abrir el detalle de una licitación. La sección **Hitos y fechas importantes** muestra de
   entrada la publicación y el cierre oficiales de Mercado Público.
2. Adjuntar las bases (PDF, XLSX o PNG) en el **asistente** de la licitación. No hay que
   pulsar nada más: la IA las lee en segundo plano y la tabla muestra *"La IA está leyendo
   las bases que subiste…"* hasta que aparecen las visitas técnicas, consultas, entregas,
   adjudicación, etc., cada uno con una cita de las bases de donde salió. Cada base se lee
   **una sola vez**: el botón **Extraer hitos de las bases** solo se habilita si queda alguna
   sin leer (nueva o que falló). Para volver a leer una, se elimina y se sube de nuevo; al
   eliminarla, sus hitos se van de la tabla (salvo los que ya están en un calendario).
3. Los plazos a **5 días de calendario o menos** (criterio 9) se destacan en rojo y con la
   etiqueta entre exclamaciones (*¡Vence en 5 días!*, *¡Vence mañana!*, *¡Vence hoy!*); el
   resto va en gris (*Vence en 8 días*).
4. Elegir los hitos (la casilla del encabezado elige todos los pendientes) y pulsar
   **Sincronizar con mi calendario**:
   - con un solo calendario configurado en el servidor, sincroniza directo con ese; con
     Google y Outlook, abre un menú para elegir (cada opción dice si está conectada);
   - si algún hito no tiene hora exacta, se pide confirmar una (propone 09:00);
   - la primera vez, lleva a Google o a Microsoft a autorizar el acceso y, al volver, termina
     la sincronización pedida;
   - los hitos sincronizados quedan marcados **En Google Calendar** / **En Outlook
     Calendar**; un hito puede estar en los dos.
   - Debajo del botón se ve el estado de cada calendario ("conectado como …", "sin
     conectar" o "tu acceso expiró") con su **Desconectar**.
5. Si Mercado Público mueve la publicación o el cierre, el evento se actualiza solo y llega
   un aviso **Fecha modificada** en `/alertas` y por correo.
6. En la columna **Recordatorio** de cada hito se elige la anticipación: *Sin recordatorio*,
   *1 día antes*, *3 días antes* o *1 semana antes*. Al cumplirse, llega un aviso
   **Recordatorio** en `/alertas` y —si el usuario tiene el correo activado— un correo
   inmediato. Los hitos vencidos no ofrecen la opción.

Cada evento lleva como título el hito y la licitación ("Visita técnica — Reparación de
techumbre"), la fecha y hora exactas, y el enlace de vuelta a la ficha
(`APP_BASE_URL/matches/<id>`, en el texto "Ver la licitación en Chiripa"):

- **Google:** hora de Chile con su zona; el enlace también como fuente del evento ("Chiripa");
  avisos 1 día y 1 hora antes.
- **Outlook:** hora en UTC, que Outlook muestra en la zona del usuario; un solo aviso, 1 día
  antes, porque Outlook no admite más.

Esos avisos son del calendario y distintos del recordatorio del punto 6, que lo manda
Chiripa y no depende de haber sincronizado. Volver a sincronizar actualiza el mismo evento;
si el usuario lo borró en su calendario, se vuelve a crear.

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

### 1b. App de Outlook en Microsoft Entra ID

Opcional, igual que Google: sin estas variables la barra de Outlook no aparece.

1. En [entra.microsoft.com](https://entra.microsoft.com) (o portal.azure.com → *Microsoft
   Entra ID*): *Applications* → *App registrations* → *New registration*.
   - **Name:** `Chiripa (local)`.
   - **Supported account types:** *Accounts in any organizational directory (Any Microsoft
     Entra ID tenant - Multitenant) and personal Microsoft accounts*. Así sirve para
     Outlook.com, Hotmail y cuentas de trabajo o universidad.
   - **Redirect URI:** plataforma **Web**, `http://localhost:3000/calendario/callback/outlook`.
2. En *Overview*, el **Application (client) ID** es `MICROSOFT_CALENDAR_CLIENT_ID`.
3. *Certificates & secrets* → *New client secret* (180 días). Copiar la columna **Value**, no
   la *Secret ID*; solo se muestra una vez. Es `MICROSOFT_CALENDAR_CLIENT_SECRET`. Anotar la
   fecha de vencimiento: ese día hay que crear otro.
4. *API permissions* → *Add a permission* → *Microsoft Graph* → *Delegated*:
   `Calendars.ReadWrite`, `offline_access`, `openid` y `email` (`User.Read` ya viene). Con
   cuentas personales no hace falta *Grant admin consent*.
5. Para producción: en *Authentication*, **agregar** (sin quitar la local) la redirect
   `https://<dominio-del-frontend>/calendario/callback/outlook`. Fuera de `localhost` Azure
   exige `https`, y tiene que coincidir con `APP_BASE_URL` + `/calendario/callback/outlook`.

Microsoft no tiene lista de usuarios de prueba: cualquier cuenta Microsoft puede autorizar y
verá un aviso de "editor no verificado", que es normal en desarrollo.

### 2. Llave de cifrado de los tokens

```bash
docker run --rm python:3.12-slim sh -c "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
```

### 3. Variables en `monorepo/.env`

```bash
GOOGLE_CALENDAR_CLIENT_ID=<id>.apps.googleusercontent.com
GOOGLE_CALENDAR_CLIENT_SECRET=<secreto>
MICROSOFT_CALENDAR_CLIENT_ID=<Application (client) ID>
MICROSOFT_CALENDAR_CLIENT_SECRET=<Value del secreto>
MICROSOFT_CALENDAR_TENANT=common
TOKEN_ENCRYPTION_KEY=<llave generada>
APP_BASE_URL=http://localhost:3000
# Opcionales
RUN_MILESTONE_REFRESH=true
MILESTONE_REFRESH_INTERVAL_SECONDS=21600
```

Con el ID de cualquiera de los dos puesto y sin su secreto o sin llave, la API **no
arranca** y dice cuál falta (la llave es una sola para ambos); una
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
| OAuth, conexión y sincronización | `app/application/use_cases/calendar/`, `app/infrastructure/services/calendar/google_calendar_client.py` y `outlook_calendar_client.py`; proveedores disponibles en `app/bootstrap/builders.py` |
| Cambios de fecha (criterio 4) | `refresh_synced_tender_dates.py` + `MilestoneRefreshScheduler` |
| Urgencia y umbral de 5 días (criterio 9) | `app/domain/entities/tender_milestone.py` (`_DIAS_DESTACADO`) |
| Extracción automática al subir (criterio 1) | `UploadTenderChatDocumentUseCase` + `infrastructure/services/milestone_extraction_background.py` |
| Recordatorios (criterio 10) | `set_milestone_reminder.py`, `send_milestone_reminders.py` + `NotificationScheduler.start_reminder_loop` |
| Frontend | `src/features/tender-milestones/`, ruta `/calendario/callback/[provider]` |

- **Hitos oficiales**: publicación y cierre se toman de la licitación y se guardan al
  consultar, para que tengan id y se puedan sincronizar.
- **Extracción**: cada documento que el usuario subió al asistente se envía **por separado**
  a Gemini, junto con las fechas oficiales como referencia para resolver fechas relativas
  ("el día 20"). La respuesta es JSON con esquema; cada fecha se valida (`YYYY-MM-DD` y
  `HH:MM` estrictos) y se convierte de hora de Chile a UTC. Las inválidas se descartan y se
  informa cuántas. Si Gemini falla, quedan igual los hitos oficiales.
  - **Reintentos**: hasta 3 intentos (esperas de 2 y 4 s) ante 429, 5xx, timeout o una
    respuesta 200 sin contenido utilizable (`RECITATION`, `SAFETY`, JSON cortado). El
    `finishReason` queda en el log. Un 400 (p. ej. llave inválida) no se reintenta.
  - **Una sola lectura por base**: `tender_milestone_document` registra las bases ya leídas
    (se borra en cascada con el documento). Releer las mismas bases daba títulos o fechas
    algo distintos y la tabla terminaba con hitos duplicados o perdidos.
  - **Sin mezclar orígenes**: publicación y cierre se fusionan solo contra las filas
    oficiales, y la IA no agrega hitos de esos dos tipos. Antes un hito de la IA con el
    título del cierre se quedaba con el id del oficial y la fila cambiaba de origen en cada
    consulta. La consulta repara lo que eso dejó (filas oficiales repetidas, cierres de la
    IA), sin tocar lo sincronizado.
  - **Dentro de una base**, un mismo hito se reconoce por tipo y día (en Chile) y luego por
    título, así los repetidos con otro nombre quedan en una sola fila.
- **Extracción automática**: subir un documento al asistente agenda la extracción en una
  tarea de asyncio con sesión propia; la subida no espera a Gemini. Varias subidas seguidas
  se agrupan (como máximo una pasada más al terminar la que está en curso), y la
  extracción manual comparte el candado por usuario y licitación, así nunca corren dos a la
  vez. El estado (`extraction_status`: `idle`, `running`, `failed`) vive en memoria —asume
  una sola instancia de la API, como las exportaciones de la HdU 19— y el frontend
  consulta cada 4 s mientras dice `running`. Si la API se reinicia a mitad de camino, la
  extracción se pierde y se reintenta con el botón.
- **Sincronización**: el token se refresca antes de vencer (Microsoft además entrega un
  refresh token nuevo en cada refresco, que reemplaza al anterior); si el proveedor lo
  rechaza, se refresca una vez y se reintenta; si el refresh fue revocado, la conexión queda marcada y
  el frontend lleva a reconectar. Un hito que falla no detiene a los demás: la respuesta
  informa el resultado por hito y el reintento reenvía solo los fallidos.
- **Cambios de fecha**: cada `MILESTONE_REFRESH_INTERVAL_SECONDS` se revisan solo las
  licitaciones **abiertas** que alguien tiene sincronizadas. Se refrescan con la misma
  ingesta de siempre (SQL y Qdrant quedan alineados) y se comparan publicación y cierre.
  Si cambiaron: se actualizan los hitos oficiales, el evento en el calendario (Google u
  Outlook) de cada usuario vinculado, y se deja un aviso `date_changed` con correo inmediato (aunque el usuario use
  resumen diario). Un nuevo cambio reemplaza el aviso y lo marca sin leer.

- **Recordatorios**: la anticipación se guarda en el hito (`reminder_days_before`). Cada hora
  un bucle busca los hitos cuya ventana ya empezó (`due_at - días <= ahora < due_at`) y que
  no se avisaron todavía, deja un aviso `milestone_reminder` —uno por licitación, con la
  lista de hitos— y encola el correo si el usuario lo tiene activado. `reminder_sent_at`
  evita el reenvío; cambiar la anticipación lo reabre.

> Los correos de "Fecha modificada" y de los recordatorios los despacha el bucle de entrega
> de las alertas (HdU 08), que solo corre con `RUN_NOTIFICATION_SCAN=true` — esa variable
> enciende también el bucle de recordatorios. Los avisos en `/alertas` aparecen igual.

## API y migraciones

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/tenders/{id}/milestones` | Hitos con urgencia, calendarios donde están sincronizados, `extraction_status` y `pending_documents_count` |
| `POST` | `/tenders/{id}/milestones/extract` | Lee con IA las bases pendientes del asistente; informa `failed_documents_count` |
| `POST` | `/tenders/{id}/milestones/sync` | Sincroniza `{provider, milestone_ids, default_time?}`; devuelve el resultado por hito |
| `PATCH` | `/tenders/{id}/milestones/{hito}/reminder` | Activa el recordatorio con `{days_before: 1\|3\|7}`, o lo apaga con `null` |
| `GET` | `/calendar/connections` | Una fila por calendario configurado con su estado de conexión (nunca devuelve tokens) |
| `POST` | `/calendar/{provider}/authorize` | `provider` = `google` u `outlook`. Guarda la sincronización pedida y devuelve la URL de autorización del proveedor |
| `POST` | `/calendar/{provider}/callback` | Valida el `state`, intercambia el código y guarda la conexión |
| `DELETE` | `/calendar/connections/{provider}` | Revoca el token en Google (Microsoft no lo permite) y borra la conexión |

Errores: 401 sin sesión · 404 licitación o hitos ajenos · 409 hay que (re)conectar el
calendario · 422 falta la hora por defecto o el cuerpo es inválido · 502 el proveedor de
calendario no respondió · 503 IA o calendario no disponibles/configurados.

Migraciones, todas compatibles hacia atrás y en una sola cabeza:

- `b16c4e1a7d20` (después de `a227c0150001`): tablas `tender_milestone`,
  `calendar_connection`, `calendar_oauth_state` y `calendar_event_link`.
- `c16d5f2a8b31`: `notification` gana `kind` (default `'match'`) y `payload`, `score` pasa a
  nullable y el unique pasa a `(user_id, tender_id, kind)`. El escaneo y el resumen diario
  de HdU 08 siguen mirando solo los avisos `match`. El downgrade borra los avisos
  `date_changed`, que no tienen score.
- `d27a9c3f1b84`: `tender_milestone` gana `reminder_days_before` y `reminder_sent_at`, ambas
  nullable, más el índice parcial que usa el bucle de recordatorios.
- `b16e7a2c9d40` (después de `b3c2d1e0f9a8`): tabla `tender_milestone_document`, las bases ya
  leídas por la extracción (PK y FK a `tender_chat_documents` con borrado en cascada).

## Seguridad (criterio 8)

- Tokens de Google y de Outlook cifrados con Fernet (AES + HMAC) en `calendar_connection`;
  en el dominio viajan como `SecretStr`, así que no se filtran en logs ni en respuestas.
- El `state` de OAuth es aleatorio (32 bytes), se guarda solo su SHA-256, vence a los 10
  minutos, está ligado al usuario y se consume con `DELETE … RETURNING` (un solo uso).
- Permisos mínimos:
  - **Google:** `calendar.events` y `email`.
  - **Outlook:** `Calendars.ReadWrite`, `User.Read`, `offline_access` y `email`; Graph no
    tiene un permiso más acotado para crear eventos.
  - Si el usuario no concede el de calendario, la conexión se rechaza con un mensaje claro.
- Desconectar:
  - **Google:** revoca el token antes de borrarlo.
  - **Outlook:** Microsoft no permite revocar un token suelto, así que se borra la conexión y
    el permiso se quita en la cuenta Microsoft (ver Limitaciones).
- El prompt de extracción trata los documentos como datos e ignora instrucciones que
  traigan.

## Verificación por criterio

Cada criterio va con su texto literal de la HdU, los tests que lo cubren y cómo probarlo a
mano. Las pruebas manuales suponen la app levantada con la configuración de arriba.

### Criterio 1 — Extracción de hitos con IA

> Dado que el sistema procesa los documentos de bases de una licitación, cuando el motor de
> IA identifica párrafos que contienen fechas límite, entregas o visitas técnicas, entonces
> el sistema extrae estos hitos y los organiza en una tabla de eventos dentro de la
> plataforma.

**Automatizada:** `test_extract_tender_milestones.py`,
`test_gemini_milestone_extraction_service.py`, `test_milestone_extraction_background.py`,
`test_upload_tender_chat_document_use_case.py`, `test_get_tender_milestones.py`,
`test_milestone_document_repository.py` (integración), `MilestonesSection.test.tsx`,
`useTenderMilestones.test.ts`, `useTenderDocuments.test.ts` y `TenderDetailView.test.tsx`.

**A mano** (con una `GEMINI_API_KEY` real):
1. En el detalle de una licitación, subir unas bases (PDF) en el asistente, sin pulsar nada
   más.
2. La tabla muestra "La IA está leyendo las bases que subiste…" y luego los hitos, cada uno
   con **Ver párrafo de las bases**. El cierre no aparece duplicado.
3. Recargar: la tabla no cambia y **Extraer hitos de las bases** queda desactivado.
4. Subir otra base: solo se agregan sus hitos. Eliminarla en el asistente: sus hitos se van.

### Criterio 2 — "Sincronizar con mi calendario" lleva a autenticarse

> Dado que el representante de empresa revisa los hitos de una licitación, cuando hace clic
> en "Sincronizar con mi calendario", entonces el sistema lo redirige a la autenticación de
> su proveedor externo (Google Calendar u Outlook) para añadir los eventos seleccionados.

**Automatizada:** `test_calendar_authorization.py`, `test_outlook_calendar_client.py`
(URL de autorización), `test_calendar_providers_builder.py`, `test_config_microsoft_calendar.py`,
`useCalendarSync.test.ts` (redirige a Google y a Microsoft), `calendarReturn.test.ts`,
`CalendarOAuthCallback.test.tsx`, `CalendarSyncPanel.test.tsx` y `MilestonesSection.test.tsx`
(menú con los dos calendarios).

**A mano:**
1. Sin calendario conectado, elegir uno o más hitos y pulsar **Sincronizar con mi
   calendario**.
2. Con los dos configurados, elegir **Google Calendar** en el menú. Lleva a la pantalla de
   Google; al aceptar, vuelve a la ficha y los hitos quedan **En Google Calendar**.
3. Repetir eligiendo **Outlook Calendar**: lleva a Microsoft y, al volver, quedan **En
   Outlook Calendar**.

### Criterio 3 — Contenido del evento

> Dado que el representante de empresa sincroniza uno o más hitos, cuando estos aparecen en
> su calendario personal, entonces cada evento contiene el título de la licitación, la fecha
> exacta y un enlace de retorno a la ficha de la licitación en la plataforma (Chiripa).

**Automatizada:** `test_sync_milestones.py` (título "Hito — Licitación" y enlace
`/matches/<id>`), `test_google_calendar_client.py` y `test_outlook_calendar_client.py`
(cuerpo del evento enviado a cada proveedor).

**A mano:** abrir el evento creado en Google Calendar y en Outlook. Revisar que tenga:
- el título con el nombre de la licitación;
- la fecha y hora del hito;
- en la descripción, "Ver la licitación en Chiripa: …"; el enlace abre la ficha.

### Criterio 4 — Cambio de fechas en Mercado Público

> Dado que una licitación sufre una modificación en sus fechas oficiales en Mercado Público,
> cuando el sistema detecta este cambio, entonces actualiza automáticamente el evento en el
> calendario del usuario y le envía una notificación de "Fecha modificada".

**Automatizada:** `test_refresh_synced_tender_dates.py` (Google y Outlook),
`test_dispatch_pending_deliveries.py` y `NotificationPanel.test.tsx`.

**A mano:** Mercado Público no cambia fechas a pedido, así que se simula corriendo la fecha
en la base local. El refresco la compara con la oficial y la ve "movida".
1. En `.env`: `MILESTONE_REFRESH_INTERVAL_SECONDS=60` y `RUN_NOTIFICATION_SCAN=true`;
   recrear el contenedor `api`.
2. Elegir una licitación **abierta** y correr su cierre un día, contra la base local
   (Postgres de Supabase en el puerto 54322):
   ```sql
   UPDATE tender SET closing_at = closing_at - interval '1 day' WHERE code = '<código>';
   ```
3. Abrir su detalle (los hitos oficiales toman la fecha corrida), elegir **Cierre de
   recepción de ofertas** y sincronizarlo. En el calendario (Google u Outlook) el evento
   queda un día antes.
4. En el minuto siguiente el refresco trae la fecha real. El evento vuelve a su día, aparece
   **Fecha modificada** en `/alertas` y el correo llega a Mailpit (http://localhost:54324).

### Criterio 5 — Fechas normalizadas

> Dado que el documento técnico presenta las fechas en formatos variados (ej. "a las 15:00
> del día 20"), cuando el sistema procesa el documento, entonces el motor de IA normaliza
> todas las fechas a un formato estándar internacional para garantizar que la
> sincronización no falle.

**Automatizada:** `test_milestone_date_normalizer.py` (`YYYY-MM-DD` / `HH:MM` estrictos, hora
de Chile → UTC, fechas imposibles descartadas) y `test_extract_tender_milestones.py`
("a las 10:00 del día 10" queda en `2026-10-10T13:00Z`).

**A mano:** con unas bases que digan, por ejemplo, "a las 15:00 del día 20", el hito aparece
con fecha y hora completas en la tabla. Los eventos se crean sin errores.

### Criterio 6 — Falla del proveedor y reintento

> Dado que el sistema intenta comunicarse con Google Calendar o Outlook, cuando el servicio
> externo no responde o rechaza la petición, entonces el sistema notifica al usuario que
> "La sincronización no pudo completarse" y permite reintentar la acción manualmente.

**Automatizada:** `test_sync_milestones.py` (fallo parcial, refresh revocado),
`test_google_calendar_client.py` y `test_outlook_calendar_client.py` (5xx, timeout, 401),
`useCalendarSync.test.ts`, `SyncErrorAlert.test.tsx`, `CalendarSyncPanel.test.tsx` y
`MilestonesSection.test.tsx` ("La sincronización no pudo completarse." + **Reintentar**).

**A mano** (rechazo):
1. Quitar el acceso de la app:
   - **Google:** en [myaccount.google.com/permissions](https://myaccount.google.com/permissions);
   - **Outlook:** en [account.live.com/consent](https://account.live.com/consent/Manage) (cuentas
     personales) o [myapps.microsoft.com](https://myapps.microsoft.com) (de trabajo).
2. Volver a sincronizar. El refresh es rechazado y aparece el error con **Reconectar Google
   Calendar** / **Reconectar Outlook Calendar**, que lleva a autorizar de nuevo.

La caída del proveedor (5xx, timeout) se cubre con los tests: muestra "La sincronización no
pudo completarse" con **Reintentar**, que reenvía solo los hitos fallidos.

### Criterio 7 — Hito sin hora

> Dado que el sistema extrae un hito pero no logra identificar la hora exacta, cuando el
> usuario solicita sincronizar, entonces el sistema le pide confirmar una hora por defecto
> (ej. inicio de jornada) antes de crear el evento, evitando fechas incompletas.

**Automatizada:** `test_sync_milestones.py` (sin hora no crea el evento), `test_tender_milestone.py`
(`con_hora`), `DefaultTimeDialog.test.tsx` y `MilestonesSection.test.tsx`.

**A mano:**
1. Elegir un hito marcado "Sin hora exacta" y pulsar **Sincronizar con mi calendario**.
2. Antes de crear nada aparece el diálogo con 09:00 propuesto. Al confirmar, el evento queda a
   esa hora.

### Criterio 8 — Tokens cifrados

> Dado que el representante de empresa conecta su cuenta de calendario, cuando el sistema
> almacena los tokens de acceso, entonces estos se guardan cifrados en la base de datos y
> nunca se comparten con terceros.

**Automatizada:**
- `test_fernet_token_cipher.py`;
- `test_milestone_calendar_repositories.py` (integración: la columna no tiene el token en
  texto plano);
- `test_calendar_router.py` (la respuesta nunca trae tokens);
- `test_outlook_calendar_client.py` (los logs no registran códigos, secretos ni tokens).

**A mano:** con Google y Outlook conectados, consultar la base local:
```sql
SELECT provider, left(access_token_encrypted, 20) FROM calendar_connection;
```
Los valores empiezan con `gAAAA` (formato Fernet), no con el token real.

### Criterio 9 — Destacar plazos de 5 días o menos

> Dado que la tabla de hitos de una licitación contiene eventos próximos, cuando a un hito le
> quedan 5 días o menos para su vencimiento, entonces el sistema lo destaca visualmente (ej.
> color o ícono de alerta) dentro de la tabla.

**Automatizada:** `test_tender_milestone.py` (bordes de `MilestoneUrgency` por día de
calendario en Chile), `test_get_tender_milestones.py`, `milestoneFormat.test.ts` y
`MilestonesSection.test.tsx`.

**A mano:** correr el cierre de una licitación abierta contra la base local y recargar su
detalle.
```sql
UPDATE tender SET closing_at = now() + interval '4 days' WHERE code = '<código>';
```
El plazo queda **rojo** y entre exclamaciones ("¡Vence en 4 días!"). Con `interval '8 days'`
queda gris ("Vence en 8 días"). Se cuentan días de calendario en hora de Chile: lo que vence
dentro de 5 días se destaca a cualquier hora, y a 6 días ya no.

### Criterio 10 — Recordatorios

> Dado un representante de empresa visualizando un hito, cuando activa la opción de
> recordatorio, entonces el sistema le notifica (dentro de la plataforma y/o por correo) con
> una anticipación configurable antes del vencimiento del hito.

**Automatizada:** `test_send_milestone_reminders.py`, `test_set_milestone_reminder.py`,
`tests/unit/test_milestones_router.py::TestRecordatorio`,
`test_milestone_calendar_repositories.py::TestRecordatoriosDeHitos`,
`test_dispatch_pending_deliveries.py`, `MilestonesSection.test.tsx` y
`NotificationPanel.test.tsx`.

**A mano:**
1. En `.env`: `RUN_NOTIFICATION_SCAN=true`; recrear el contenedor `api`.
2. En el detalle de la licitación, elegir **1 día antes** en la columna *Recordatorio* de un
   hito **extraído por IA**. El selector queda con ese valor y sobrevive a recargar la
   página. Los hitos oficiales se recalculan desde la licitación al abrir la ficha; para
   uno de ellos hay que cambiar `tender.closing_at`.
3. Para no esperar, adelantar el vencimiento del hito dentro de la ventana:
   ```sql
   UPDATE tender_milestone SET due_at = now() + interval '12 hours'
   WHERE id = '<id del hito>';
   ```
4. El bucle corre cada hora; para verlo en el momento, reiniciar `api` (`docker compose
   restart api`). Al pasar, aparece **Recordatorio** en `/alertas` con el hito y su fecha, y
   el correo llega a Mailpit (http://localhost:54324).
5. Comprobar que no se repite: en la vuelta siguiente el hito ya tiene `reminder_sent_at` y
   no se vuelve a avisar. Cambiar la anticipación en el selector lo reabre.

## Verificación reproducible

Backend (sin Python 3.12 local, en un contenedor desde `monorepo/backend`, en Git Bash).
Se omite `sentence-transformers`, que el conftest reemplaza y arrastraría torch:

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/app" -w /app -e POSTGRES_PASSWORD=x -e MERCADO_PUBLICO_API_KEY=x -e GEMINI_API_KEY=x -e GEMINI_MODEL=x python:3.12-slim sh -c "cat requirements.txt requirements-test.txt | grep -v -e sentence-transformers -e '^-r' > /tmp/r.txt && pip install -q -r /tmp/r.txt huggingface_hub && pytest -q -m 'not integration and not network'"
```

Con un Postgres disponible se agregan `tests/integration/test_milestone_calendar_repositories.py`,
`tests/integration/test_milestone_document_repository.py` y `tests/integration/test_migraciones.py`.
`alembic heads` debe mostrar una sola línea: hoy, `b16e7a2c9d40`.

Los tests `test_config_google_calendar.py` y `test_config_microsoft_calendar.py` construyen la
configuración sin `.env`. Si el contenedor ya trae `TOKEN_ENCRYPTION_KEY` o las credenciales
de calendario como variables de entorno, se corren sin ellas:
`env -u TOKEN_ENCRYPTION_KEY -u GOOGLE_CALENDAR_CLIENT_ID -u GOOGLE_CALENDAR_CLIENT_SECRET pytest tests/unit/test_config_*_calendar.py`.

Frontend:

```bash
pnpm test
pnpm exec tsc --noEmit
pnpm lint
```

## Limitaciones

- **Outlook:**
  - Graph no tiene un permiso más acotado que `Calendars.ReadWrite` para crear eventos.
  - Admite un solo recordatorio por evento: se usa el más anticipado (1 día), en vez de los
    dos que crea Google (1 día y 1 hora).
  - **Desconectar** borra la conexión en Chiripa, pero Microsoft no permite revocar el token
    desde la app. El permiso se quita en la cuenta Microsoft: account.live.com/consent para
    cuentas personales, myapps.microsoft.com para las de trabajo.
  - El secreto de la app vence (180 días o lo elegido): hay que renovarlo antes en Azure y
    en las variables.
- Mientras la app de Google esté en **Testing**, los refresh tokens vencen a los 7 días: la
  app lo detecta y pide reconectar. En producción hay que publicar (y verificar) la app.
- Los documentos los sube el usuario al asistente: la API de Compra Ágil no entrega las
  bases. Los hitos extraídos son por usuario, como los documentos.
- Solo se vigilan en Mercado Público la publicación y el cierre; los hitos extraídos por IA
  no tienen fuente oficial con la que compararse.
- Como los demás loops, el refresco asume **una sola instancia** de la API.
