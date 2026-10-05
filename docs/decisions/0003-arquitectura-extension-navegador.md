# ADR-0003: Arquitectura de la Extensión de Navegador y Adaptador de Mercado Público

* **Fecha**: 2026-10-04  
* **Estado**: Propuesto  
* **Autores**: Equipo Chiripa  

---

## 1. Contexto

La indexación de las bases y anexos oficiales de Mercado Público (documentos de Compra Ágil y licitaciones) es fundamental para alimentar el asistente RAG (Decisión 5) y enriquecer el matching semántico con IA (Spike 2). Sin embargo, la API v2 de ChileCompra no sirve los archivos binarios; únicamente expone metadatos elementales (`documentos: [{id, nombre}]`).

Los archivos binarios están disponibles públicamente en la SPA de Mercado Público (`buscador.mercadopublico.cl/ficha?code=<COT>`) y sus endpoints asociados (`adjunto.mercadopublico.cl/.../adjuntos-compra-agil/`). Para capturar estos archivos sin incurrir en costos exorbitantes de clusters de scraping headless en servidores backend, se plantea que la comunidad de usuarios de Chiripa colabore mediante una **extensión de navegador** oficial.

Adicionalmente, el diseño técnico debe anticipar la Historia de Usuario 20 (Plan 230: Generación y postulación automatizada de ofertas), dejando la arquitectura preparada para interactuar con los portales de proveedores de Mercado Público en el futuro.

### Restricciones y desafíos:
1. **Multi-navegador y Manifest V3 (MV3):** Los usuarios utilizan Google Chrome, Microsoft Edge y Mozilla Firefox. Firefox MV3 no admite `externally_connectable` con páginas web estándar y difiere en el modelo de ejecución de background scripts frente a los Service Workers de Chromium.
2. **Seguridad y privacidad (Zero-Credential Leakage):** La extensión jamás debe solicitar ni almacenar contraseñas ni RUT de Mercado Público. El emparejamiento con Chiripa debe ser seguro y sin fricción.
3. **Resiliencia ante la SPA de Mercado Público:** La plataforma de ChileCompra está construida en Angular y carga datos de forma asíncrona; cualquier rediseño no debe romper el cliente en producción sin posibilidad de reacción inmediata.
4. **Almacenamiento y cuotas:** Las transferencias deben ir directo a Cloudflare R2 con validación criptográfica SHA-256 (`by-code`), sin saturar el ancho de banda del usuario ni la memoria del backend.

---

## 2. Decisión Tomada

Se adopta una **arquitectura basada en el framework WXT con bridge universal por Content Script, scraping reactivo mediante MutationObserver y cola pull distribuida** (Decisión 7 del Plan 233):

### 1. Framework WXT (`monorepo/extension`)
Se selecciona WXT (Web Extension Framework) con TypeScript, React 19 y TailwindCSS v4. WXT compila a Manifest V3 de forma nativa tanto para Chromium (`target: chrome`) como para Firefox (`target: firefox`), unificando la API `browser`/`chrome` y gestionando la disparidad entre Service Workers y Background Event Pages.

### 2. Bridge Universal por Content Script
Ante la falta de soporte de `externally_connectable` en Firefox para sitios web externos, el emparejamiento (pairing) entre la SPA de Chiripa y la extensión se implementa mediante un Content Script inyectado en los dominios oficiales (`*.chiripa.cl`, `*.proyectosya.cl`, `localhost:3000`). La comunicación vía `window.postMessage` exige:
- Validación estricta de `event.origin` coincidente con `window.location.origin`.
- Canal tipado `target: "CHIRIPA_EXTENSION"`.
- Nonce criptográfico único por sesión (`crypto.randomUUID()`).
- Ventana de expiración estricta de 60 segundos.
Las credenciales de sesión y tokens de refresco se persisten de forma aislada en `chrome.storage.local`.

### 3. Kill Switch y Capacidades Dinámicas (`GET /extension/capabilities`)
El backend expone capacidades operativas gobernadas por la variable `EXTENSION_ENABLED`. Si Mercado Público altera su estructura o surgen incidencias operativas, el backend puede desactivar selectivamente el scraping (`mp_adapter_enabled: false`) o la cola distribuida (`fetch_jobs_enabled: false`) de inmediato, sin esperar los días de revisión de las tiendas de extensiones.

### 4. `MpFichaAdapter` Resiliente
El adaptador de Mercado Público implementa selectores jerárquicos con fallback y escucha asíncrona vía `MutationObserver`. Detecta el número de llamado (1.er o 2.º llamado), fechas de cierre y extrae el listado de documentos adjuntos. Si la estructura DOM no responde en 10 segundos, emite telemetría de error `adapter_broken` hacia la API de Chiripa.

### 5. Reutilización de Cookies y Subida Deduplicada a R2
La extensión utiliza los permisos de host de `*.mercadopublico.cl` para descargar los archivos con las cookies activas del usuario sin pedir credenciales. Antes de descargar, consulta `POST /extension/attachments/check` y solo descarga documentos inexistentes (`missing`). El SHA-256 se calcula en streaming mediante Web Crypto API y el archivo se sube directo a Cloudflare R2 mediante la URL prefirmada emitida por `POST /tenders/{tender_id}/attachments/{attachment_id}/upload-url`, registrándose con `source="extension"` para alimentar el modelo de confianza de la Decisión 6 (ADR 0002).

### 6. Cola Pull Distribuida (`LeaseFetchJobsUseCase` + `JobRunner`)
Cuando el usuario está inactivo (`chrome.idle == "idle"`), la extensión solicita periódicamente una tarea de descarga mediante `POST /extension/jobs/lease`. La API reserva licitaciones huérfanas mediante `SELECT ... FOR UPDATE SKIP LOCKED` con un arrendamiento de 5 minutos. Se aplica rate-limiting estricto (máximo 1 tarea cada 5 minutos por cliente, tope de 50 tareas diarias y backoff con jitter aleatorio).

### 7. Permisos Mínimos y Opcionales Diferidos
Se solicitan únicamente los permisos esenciales en el manifiesto (`storage`, `cookies`, `alarms`, hosts de Mercado Público y Chiripa). Los permisos de portales de proveedores requeridos para la postulación futura (HdU 20) se configuran como `optional_host_permissions` y se solicitarán bajo demanda en dicha fase.

---

## 3. Alternativas Descartadas

* **Uso de `externally_connectable` en el manifiesto:**  
  *Descartada.* No es compatible con Mozilla Firefox para páginas web estándar, lo que obligaría a mantener dos bases de código incompatibles y excluiría a los usuarios de Firefox.
* **Scraping centralizado en servidores con Playwright / Selenium Headless:**  
  *Descartada.* Costo operativo prohibitivo en infraestructura (CPU/RAM en Railway) y alto riesgo de bloqueo por IP al concentrar miles de peticiones desde un único centro de datos.
* **Solicitar credenciales de Mercado Público al usuario en el popup:**  
  *Descartada.* Representa un riesgo inaceptable de seguridad, almacenamiento de credenciales críticas y fricción innecesaria para el usuario.
* **Uso de `setInterval` continuo en el background service worker:**  
  *Descartada.* Los Service Workers de Manifest V3 en Chromium se suspenden automáticamente tras 30 segundos de inactividad, cancelando los temporizadores. Se adoptó obligatoriamente `chrome.alarms`.

---

## 4. Consecuencias

### Positivas (Beneficios)
- **Soporte universal multi-navegador:** Misma base de código y protocolo seguro para Chrome, Edge y Firefox.
- **Eficiencia y escalabilidad:** Distribuye la captura de documentos entre la comunidad de usuarios sin costo de servidores ni bloqueos de IP centralizados.
- **Seguridad robusta:** Cero almacenamiento de contraseñas de portales externos y aislamiento criptográfico en el emparejamiento.
- **Continuidad operativa:** Capacidad de apagar o pausar módulos instantáneamente mediante el kill switch remoto.
- **Preparación para HdU 20:** Estructura modular lista para incorporar submódulos de postulación en el portal de proveedores cuando se apruebe dicha fase.

### Negativas / Compromisos (Trade-offs)
- **Dependencia de la actividad del usuario:** La velocidad de indexación de licitaciones huérfanas depende de que existan usuarios con la extensión instalada y navegadores abiertos. Mitigado por el fallback de subida manual del panel (Decisión 2).
- **Mantenimiento de selectores DOM:** Cambios estructurales en la SPA de Mercado Público requerirán actualizaciones del adaptador, mitigado por el reporte automático de `adapter_broken` y el kill switch remoto.
- **Proceso de revisión en tiendas:** Cada actualización requiere aprobación en Chrome Web Store y Mozilla Add-ons (AMO).
