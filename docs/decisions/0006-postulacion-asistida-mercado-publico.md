# ADR-0006: Postulación Asistida en Mercado Público mediante Extensión de Navegador

* **Fecha**: 2026-11-03  
* **Estado**: Aceptado  
* **Autores**: Equipo Chiripa  

---

## 1. Contexto

La Historia de Usuario HU-032 (Refs #318) tiene como meta permitir a los usuarios de Chiripa postular o cotizar en licitaciones de Mercado Público directamente a partir del borrador de postulación y cotización ya elaborados en la plataforma. 

Mercado Público y Compra Ágil operan como aplicaciones web con autenticación gubernamental (ClaveÚnica) y flujos con CSRF y sesiones protegidas, sin APIs abiertas ni públicas para la remisión directa de ofertas por parte de terceros.

Asimismo, las políticas de seguridad y los términos de servicio exigen:
1. Privacidad y seguridad estricta de las credenciales (Chiripa no debe almacenar, solicitar ni interceptar claves ni sesiones de Mercado Público).
2. Trazabilidad y responsabilidad legal del proveedor: la acción de ofertar y firmar la declaración jurada debe ser realizada conscientemente y de forma manual por el usuario en Mercado Público.
3. Compatibilidad con los estándares de publicación en Chrome Web Store (CWS) y Firefox Add-ons (AMO), lo que demanda permisos mínimos, ausencia de código remoto y justificaciones de seguridad transparentes.

---

## 2. Decisión Tomada

Se decide implementar una **arquitectura de postulación asistida basada en la extensión de navegador web**:

1. **Apertura controlada de pestaña**:
   Al pulsar "Postular en Mercado Público" en Chiripa, la extensión abre una pestaña secundaria en Mercado Público en segundo plano (`tabs.create({ active: false })`), manteniendo el foco en Chiripa para que el usuario revise y confirme la oferta.

2. **Transferencia local y sin pairing obligatorio**:
   Los datos del borrador y cotización se descargan desde la API de Chiripa y se transfieren localmente del frontend a la extensión vía mensajes (`window.postMessage` estructurado y conexión de puerto `runtime.connect` con chunking de binarios hacia IndexedDB de la extensión, con TTL de 30 minutos). No se requiere emparejamiento previo ni compartir tokens de sesión duraderos.

3. **Aislamiento absoluto de credenciales (CA5)**:
   La extensión no tiene permisos ni `content_scripts` sobre dominios de autenticación (ClaveÚnica u otros proveedores de identidad). Cuando el usuario es redirigido al portal de acceso de Mercado Público, la extensión permanece en reposo mediante observación pasiva hasta que el usuario inicia sesión manualmente.

4. **Matching determinista en backend**:
   La normalización y asignación de ítems entre la licitación oficial y los materiales cotizados se resuelve en el backend (`BuildPostulationPackageUseCase`) mediante reglas de emparejamiento textual determinista y orden de aparición, permitiendo revisión y edición de precios en el modal de confirmación antes de la carga.

5. **Asistencia de llenado sin envío automático (CA8)**:
   El adaptador en Mercado Público autocompleta los campos de cotización, impuestos, vigencia y archivos adjuntos mediante inyección en el DOM (`DataTransfer`), resaltando visualmente en un panel Shadow DOM los campos completados (verde) y los pendientes o advertencias (ámbar). Se prohíbe explícitamente cualquier llamada automática a métodos `.submit()`, `requestSubmit()` o clics programáticos en botones de envío o aceptación de declaraciones juradas.

6. **Feature Flag y Despliegue Gradual**:
   Se incorpora el flag `extension_postulation_enabled` en backend y frontend, apagado por defecto en producción hasta que la versión `0.2.0` de la extensión sea formalmente revisada y publicada en Chrome Web Store y Firefox AMO.

---

## 3. Alternativas Consideradas

* **Automatización Server-Side (Headless Browser / Puppeteer en Backend)**:  
  *Descartada*: Exigiría que el usuario entregara su ClaveÚnica o credenciales de Mercado Público a los servidores de Chiripa, lo cual viola flagrantemente las políticas de seguridad de ClaveÚnica, expone a la plataforma a responsabilidades legales severas y resulta frágil frente a CAPTCHAs y mecanismos anti-bot.

* **Exportación a archivo Excel / CSV para importación masiva**:  
  *Descartada*: Compra Ágil y los formularios regulares de cotización en Mercado Público no ofrecen funcionalidad genérica de carga masiva de cotización para todos los rubros, obligando de todos modos al usuario al llenado manual campo por campo.

* **Autocompletado con envío automático de la oferta**:  
  *Descartada*: La presentación de una oferta pública genera obligaciones legales y económicas vinculantes para el proveedor. El envío debe ser un acto voluntario, explícito y verificado por la persona natural autorizada en el portal de compras del Estado.

---

## 4. Consecuencias

### Positivas (Beneficios)
- Ahorro de tiempo sustancial y reducción drástica de errores de tipeo manual para las MiPymes al postular.
- Máxima seguridad: ningún dato de credenciales de Mercado Público o ClaveÚnica es accesible ni almacenado por Chiripa.
- Transparencia total frente a las tiendas de extensiones (CWS y AMO), facilitando la aprobación al usar permisos estrictamente necesarios y código auditable.
- Robustez arquitectónica: separación clara entre preparación de datos (backend/frontend) y manipulación del DOM externo (adaptador de la extensión).

### Negativas / Compromisos (Trade-offs)
- Dependencia del DOM de Mercado Público: si la interfaz o selectores de Mercado Público cambian, el adaptador requerirá actualización y release en las tiendas (mitigado con centralización de selectores en `mp-postulation-selectors.ts` y reportes visuales de campos incompletos).
- Requiere que el usuario tenga instalada la extensión oficial en su navegador Chromium (Chrome, Edge, Brave) o Firefox.
- Proceso de publicación sujeto a los tiempos de revisión de las tiendas de extensiones (de días a un par de semanas).
