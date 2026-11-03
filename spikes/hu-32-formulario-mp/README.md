# Spike: Formulario de Postulación de Mercado Público (HU-032)

Este documento registra los hallazgos técnicos, selectores estables y garantías de seguridad recopiladas para la interacción con los formularios de Mercado Público (Compra Ágil y Licitaciones).

## 1. Detección Pasiva en Pantalla de Login (CA5)

- **Selectores de login**: `form[action*='Login']`, `#txtUsuario`, `#txtClave`, `#btnIngresar`, `#lnkClaveUnica`.
- **Garantía de Seguridad**:
  - La extensión jamás inyecta listeners sobre `#txtClave` ni sobre ningún input `type="password"`.
  - La extensión no interactúa con ClaveÚnica ni con dominios externos de autenticación.
  - La extensión detecta el formulario pasivamente y suspende cualquier acción de postulación hasta que el usuario complete su inicio de sesión de forma manual.

## 2. Detección del Formulario de Postulación (CA6)

- **Selectores del encabezado**:
  - Código de licitación: `#lblNumeroLicitacion` o `.tender-header span`.
  - RUT de la sesión activa: `#lblUsuarioRUT` o `.user-session #lblUsuarioRUT`.
- **Regla estricta de cruce de RUT**:
  - Si el RUT de la sesión activa difiere del RUT de la empresa registrada en la propuesta de Chiripa, la extensión **aborta inmediatamente** el autocompletado y emite una alerta de seguridad (`RUT_MISMATCH`).
- **Selectores de la tabla de cotización**:
  - Fila por ítem: `#tblItems tbody tr` o `tr[data-line]`.
  - Input precio unitario: `input[name*='precio' i]` o `#txtPrecioUnitario_{i}`.
  - Subtotal calculado: `input[name*='subtotal' i]` o `#txtSubtotal_{i}`.
- **Selectores de condiciones generales**:
  - Observaciones / Detalle: `#txtObservaciones` o `textarea[name*='observaciones' i]` (con tope estricto de 255 caracteres para evitar truncado silencioso).
  - Plazo de entrega: `#txtPlazoEntrega` o `input[name*='plazo' i]`.
  - Validez de la oferta: `#txtValidezOferta` o `input[name*='validez' i]`.
  - Archivos adjuntos: `#fileAdjunto` o `input[type='file'][name*='archivos' i]`.

## 3. Resaltado Visual y Asistencia (CA7)

- Todos los campos modificados reciben el atributo `data-chiripa-field-status="filled"`.
- Los campos no modificados o faltantes reciben `data-chiripa-field-status="incomplete"`.
- Los estilos se inyectan en el documento principal respetando variables de accesibilidad (borde verde para completados, ámbar para incompletos).
- Un panel flotante montado en **Shadow DOM** (`#chiripa-postulation-panel-host`) presenta el resumen de campos completados y pendientes, y permite quitar el resaltado con un solo clic.

## 4. Garantía Absoluta de Cero Envíos Automáticos (CA8)

- El código del adaptador y de la extensión tiene prohibido:
  - Invocar `.submit()` o `.requestSubmit()` sobre cualquier formulario.
  - Hacer `.click()` sobre `#btnEnviarOferta`, `#btnGuardarBorrador` o cualquier botón de guardado.
  - Marcar el checkbox de `#chkDeclaracionJurada` (la aceptación de habilidad debe ser un acto voluntario del usuario).
- Esto se verifica continuamente en CI mediante el test estático `static-guards.test.ts`.
