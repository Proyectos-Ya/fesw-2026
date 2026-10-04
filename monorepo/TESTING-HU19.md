# HdU 19 — Compartir y exportar el detalle de una licitación (enlace, PDF y Excel)

Rama `feat/HU-19-compartir-exportar-licitaciones`, sobre `develop` (`2d826b0`).

> Como representante de empresa, necesito compartir el detalle, análisis de compatibilidad y
> justificaciones de una licitación mediante un enlace web temporal, o exportarlo en formato
> PDF o Excel, para facilitar la toma de decisiones colaborativa con mi equipo y contar con
> respaldos formales para la gestión comercial, sin que los colaboradores externos requieran
> una cuenta registrada en la plataforma.

## Uso

En la ficha de una licitación (`/matches/{id}`):

1. **Compartir** (ícono junto a *Guardar*): **Generar enlace** crea una URL válida por
   7 días. Se muestra con **Copiar** una sola vez; después la lista de *Enlaces vigentes*
   solo informa cuándo se creó y cuándo vence, con **Revocar** (pide confirmación).
2. Quien abre la URL (`/compartido/{token}`) ve, sin cuenta, los datos de la licitación, el
   puntaje, la recomendación, la justificación y los ítems. Si el enlace venció o fue
   revocado, se lo redirige a **Enlace caducado** (`/enlace-caducado`).
3. **Exportar a PDF**: genera y descarga un PDF con los datos generales, el análisis de
   compatibilidad con su justificación, las fechas clave, los ítems y la cotización de la
   empresa con su total.
4. **Exportar a Excel**: primero deja marcar o desmarcar las secciones (datos generales,
   montos y cotización, datos técnicos, fechas clave, análisis de la IA). Cada sección es una
   hoja; los montos son números con formato de moneda y las fechas, fechas reales de Excel.
5. Si un archivo tarda más de 10 s, se avisa *"Tu archivo se está generando en segundo
   plano. Te avisaremos por correo cuando esté listo para descargar"*. Mientras la ficha
   siga abierta se descarga sola al terminar; si no, el correo lleva a
   `/exportaciones/{id}`, que pide sesión y descarga el archivo.

Compartir y exportar usan la **empresa activa** del selector. Exige el permiso
`view_matches`, el mismo que ver la ficha.

## Configuración

| Variable | Default | Qué es |
|---|---|---|
| `EXPORT_INLINE_TIMEOUT_SECONDS` | `10` | Sobre este tiempo, la exportación pasa a segundo plano |
| `APP_BASE_URL` | `http://localhost:3000` | Base de la URL compartida y del enlace del correo |
| `SMTP_*` | los de la HdU 08 | El correo de "archivo listo" usa el mismo servidor que las alertas |

Dependencia nueva: `reportlab==4.5.1` (wheel puro, sin paquetes del sistema). **Reconstruir
la imagen** para que la traiga: `docker compose up -d --build api`.

El correo de "archivo listo" se envía directo, no por la cola de alertas: llega aunque
`RUN_NOTIFICATION_SCAN=false` o aunque el usuario tenga las alertas por correo apagadas.

## Cómo funciona

| Pieza | Dónde |
|---|---|
| Enlace temporal | `app/domain/entities/tender_share_link.py`, `app/application/use_cases/sharing/tender_sharing.py`, `app/infrastructure/routers/sharing.py` |
| Datos de la exportación | `app/application/use_cases/exports/export_snapshot.py`, `build_export_snapshot.py` |
| PDF y Excel | `app/infrastructure/services/exports/pdf_renderer.py`, `excel_renderer.py` |
| Segundo plano y correo | `export_tender.py`, `export_jobs.py`, `app/infrastructure/services/exports/background.py` |
| Frontend | `src/features/tender-sharing/`, `src/features/tender-export/`, rutas `/compartido/[token]`, `/enlace-caducado`, `/exportaciones/[jobId]` |

- **Token del enlace:** `secrets.token_urlsafe(32)`. En la base queda solo su SHA-256, así
  que quien lea la base no puede armar la URL; por lo mismo, la URL no se puede volver a
  mostrar después de creada.
- **La vista pública lee datos en vivo:** el puntaje y el análisis actuales de la empresa que
  compartió. **Nunca genera** un análisis: una inferencia pedida desde un enlace público la
  pagaría alguien que no la pidió. **No incluye la cotización**, que es información
  comercial; la historia pide detalle, análisis y justificaciones.
- **Exportar solo lee:** no calcula puntajes ni genera análisis. Si faltan, el archivo lo dice
  ("Sin análisis de compatibilidad", "Sin cotización registrada") en vez de omitirlo.
- **Fechas clave:** por ahora, publicación y cierre de Mercado Público
  (`key_dates_for` en `export_snapshot.py`). Es el único punto que cambia cuando los hitos
  extraídos por IA de la HU-16 lleguen a `develop`.
- **Segundo plano:** el render corre en un hilo aparte (`asyncio.to_thread`), porque la API
  atiende con un solo worker y un PDF en el event loop frenaría todas las demás peticiones.
  Se espera con `shield`, así que vencer el umbral no lo cancela: la tarea sigue y, al
  terminar, abre su propia sesión, guarda el archivo y manda el correo.
- **El archivo se guarda en Postgres** (`export_job.content`), no en disco: el disco del
  contenedor se pierde en cada despliegue. Pesa KB y se vacía a los 7 días.
- **Reinicios:** al arrancar, los trabajos que quedaron en proceso se marcan fallidos y se
  vacían los archivos vencidos. Al apagar se cancelan las tareas pendientes.

> Como los bucles de alertas, esto asume **una sola instancia** de la API: la tarea vive en
> la memoria del proceso.

## API y migraciones

| Método | Ruta | Sesión | Qué hace |
|---|---|---|---|
| `POST` | `/tenders/{id}/share-links` | Sí | Crea el enlace; es la única respuesta que trae la `url` |
| `GET` | `/tenders/{id}/share-links` | Sí | Enlaces vigentes de la licitación y la empresa activa |
| `DELETE` | `/tenders/{id}/share-links/{link}` | Sí | Revoca (quien lo creó o un admin) |
| `GET` | `/shared/{token}` | **No** | Vista pública; `Cache-Control: no-store`, `X-Robots-Tag: noindex` |
| `POST` | `/tenders/{id}/exports` | Sí | `{format: "pdf"\|"xlsx", sections?}` → 200 con el archivo, o 202 con `job_id` |
| `GET` | `/exports/{job}` | Sí | Estado del trabajo (solo su dueño) |
| `GET` | `/exports/{job}/file` | Sí | Descarga el archivo terminado (solo su dueño) |

Errores: 401 sin sesión · 403 sin permiso · 404 licitación, enlace o trabajo inexistente o
ajeno · 409 archivo todavía generándose · 410 enlace caducado o revocado, o archivo fallido
o vencido (cada uno con un `code`: `share_link_expired`, `share_link_revoked`,
`export_failed`, `export_expired`) · 422 formato o sección inválidos, o Excel sin secciones.

Migraciones, ambas solo agregan una tabla (compatibles hacia atrás) y en una sola cabeza:

- `e19a4c2b7d01` (después de `f1e2d3c4b5a6`): `tender_share_link`.
- `e19b7f3a2c04`: `export_job`.

Si la HU-16 se mergea antes, hay que repuntar el `down_revision` de `e19a4c2b7d01` a su
cabeza, como indica `AGENTS.md`, y comprobar con `alembic heads`.

## Seguridad

- En la base solo queda el hash del token; la URL no viaja en logs ni en la lista de enlaces.
- La vista pública no expone ids de la empresa ni del usuario, no se guarda en cachés ni se
  indexa, y la página no manda `Referer` al abrir la ficha de Mercado Público.
- A quien no puede revocar un enlace, o pide un trabajo ajeno, se le responde 404: no se
  entera de que existe.
- Todo texto de datos se escapa en el PDF (ReportLab interpreta etiquetas), en el HTML del
  correo, y en el Excel se guarda como texto aunque empiece con `=`, para que no se ejecute
  como fórmula al abrir la planilla.

## Verificación por criterio

| # | Criterio | Evidencia automatizada | Prueba manual |
|---|---|---|---|
| 1 | "Compartir" genera una URL única con vigencia de 7 días | `test_tender_share_link.py::TestEmision`, `test_tender_sharing.py::TestCrear`, `test_sharing_api.py`, `ShareDialog.test.tsx` | Ver abajo |
| 2 | El tercero ve el detalle sin iniciar sesión | `test_tender_sharing.py::TestAbrirSinSesion`, `test_sharing_router.py::TestVistaPublica`, `test_sharing_api.py`, `SharedTenderView.test.tsx`, `proxy.test.ts` | Abrir la URL en una ventana privada |
| 3 | PDF profesional con análisis, justificaciones y cotizaciones | `test_pdf_export_renderer.py`, `test_build_export_snapshot.py`, `test_exports_api.py`, `ExportActions.test.tsx` | Abrir el PDF descargado |
| 4 | Excel con hitos, montos y datos técnicos | `test_excel_export_renderer.py::TestContenido`, `test_exports_api.py` | Abrir el `.xlsx` y ordenar/sumar |
| 5 | Marcar o desmarcar secciones antes de generar | `test_excel_export_renderer.py::TestHojas`, `test_export_tender.py`, `ExcelExportDialog.test.tsx` | Desmarcar *Análisis de la IA* |
| 6 | A los 7 días, acceso denegado y página "Enlace caducado" | `test_tender_share_link.py::TestEstado`, `test_tender_sharing.py`, `test_sharing_router.py`, `SharedTenderView.test.tsx`, `ExpiredLinkNotice.test.tsx` | Ver abajo |
| 7 | "Revocar" invalida la URL al instante | `test_tender_sharing.py::TestRevocar`, `test_sharing_api.py`, `ShareDialog.test.tsx` | Revocar y recargar la URL |
| 8 | PDF > 10 s: aviso de segundo plano y correo al estar listo | `test_export_tender.py::TestLento`, `test_export_jobs.py`, `test_export_background.py`, `test_exports_router.py`, `test_exports_api.py`, `useTenderExport.test.ts`, `ExportDownloadView.test.tsx` | Ver abajo |
| 9 | Lo mismo para el Excel | Los mismos que el 8 (`test_un_excel_lento_tambien`, `test_el_correo_del_excel_dice_excel`) | Ver abajo, con Excel |

### Preparar la base local

Si la base local tiene aplicadas las migraciones de la HU-16 (`c16d5f2a8b31` o
`d27a9c3f1b84`), esta rama no las conoce y `alembic upgrade head` —que el compose corre al
arrancar— falla con *Can't locate revision*. Se arregla sin borrar datos (las tablas de la
HU-16 quedan intactas), desde `monorepo/backend`:

```bash
docker compose run --rm api alembic stamp --purge f1e2d3c4b5a6
docker compose up -d --build api
```

Al volver a la rama de la HU-16, lo inverso: `alembic stamp --purge c16d5f2a8b31` y
`alembic upgrade head`.

### Criterios 1, 2 y 7 a mano

1. En la ficha de una licitación, **Compartir → Generar enlace** y **Copiar**. Vence en 7 días.
2. Pegar la URL en una **ventana privada** (sin sesión): se ve la licitación y su análisis.
3. Volver a *Compartir*, **Revocar → Sí, revocar** y recargar la ventana privada: redirige a
   **Enlace caducado** con el mensaje de que fue revocado.

### Criterio 6 a mano

Nadie espera 7 días: se adelanta el vencimiento del enlace más reciente (Postgres local en el
puerto 54322) y se recarga la URL en la ventana privada.

```sql
UPDATE tender_share_link SET expires_at = now() - interval '1 minute'
WHERE id = (SELECT id FROM tender_share_link ORDER BY created_at DESC LIMIT 1);
```

### Criterios 8 y 9 a mano

1. En `.env`: `EXPORT_INLINE_TIMEOUT_SECONDS=0` (cualquier generación "tarda demasiado");
   `docker compose up -d --force-recreate api`, porque el reinicio simple no relee el `.env`.
2. **Exportar a PDF**: aparece el aviso de segundo plano y, a los segundos, se descarga solo.
3. En Mailpit (http://localhost:54324) llega *"Tu PDF está listo"*; su botón lleva a
   `/exportaciones/{id}`, que descarga el archivo.
4. Repetir con **Exportar a Excel** (criterio 9).
5. Devolver `EXPORT_INLINE_TIMEOUT_SECONDS` a su valor y recrear el contenedor.

## Verificación reproducible

Backend, con el contenedor `api` arriba (desde `monorepo/backend`):

```bash
docker compose exec -T api python -m pytest -q -m "not integration and not network"
```

```bash
docker compose exec -T api python -m pytest -q -m integration tests/integration/test_tender_share_link_repository.py tests/integration/test_export_job_repository.py tests/integration/test_migraciones.py
```

```bash
docker compose exec -T api alembic heads
```

`alembic heads` debe mostrar solo `e19b7f3a2c04`. `test_migraciones.py` equivale a
`alembic check`.

Frontend (desde `monorepo/frontend`):

```bash
corepack pnpm test
```

```bash
corepack pnpm exec tsc --noEmit
```

```bash
corepack pnpm lint
```

## Limitaciones

- **Hitos:** mientras la HU-16 no esté en `develop`, la hoja de fechas clave trae solo la
  publicación y el cierre oficiales.
- **Una sola instancia:** con dos réplicas, un trabajo iniciado en una no lo termina la otra.
  Si la API se reinicia durante una generación, el trabajo queda fallido y hay que volver a
  exportar.
- **La URL del enlace se ve una vez.** Si se pierde, se genera otra; la anterior se puede
  revocar desde la lista.
- **El PDF va completo:** la selección de secciones es del Excel, como pide el criterio 5.
