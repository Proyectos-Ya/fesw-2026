# Plan técnico: HU-032 — Postular en Mercado Público desde Chiripa

**Issue**: Refs #318 · **Rama**: `318-hu-32-postular-mercado-publico` desde `develop` (`a23fc34f`)  
**Estado**: Aceptado / En implementación · **Alcance**: código + publicación en **Chrome Web Store** y **Firefox AMO**  
**Tareas atómicas**: [task.md](./task.md)

---

## 0. Resumen y hallazgos en el código

### 0.1 Hallazgos verificados en la extensión y repositorio

| # | Hallazgo | Dónde | Impacto si no se corrige |
|---|---|---|---|
| H1 | El manifiesto apunta a `icons/icon-{16,48,128}.png`, pero **no existe `public/`** | `monorepo/extension/wxt.config.ts` | Las dos stores exigen ícono de 128 px: rechazo directo |
| H2 | Se declara el permiso `cookies` y ningún archivo lo usa | `monorepo/extension/wxt.config.ts` | CWS rechaza por permisos innecesarios |
| H3 | `localhost:3000` y `localhost:8000` están en los permisos y `matches` de producción | `monorepo/extension/wxt.config.ts`, `bridge.content.ts` | Bandera roja en la revisión y superficie de ataque |
| H4 | El bridge solo se inyecta en `*.chiripa.cl` y `*.proyectosya.cl`. El frontend desplegado vive en `*.vercel.app` | `bridge.content.ts` | En producción la web nunca detecta la extensión (CA2 fallaría) |
| H5 | No hay `browser_specific_settings.gecko.id` ni `data_collection_permissions` | `monorepo/extension/wxt.config.ts` | AMO rechaza la subida de MV3 sin id y exige declarar recolección de datos |
| H6 | La versión `"0.1.0"` está escrita a mano en 4 lugares | `background.ts`, `bridge.content.ts`, `App.tsx`, tests | Cada store exige versión estrictamente mayor; PONG mentiría |
| H7 | `JobRunner.processJob` reporta `completed` sin descargar nada, y `chrome.idle` se usa sin permiso `idle` | `job-runner.ts` | Ensucia la cola del plan 233. Se apaga por flag (`EXTENSION_MAX_DAILY_FETCHES=0`) |
| H8 | Vitest corre sin entorno DOM (no hay `vitest.config` ni `happy-dom`) | `monorepo/extension` | Sin DOM no se puede probar el adaptador del formulario (CA5 a CA8) |
| H9 | CI no corre la extensión | `.github/workflows/ci.yml` | Tests de CA4 a CA8 no protegerían nada en CI |
| H10 | `mp.content.ts` arma el badge con `innerHTML` | `mp.content.ts` | Mala práctica en página de terceros. La UI nueva va en Shadow DOM y usa solo `textContent` |
| H11 | La cotización de Chiripa son "materiales" editables, no un precio por ítem de la licitación | `quotation.ts` | Mercado Público pide un valor por ítem: hace falta una regla de cruce explícita (§2.4) |
| H12 | Tras instalar la extensión, Chrome no inyecta content scripts en pestañas ya abiertas | Comportamiento Chromium | Sin recargar la página, "volver a comprobar" fallaría siempre |
| H13 | No se conoce el DOM ni la URL del formulario de cotización de proveedor sin sesión | — | Requiere captura con cuenta real en el spike F1 |

### 0.2 Decisiones de diseño adoptadas

1. **La extensión abre la pestaña de Mercado Público** con `tabs.create({ active: false })`, que no requiere permiso. Evita bloqueadores de popups, mantiene al usuario en Chiripa viendo la confirmación (CA3) y recuerda el tab id.
2. **Postular no exige vincular la extensión** (pairing). Los datos viajan de la web a la extensión y de ahí al formulario localmente en el navegador. No depende de tokens de sesión que expiran.
3. **No se pide permiso sobre ClaveÚnica ni sobre ningún dominio de login.** La extensión ni siquiera puede ejecutarse donde se escribe la contraseña (CA5 garantizado por diseño y verificado por test estático).
4. **El cruce cotización→ítems se hace en el backend** con regla determinista y probada (§2.4). En el diálogo de confirmación los precios son editables.
5. **El detalle de la oferta tiene un tope de 255 caracteres que bloquea la confirmación.** Mercado Público corta el texto en silencio por `maxlength`.
6. **Despliegue gradual**: `EXTENSION_POSTULATION_ENABLED` arranca en `False` en Railway y se enciende con ambas stores aprobadas. Funciona como kill switch operativo.

---

## 1. Decisiones por Criterio de Aceptación (CA)

- **CA1**: El botón "Postular en Mercado Público" se ubica en `ProposalDraftViewer.tsx`. Se visualiza si `capabilities.postulation_enabled` es verdadero. Deshabilitado con tooltip explicativo si la licitación cerró o si el rol carece de `generate_proposal`.
- **CA2**: Al pulsar el botón, Chiripa envía un `PING` con 1 s de timeout. Sin `PONG`: se despliega `ExtensionRequiredDialog` con enlace adaptado según navegador (Chrome/Edge a CWS, Firefox a AMO; Safari/otros: aviso de navegador compatible) y botón "Ya la instalé — recargar" (`location.reload()`).
- **CA3**: Con `PONG`: se envía `OPEN_POSTULATION` (la extensión abre pestaña inactiva de Mercado Público). En paralelo, la web obtiene `GET …/postulation-package` y abre `PostulationConfirmDialog` en Chiripa.
- **CA4**: Al confirmar en Chiripa, se junta el `.docx` técnico (si existe y está seleccionado) con los anexos seleccionados, se envía `CONFIRM_POSTULATION` y se enfoca la pestaña de Mercado Público. La extensión almacena el paquete con TTL de 30 min (IndexedDB para binarios, `storage.local` para metadatos).
- **CA5**: El content script en Mercado Público detecta la página de ingreso, **no registra listeners en inputs**, jamás lee `input[type=password]` ni cookies, y espera con `MutationObserver` o cambio de URL a que el usuario complete su inicio de sesión por cuenta propia.
- **CA6**: En el formulario: valida que el código de la licitación coincida. Si detecta el RUT de la sesión y no coincide con la empresa de Chiripa, no carga precios y alerta. Si coincide, autocompleta: precios por ítem, impuesto, vigencia, detalle, nombre y adjuntos vía `DataTransfer`.
- **CA7**: Panel en Shadow DOM con conteo y listado de campos, botones "Ir al campo", "Volver a cargar datos", "Quitar resaltado" y "Descargar anexos". Campos marcados con `data-chiripa-field-status="filled"` (verde) o `"incomplete"` (ámbar) con soporte de accesibilidad.
- **CA8**: El adaptador carece absolutamente de llamadas a `submit`, `requestSubmit` o clicks automáticos sobre botones de envío, ni marca la Declaración Jurada. El envío final es 100% manual por el usuario.

---

## 2. Arquitectura de Integración

### 2.1 Protocolo Web ↔ Extensión
- Filtro estricto por `event.origin === location.origin`, `target: "CHIRIPA_EXTENSION"` y `nonce` UUID. Respuestas con `target: "CHIRIPA_WEB"`.
- `PING` → `PONG { version, features: ["postulation"], mp_access: boolean }`.
- `OPEN_POSTULATION` → `POSTULATION_TAB_OPENED { ok }`.
- `CONFIRM_POSTULATION` → Stream en trozos de 1 MiB vía `runtime.connect` hacia background para evitar limitaciones de serialización de `File`/`ArrayBuffer`.
- Almacenamiento local en extensión: IndexedDB para binarios (`File[]`), `chrome.storage.local` para metadatos, con TTL de 30 minutos.

### 2.2 Endpoint Backend: `GET /tenders/{tender_id}/proposal/postulation-package`
- Use Case: `BuildPostulationPackageUseCase`.
- Realiza el matching determinista entre ítems de la licitación y cotizaciones guardadas.
- Valida permisos de usuario y estado abierto de la licitación.
- Retorna datos de empresa, ítems con precio sugerido, advertencias, detalles y documentos requeridos.
- Controlado por el feature flag `extension_postulation_enabled`.

---

## 3. Matriz de Pruebas TDD (mínimo 1 por CA)

| CA | Tipo | Descripción de la prueba |
|---|---|---|
| CA1 | Unitario FE | `ProposalDraftViewer.test.tsx`: botón visible en borrador con flag activo, deshabilitado si licitación cerró o rol sin permisos |
| CA2 | Unitario FE | `PostularEnMercadoPublicoButton.test.tsx`: sin extensión despliega `ExtensionRequiredDialog` con enlaces dinámicos según navegador |
| CA3 | Integración BE/EXT | `test_build_postulation_package.py` valida paquete; `postulation-coordinator.test.ts` valida apertura de pestaña inactiva |
| CA4 | Unitario FE/EXT | `PostulationConfirmDialog.test.tsx` valida envío de payload; `postulation-store.test.ts` valida persistencia y TTL |
| CA5 | Unitario EXT | `mp-postulation-adapter.test.ts` + `static-guards.test.ts`: no lectura de passwords ni cookies en página de login |
| CA6 | Unitario EXT | `mp-postulation-adapter.test.ts`: autocompletado en formulario con sesión, bloqueo por RUT discrepante |
| CA7 | Unitario EXT | `postulation-panel.test.ts` + `mp-postulation-adapter.test.ts`: asignación de estados verde (`filled`) y ámbar (`incomplete`) |
| CA8 | Test Estático EXT | `static-guards.test.ts`: aserción estática de ausencia de `.submit()`, `requestSubmit()` o clicks en botones de envío |
