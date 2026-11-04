# Plan Técnico: Pegar el borrador en el formulario real de Compra Ágil

**Issue asociada**: Refs #318
**Estado**: Aprobado (2026-11-04), en implementación
**Fecha**: 2026-11-04

Complementa [plan.md](./plan.md) y reemplaza la propuesta de
[compatibilidad-compra-agil.md](./compatibilidad-compra-agil.md), cuyos puntos absorbe.

---

## 1. Contexto y Objetivo

La HU-032 ya tiene el botón, el diálogo de extensión requerida, el diálogo de confirmación y el
traspaso del paquete a la extensión. Lo que no funciona es la parte central: **pegar los datos del
borrador en la pestaña de Mercado Público**. El 2026-11-04 se probó contra la cotización real
5626-943-COT26, con sesión iniciada y sin enviar nada:

| Hipótesis | Resultado |
|---|---|
| Los selectores del adaptador (`#tblItems`, `#lblNumeroLicitacion`, `#lblUsuarioRUT`, `#txtObservaciones`, `input[name*=precio]`…) existen | **No**: 0 coincidencias y ningún `<form>`. `isPostulationForm()` da `false`. |
| El formulario existe en `document_idle` | **No**: a los 6,5 s había 1 input; los 9 controles aparecen hacia los 12 s. |
| `.value = x` + `input`/`change` actualiza React | **No**: React conserva `""` y borra el valor al perder foco. Con el setter nativo de `HTMLInputElement.prototype.value` sí: recalcula subtotal, IVA y total. |
| El RUT de la sesión está en el DOM | **No**: solo aparece el RUT del comprador. El chequeo actual falla abierto. |

Además, con precio y detalle completados, **«Enviar cotización» se habilita**: el llenado deja la
oferta a un clic. CA8 depende de que la extensión nunca lo pulse.

Prioridad pedida: que los ítems, valores y descripción del borrador queden pegados en la pestaña de
Compra Ágil (CA4, CA6, CA7). El resto de los CA se ajustan solo en lo que bloquea eso.

---

## 2. Decisiones Técnicas y Arquitectura

### 2.1 Estructura real del formulario (Compra Ágil, nov-2026)

SPA React en `compra-agil.mercadopublico.cl/resumen-cotizacion/<código>`. Sin `name` ni IDs estables:

- Encabezado `h2` «Detalle de la cotización `<código>`» y sección `h3` «Participar de la Compra Ágil».
- Por producto: nombre, `ID: <código ONU>`, «Cantidad», input «Valor unitario» y subtotal deshabilitado.
- Input «Despacho», textarea «Detalle cotización» (`maxlength=255`).
- «Fecha de vigencia»: datepicker MUI con ID generado (`:r0:`), formato `dd/mm/aaaa`.
- Input `type=file` «documento anexo (opcional)», máx. 20 MB, doc/docx/xls/xlsx/pdf.
- Botones «Volver» y «Enviar cotización» (deshabilitado hasta que hay datos), más reCAPTCHA Enterprise.

### 2.2 Adaptador nuevo y separado

- `extension/src/adapters/mp/compra-agil-adapter.ts`, sin tocar el adaptador clásico
  (`mp-postulation-adapter.ts`), que queda para licitaciones y marcado como **no verificado
  contra el sitio real**.
- Selección por URL: host `compra-agil.mercadopublico.cl` y ruta `/resumen-cotizacion/<código>`.
  El código de la URL debe coincidir con el `h2` y con `tender_code` del paquete.
- Localización de controles por **texto visible del contenedor** («Valor unitario», «Despacho»,
  «Detalle cotización», «Fecha de vigencia», «documento anexo»), centralizado en
  `compra-agil-selectors.ts` para que un cambio de MP se arregle en un solo archivo.
- Escritura con el **setter nativo** + evento `input` burbujeante. Un campo se marca `filled`
  solo si, tras un re-render, el valor leído sigue siendo el escrito. Si no, `incomplete`.
- Montos: enteros CLP sin separadores (MP formatea a `11.111`).

### 2.3 Espera de hidratación

`waitForCompraAgilForm(timeoutMs = 30000)` con `MutationObserver` hasta que existan la sección
«Participar» y al menos un input «Valor unitario». Se desconecta al cumplirse, al vencer o al
cambiar de ruta (la SPA navega con History API: vigilar `location.href`). Al vencer, el panel
informa «No encontramos el formulario» y no se toca nada.

### 2.4 Mapeo de ítems

- Agregar `product_code` (opcional) a `PostulationItemPayloadSchema` (extensión) y al payload que
  arma `PostulationConfirmDialog` (el backend ya lo entrega en `PostulationItem.product_code`).
- Orden de preferencia: `product_code` igual al `ID:` del bloque y único → mismo número de ítems
  y mismo orden → si no, el ítem queda `incomplete`. Nunca se adivina.

### 2.5 Identidad de la empresa (fail-closed)

- La página llama a `servicios-compra-agil.mercadopublico.cl/v1/compra-agil/proveedor/empresa/<RUT>`
  con el RUT de la empresa en sesión. Se lee desde `performance.getEntriesByType("resource")`
  (solo URLs, sin tokens, cookies ni cuerpos). **Hay que verificar** que el content script ve
  esas entradas. Alternativa: el texto del encabezado del escritorio, si lo muestra.
- Si no se obtiene el RUT o no coincide con `company_rut`: **no se llena nada** y el panel lo dice.
  Esto corrige el fallo abierto actual.
- CA6 «datos de la empresa»: Compra Ágil no pide datos de empresa en el formulario (los toma de la
  sesión). El CA se cumple con la verificación de identidad, y así se documenta.

### 2.6 Apertura de la pestaña (CA3) y login (CA5)

- Para códigos `-COT`, abrir `https://compra-agil.mercadopublico.cl/resumen-cotizacion/<código>`
  en lugar de `Menu.aspx`, que es un marco del portal y obligaba a `allFrames`.
  Se verificó que la URL directa carga el formulario con la sesión iniciada.
- Sin sesión, MP redirige a su login. La extensión no actúa en el host de autenticación:
  identificar ese host y agregarlo a `excludeMatches` del content script (hoy
  `*://*.mercadopublico.cl/*` lo cubriría). Quitar `allFrames: true`.
- Al volver del login, el content script se activa en la ruta de la cotización y pide el paquete
  pendiente (ya persiste en IndexedDB con TTL de 30 min). Verificar a dónde vuelve MP tras el login.

### 2.7 Adjuntos (CA4, CA6)

- Asignar `input.files` con `DataTransfer` y disparar `change`. Validar tamaño (≤ 20 MB) y
  extensión antes de intentarlo.
- **Riesgo por verificar**: si Compra Ágil sube el archivo a su servidor apenas se selecciona, la
  prueba real ya envía un documento a MP aunque no se envíe la cotización. Probarlo solo con
  autorización explícita y con un archivo inocuo.
- Si no se puede, el adjunto queda `incomplete` y el panel ofrece descargarlo para subirlo a mano.

### 2.8 Resaltado y no envío (CA7, CA8)

- Atributo `data-chiripa-field-status` y estilos en los controles. Resumen en el panel Shadow DOM,
  con lista de completados y pendientes y un aviso: «Revisa y envía tú la cotización».
- La página carga Hotjar y Mouseflow (grabación de sesión). El panel no escribe datos sensibles
  en el DOM de la página fuera del Shadow DOM cerrado.
- `static-guards.test.ts` se extiende al adaptador nuevo: sin `.click()`, `submit()`,
  `requestSubmit()` ni acceso a botones de envío, a reCAPTCHA o a inputs `password`.

### 2.9 Seguridad del bridge (bloqueante, porque el bridge entrega el paquete que se pega)

- Quitar `*://*.vercel.app/*` de `bridge.content.ts` y del manifiesto. Dejar los dominios de
  Chiripa y, en desarrollo, localhost.
- Revertir el chequeo de origen relajado (`event.origin && …`) y el `postMessage(…, "*")`.
- `mp_url` solo se acepta si su host es `*.mercadopublico.cl`. `api_url` de `PAIR_SESSION` solo
  si está en una lista permitida.
- Quitar los `console.log` de depuración del bridge.

### 2.10 Fuera de alcance y limpieza

- Licitaciones (no COT): siguen con el adaptador clásico sin verificar. Se planifican aparte con
  su propia captura real.
- Valor de despacho: el paquete no lo tiene. Queda `incomplete` para que el usuario lo complete.
- Quitar `rea-agents` de `extension/package.json` y del lockfile. No se usa en la extensión.
- Sin dependencias nuevas.

---

## 3. Desglose de Tareas (Checklist)

Orden por prioridad. Cada tarea con TDD (Red → Green → Refactor).

### Fase A — Bridge seguro (bloqueante)
- [x] A1 Red: tests de `content-script-bridge` que rechazan origen vacío o ajeno y `mp_url` fuera de MP.
- [x] A2 Green: restringir matches, revertir el origen relajado y `"*"`, validar `mp_url` y `api_url`.
- [x] A3 Quitar `rea-agents` y los logs de depuración.

### Fase B — Pegar ítems, valores y descripción (núcleo de la prioridad)
- [x] B1 Fixture saneada `__fixtures__/compra-agil-form.html` con la estructura real (sin RUT ni datos
      personales), más un componente React controlado mínimo en el test para reproducir el fallo de `.value`.
- [x] B2 Red: `compra-agil-adapter.test.ts`: detecta la ruta y el código, rechaza código distinto,
      llena el precio con el setter nativo y lo verifica, deja `incomplete` el ítem ambiguo,
      recorta el detalle a 255 y no toca botones.
- [x] B3 Green: `compra-agil-selectors.ts` y `compra-agil-adapter.ts`.
- [x] B4 Red-Green: `waitForCompraAgilForm` (hidratación tardía, timeout, cambio de ruta).
- [x] B5 Red-Green: `product_code` en el schema Zod y en `PostulationConfirmDialog`.
- [x] B6 Red-Green: `mp.content.ts` elige el adaptador por URL, espera el formulario y aplica el paquete.

### Fase C — Identidad fail-closed
- [ ] C1 Verificar en el sitio real que el content script lee la entrada `/proveedor/empresa/<RUT>`.
- [x] C2 Red-Green: sin RUT o con RUT distinto no se llena nada y el panel lo informa.

### Fase D — Apertura y login
- [x] D1 Red-Green: el coordinador y `useMercadoPublicoPostulation` abren la URL directa para `-COT`.
- [ ] D2 Identificar el host de login de MP, agregar `excludeMatches`, quitar `allFrames`.
- [ ] D3 Verificar el regreso tras el login y que el paquete pendiente se aplica.

### Fase E — Vigencia y adjuntos
- [x] E1 Red-Green: fecha de vigencia = hoy + `validity_days` en `dd/mm/aaaa`, verificada tras re-render.
- [x] E2 Red-Green: adjunto vía `DataTransfer` con validación de tamaño y tipo.
- [x] E3 Verificación real de adjuntos **solo con autorización** (ver 2.7).

### Fase F — Resaltado y verificación final
- [x] F1 Red-Green: panel con completados, pendientes y aviso de envío manual.
- [ ] F2 Extender `static-guards.test.ts` al adaptador nuevo.
- [ ] F3 Verificación manual con la extensión cargada en Chrome y Firefox sobre una Compra Ágil
      real, sin enviar. Recargar para descartar.
- [ ] F4 Actualizar `task.md`, `spikes/hu-32-formulario-mp/README.md` y el ADR-0006 (adjuntos,
      URL directa, identidad).

---

## 4. Plan de Verificación y Pruebas

```bash
# Extensión (monorepo/extension)
pnpm run test
pnpm run compile

# Frontend (monorepo/frontend)
pnpm run test
```

Verificación manual (F3), por CA:

| CA | Comprobación |
|---|---|
| CA3 | La pestaña abre en `resumen-cotizacion/<código>` y el diálogo aparece en Chiripa. |
| CA4/CA6 | Tras confirmar, cada «Valor unitario» muestra el precio, el total de MP coincide con `total_clp` y el detalle tiene el texto del borrador. |
| CA5 | Sin sesión, la extensión no actúa en el login. Tras iniciar sesión, se aplica el paquete. |
| CA6 | Con otra empresa en sesión, no se llena nada. |
| CA7 | Campos verdes y ámbar, y el panel los lista. |
| CA8 | «Enviar cotización» nunca se pulsa. Lo envía el usuario. |

## 5. Decisiones de la revisión (2026-11-04)

1. Se autoriza probar un adjunto real en Compra Ágil (E3) con un PDF de prueba sin datos
   personales, sin pulsar «Enviar cotización» y quitando el adjunto o recargando al terminar.
2. Despacho no debe quedar siempre para el usuario, pero no es prioritario. Por ahora queda
   marcado como pendiente; **fuente del valor por definir** (borrador o cotización).
3. Las licitaciones que no son Compra Ágil quedan fuera de esta iteración.

## 6. Hallazgos durante la implementación

- Sin sesión, abrir `resumen-cotizacion/<código>` redirige a `www.mercadopublico.cl/Home` y se
  pierde la ficha. Tras iniciar sesión hay que volver a abrirla desde Chiripa (el paquete sigue
  disponible 30 min). Pendiente: guiar al usuario en el panel o en el diálogo (D3).
- La prueba del 2026-11-04 se hizo en el mundo de la página. En un content script (mundo aislado)
  el `.value` directo podría bastar, porque React no ve el interceptor; el setter nativo funciona
  en ambos casos y es lo que usa el adaptador.

## 7. Verificación en el sitio real (2026-11-04, 5626-943-COT26)

El adaptador compilado se ejecutó en la página con sesión iniciada (en el mundo de la página,
no como extensión instalada). Nunca se pulsó «Enviar cotización».

- Detección: código de la URL y del encabezado, formulario listo en 0,6 s tras cargar, RUT de la
  empresa en sesión leído de `/proveedor/empresa/<RUT>` y el ítem 42070220 emparejado por código.
- Llenado: precio 11.111 (MP recalculó IVA 2.111 y total 13.222), detalle, vigencia y anexo
  quedaron `filled`. Despacho `incomplete`. «Enviar cotización» se habilitó.
- **El anexo se sube al servidor de MP apenas se selecciona** (`POST …/cotizacion/adjuntar`),
  antes de enviar la cotización. Se quitó con «Eliminar» y se verificó tras recargar.
  Consecuencia: el adjunto debe pedir confirmación explícita en el panel antes de subirse
  (pendiente) o dejarse como acción del usuario.
- Pendiente C1: confirmar que el content script (mundo aislado) ve las entradas de
  `performance` de la página, con la extensión cargada.

