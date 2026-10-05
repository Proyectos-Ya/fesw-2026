# ADR-0003: Arquitectura de la Extensión de Navegador y Adaptador de Mercado Público

* **Fecha**: 2026-10-05  
* **Estado**: Aceptado  
* **Autores**: Equipo Chiripa  

---

## 1. Contexto

La plataforma Chiripa ayuda a MiPymes chilenas a competir y ganar licitaciones del Estado en Mercado Público y Compra Ágil. En la Fase 2 (Decisiones 2, 4, 5 y 6) se implementó el ecosistema de anexos oficiales, el modelo de confianza comunitaria (ADR 0002) y la extracción semántica con Gemini.

Para alimentar este catálogo de documentos y evitar que el backend deba desplegar clusters costosos de navegadores headless (Selenium o Playwright) que saturen los servidores o sufran bloqueos de IP, se requiere una **extensión de navegador** (Decisión 7 del Plan 233). Esta extensión opera en los navegadores de los propios usuarios (Chrome, Edge y Firefox) para detectar fichas de licitaciones, consultar anexos faltantes, descargarlos en el contexto autenticado del usuario en Mercado Público y subirlos de forma deduplicada a Cloudflare R2.

El diseño de esta extensión enfrenta varios desafíos técnicos y arquitectónicos:

1. **Fragmentación de Manifest V3 (MV3) entre Chromium y Firefox:**
   - En navegadores Chromium (Chrome, Edge), MV3 exige `background.service_worker`, el cual se suspende tras ~30 segundos de inactividad, destruyendo conexiones persistentes o temporizadores `setInterval`. En Firefox, MV3 utiliza `background.scripts` (event pages).
   - **Ausencia de `externally_connectable` en Firefox:** En Chrome es posible declarar `externally_connectable` para enviar mensajes directamente desde una página web a la extensión con `chrome.runtime.sendMessage`. **Firefox no soporta esta API para páginas web estándar**. Depender de ella impediría publicar la extensión en Mozilla Add-ons (AMO).
2. **Políticas estrictas de tiendas de extensiones (Chrome Web Store y Mozilla AMO):**
   - Mozilla prohíbe terminantemente código evaluado dinámicamente (`eval`, `new Function`) y scripts remotos. El código debe ser auditable y reproducible desde las fuentes del monorepo.
3. **Scraping resiliente de una Single Page Application (SPA):**
   - El portal de Mercado Público (`buscador.mercadopublico.cl/ficha`) es una SPA en AngularJS/Angular donde los elementos y tablas de anexos se hidratan asíncronamente mediante peticiones XHR. Un scraper ingenuo que lea el DOM al cargarse la página lee un documento vacío.
4. **Privacidad, credenciales y seguridad:**
   - La extensión jamás debe solicitar ni almacenar claves o credenciales de portales gubernamentales de los usuarios (RUT o clave de Mercado Público). Toda descarga debe aprovechar la sesión viva que el usuario ya tenga en su navegador.
   - La vinculación entre la web de Chiripa y la extensión debe ser resistente a ataques de suplantación desde iframes o páginas maliciosas.

---

## 2. Decisión Tomada

Se adopta una **arquitectura basada en el framework WXT (Web Extension Framework) con TypeScript estricto, React 19, TailwindCSS v4 y un Bridge universal por Content Script**, formalizada en las siguientes decisiones de diseño (D7-1 a D7-12):

### Resumen de Decisiones de Diseño (D7-1 a D7-12)

* **D7-1 (Framework WXT en `monorepo/extension`):** Se adopta WXT para compilar de forma nativa a Manifest V3 tanto para Chromium (`target: chrome`) como para Gecko (`target: firefox`), unificando APIs polifill (`browser` / `chrome`), resolviendo la disparidad de background service worker vs script, y ofreciendo Vite HMR para desarrollo.
* **D7-2 (Emparejamiento seguro sin duplicar login):** La extensión no solicita usuario ni contraseña de Chiripa. La aplicación web inicia el emparejamiento pasando el token de sesión y el ID de workspace a través del Bridge; la extensión almacena la sesión en `chrome.storage.local` y confirma la instalación ante el backend en `POST /extension/pairing/confirm`.
* **D7-3 (Bridge universal por Content Script):** Para enlazar la web con la extensión en todos los navegadores (Chromium y Firefox) sin requerir `externally_connectable`, se inyecta un Content Script en los dominios de Chiripa. El protocolo `window.postMessage` exige:
  1. `event.origin` idéntico a la ventana actual (`window.location.origin`).
  2. Canal explícito `target: "CHIRIPA_EXTENSION"`.
  3. Nonce criptográfico `crypto.randomUUID()`.
  4. Marca temporal con caducidad estricta de 60 segundos para evitar ataques de repetición.
* **D7-4 (Feature Flag y Kill Switch centralizado):** La configuración del backend incluye `extension_enabled: bool = True`. El endpoint público `GET /extension/capabilities` entrega flags operativos: `mp_adapter_enabled`, `fetch_jobs_enabled`, `min_version`, `max_daily_fetches` y lista de hosts soportados. Esto permite desactivar de emergencia el scraper sin esperar la revisión de las tiendas.
* **D7-5 (`MpFichaAdapter` resiliente):** Adaptador especializado para la ficha pública de Mercado Público y Compra Ágil. Utiliza observadores de hidratación y selectores jerárquicos resilientes con fallback para detectar el código de licitación, la convocatoria (1.er o 2.º llamado), las fechas de cierre y el listado de documentos adjuntos.
* **D7-6 (Reutilización de cookies de sesión sin credenciales):** La extensión utiliza los permisos de host de `*.mercadopublico.cl` para realizar descargas en el contexto del navegador. No se solicita RUT ni clave de Mercado Público al usuario.
* **D7-7 (Descarga y subida deduplicada por SHA-256):** Al detectar una ficha, la extensión consulta `POST /extension/attachments/check` y solo descarga los anexos faltantes (`missing`). Calcula el SHA-256 en el navegador con Web Crypto API (`crypto.subtle.digest`), solicita URL prefirmada a la API (`source="extension"`) y sube directo a Cloudflare R2 con `x-amz-checksum-sha256`.
* **D7-8 (Cola pull de extracción distribuida comunitaria):** En segundo plano y solo cuando el usuario está inactivo (`chrome.idle`), la extensión solicita periódicamente una tarea a la API (`POST /extension/jobs/lease`). La API asigna una licitación con anexos pendientes mediante `FOR UPDATE SKIP LOCKED` con un arrendamiento de 5 minutos, ritmo máximo de 1 descarga cada 5 minutos y límite de 50 tareas diarias por cliente.
* **D7-9 (Permisos mínimos obligatorios y permisos opcionales diferidos):** Se declaran en el manifiesto únicamente: `storage`, `cookies`, `alarms`, y los hosts de `*.mercadopublico.cl` y de la app de Chiripa. Los permisos para la futura postulación automática (HdU 20) se reservan como `optional_host_permissions` y no se solicitan al instalar.
* **D7-10 (Empaquetado multi-navegador y validación en CI):** Scripts dedicados `pnpm build:chrome` (`wxt build -b chrome`) y `pnpm build:firefox` (`wxt build -b firefox`). En CI se ejecutan `pnpm exec tsc --noEmit`, Vitest y `pnpm exec web-ext lint` sobre el artefacto de Firefox.
* **D7-11 (Contratos de API backend para la extensión):** Endpoints formalizados bajo el prefijo `/extension`: capacidades (`/capabilities`), emparejamiento (`/pairing/start`, `/pairing/confirm`), latido (`/installations/heartbeat`), comprobación de anexos (`/attachments/check`), y ciclo de vida de tareas distribuidas (`/jobs/lease`, `/jobs/{job_id}/result`).
* **D7-12 (Trazabilidad y compatibilidad de base de datos):** Tablas PostgreSQL `extension_installation` y `extension_fetch_job` gestionadas linealmente por Alembic (migración `e3d9b1c7a842`) con claves foráneas seguras en cascada hacia `users` y `tenders`.

---

## 3. Alternativas Descartadas

| Alternativa | Razón del descarte |
|---|---|
| **Cluster de navegadores headless en servidores de backend (Playwright/Selenium en Railway)** | Costo prohibitivo de infraestructura en memoria RAM y CPU; alto riesgo de bloqueos de IP masivos por parte de los cortafuegos gubernamentales de Mercado Público. |
| **Uso de `externally_connectable` en el manifiesto** | Incompatible con Mozilla Firefox. Firefox no implementa esta API para páginas web arbitrarias, lo que habría dejado fuera a los usuarios de Gecko. |
| **Solicitar credenciales de Mercado Público (RUT / Clave)** | Riesgo inaceptable de seguridad y privacidad. Violaría el principio de mínimo privilegio y generaría desconfianza justificada en las MiPymes. |
| **Escribir extensiones separadas nativas para Chrome y Firefox sin framework** | Duplicación masiva de lógica de adapters, hashing y comunicación; divergencia inevitable en el ciclo de vida de desarrollo. |

---

## 4. Consecuencias

### Positivas
- **Soporte universal multi-navegador:** Funciona idénticamente en Google Chrome, Microsoft Edge y Mozilla Firefox con una sola base de código en TypeScript.
- **Eficiencia de costos cero para ingesta de anexos:** La extracción de documentos se distribuye de forma transparente entre los usuarios activos sin requerir granjas de servidores en la nube.
- **Seguridad robusta:** Origen estricto, nonces criptográficos y tokens efímeros previenen ataques de CSRF o suplantación web.
- **Resiliencia operativa:** El Kill Switch (`GET /extension/capabilities`) permite pausar la extensión al instante si Mercado Público cambia su estructura o surge algún incidente.

### Negativas / Mitigaciones
- **Dependencia de la actividad del navegador del usuario:** La cola distribuida depende de que los usuarios mantengan el navegador abierto.
  - *Mitigación:* Se complementa con la subida manual de anexos (Decisión 2) y el modelo de corroboración comunitaria (Decisión 6).
