# Plan Técnico: HU-30, ver más detalles de las licitaciones

**Issue asociada**: Refs #312  
**Dependencia**: Requiere completar #294 para que la HU esté 100% funcional  
**Estado**: Aprobado el 2026-10-25, en implementación. Decisiones en §8  
**Fecha**: 2026-10-24, revisado el 2026-10-25  
**Tareas**: [task.md](./task.md)

---

## 1. Contexto y Objetivo

La ficha de una licitación (`TenderDetailView.tsx`) muestra en una sola columna
el título, el organismo, el monto, el cierre, la publicación, la descripción,
los ítems, los anexos y el análisis IA. No dice cuántas cotizaciones lleva la
licitación. El llamado solo aparece como el badge "Segundo llamado" cuando
`call_number == 2`, así que una licitación en primer llamado se ve igual que una
sin el dato.

El objetivo de esta HU es soportar en la base de datos, el dominio, la API y la
ficha del frontend el número de cotizaciones recibidas (`tender.received_offers_count`),
el conteo del primer llamado (`tender.first_call_offers_count`) y la fecha de
última revisión (`tender.offers_checked_at`). La ficha muestra arriba los datos
clave para decidir si postular y, debajo, secciones apiladas con el detalle.

La cifra ya viene en el listado de Mercado Público y hoy se descarta:
`tests/fixtures/mp_listado_cambios.json` la trae en
`resumen.total_ofertas_recibidas`, con 0, 17, 1 y 0 en sus cuatro ítems.
sync-estados la escribe desde el listado en cada corrida, y la ingesta desde el
detalle cuando lo descarga. El llamado ya se guarda en `tender.call_number`
desde el plan 233.

> **Nota de dependencia (#294):** Para que esta HU esté **100% funcional**,
> primero hay que realizar el issue **#294**. Ahí se guardan la dirección y el
> plazo de entrega, que van en la sección "Entrega y requisitos", y se verifica
> con detalles reales que el detalle trae `resumen.total_ofertas_recibidas`. Por
> eso el PR usa `Refs #312`.

**Fuera de alcance:**

- La dirección y el plazo de entrega, y la verificación del detalle con
  peticiones reales. Corresponden al issue **#294**, que debe completarse para
  que esta HU quede 100% funcional. Esta HU deja la sección "Entrega y
  requisitos" lista para recibir esos campos (§5.2).
- Un historial de cotizaciones. Se guarda solo el último valor.
- Mostrar las cotizaciones en las tarjetas de matches, en la búsqueda o en el
  enlace compartido. Esas vistas reciben el campo porque viaja en `Tender`, pero
  no lo pintan.
- Cambiar cómo otras vistas muestran el llamado. `SECOND_CALL_LABEL` e
  `isSecondCall` (`utils/secondCall.ts`) quedan igual.
- Pestañas. CA4 pide secciones, y las pestañas obligaban a montar paneles
  ocultos y a reescribir las pruebas de telemetría.

---

## 2. Criterios de Aceptación

| CA  | Cómo se cumple |
| --- | --- |
| CA1 | Métrica "Cotizaciones recibidas" con `received_offers_count` y, debajo, "Revisado el {fecha}" con `offers_checked_at` |
| CA2 | Badge en la tarjeta "Llamado y cotizaciones" de la grilla superior. "Primer llamado" en tono `info` (azul) y "Segundo llamado" en tono `warning` (ámbar) |
| CA3 | `null` de punta a punta: columna nullable, `int \| None` en dominio y API, y la vista escribe "No disponible". Un 0 solo aparece si la fuente informó 0 |
| CA4 | Encabezado con título y organismo, y grilla de tres métricas: monto, cierre, y llamado con sus cotizaciones. Debajo, las secciones "Entrega y requisitos", "Documentos" y "Descripción". Para que quede 100% funcional (dirección y plazo de entrega), primero debe completarse #294 |

---

## 3. Cambios en BD

Una migración sobre `tender`, encadenada tras la cabeza que dé `alembic heads`
(hoy `2510718f486e`, igual en `origin/develop`). Antes de escribirla se usan las
skills `supabase` y `supabase-postgres-best-practices`.

| Columna | Tipo | Uso |
| --- | --- | --- |
| `received_offers_count` | integer null, sin default | Total de ofertas recibidas en el llamado actual. `NULL` significa que la fuente no lo informó |
| `first_call_offers_count` | integer null, sin default | Última cifra registrada del primer llamado, para sumar ambos llamados cuando pasa a segundo llamado (§4.5) |
| `offers_checked_at` | timestamp (UTC naive) null, sin default | Última vez que se revisó la cifra. `NULL` si nunca se leyó |

- En `TenderModel` se agregan los campos con `Field(default=None)`, junto a
  `call_number`.
- Columnas nullable sin default: no reescriben la tabla y la versión anterior
  del backend las ignora (AGENTS.md, "Base de datos y migraciones").
- Sin paso de datos, sin índice (nadie filtra ni ordena por ellas) y sin CHECK.
- La migración va en el mismo PR que el resto (decisión 3). Es el primer commit
  de la rama, y antes de abrir el PR se corre `python -m scripts.migraciones`
  para confirmar una sola cabeza.

---

## 4. Backend

### 4.1 Lectura del dato

`leer_total_ofertas(item) -> int | None`, en
`app/infrastructure/services/tenders/ofertas.py`, al lado de `leer_llamado`
(`llamados.py`). La usan el listado y el detalle, para que los dos lean igual.

| `resumen.total_ofertas_recibidas` | Resultado |
| --- | --- |
| `0` | `0` |
| entero positivo | ese entero |
| `null`, clave ausente o `resumen` ausente | `None` |
| `resumen` que no es un objeto | `None` |
| `true` o `false` | `None`. `bool` es subclase de `int` en Python, así que se compara con `type(valor) is int` |
| negativo, texto o decimal | `None` |

### 4.2 sync-estados (listado)

- `CambioDeEstado` suma `received_offers_count`, que `cambio_desde_item` llena
  con `leer_total_ofertas(item)`. Un ítem sin el dato sigue siendo un cambio
  válido.
- `SyncTenderStatusesUseCase.execute` pasa a `overwrite_received_offers_count`
  toda licitación conocida cuyo cambio traiga cifra, también en una
  reapertura. Lo llama después de `overwrite_call_info` y antes de
  `registrar_punteros`.
- `TenderRepository.overwrite_received_offers_count` hace un
  `UPDATE ... FROM (VALUES ...)` por lote de `_LOTE_ESTADOS`. Fija la cifra y
  `offers_checked_at = utc_now_naive()` aunque la cifra no cambie, porque esa
  fecha registra la revisión. No mueve `updated_at` (dispara la regeneración del
  análisis de Gemini) ni `last_change_at`.
- `ResultadoSyncEstados.ofertas_revisadas` cuenta las filas, y el resumen que
  imprime `scripts/sync_estados.py` suma "N con cotizaciones revisadas".

### 4.3 Ingesta (detalle)

- `TenderIngestaDTO.received_offers_count`, que `_parse_to_dto` llena con
  `leer_total_ofertas(detail)`.
- En el alta, `TenderModel` guarda la cifra y, si la hay, `offers_checked_at`.
- En la actualización, `_aplicar_ofertas` sigue la regla de `_aplicar_llamado`:
  un `None` no borra, y si solo cambia la cifra no se mueve `updated_at` ni se
  toca Qdrant.

Que el detalle traiga el campo lo documenta la guía oficial de la API (versión
3.0 de mayo de 2026, §6.6, enlazada desde chilecompra.cl/api), pero no se
confirmó con una petición real. Esa verificación es un criterio de #294. Si un
detalle real no lo trae, `leer_total_ofertas` devuelve `None` y la cifra del
listado queda intacta.

### 4.4 Dominio y API

- `Tender` suma `received_offers_count: int | None = None`,
  `first_call_offers_count: int | None = None` y
  `offers_checked_at: datetime | None = None`, junto a los campos del llamado.
- `TenderRepository` los copia en las dos conversiones entre modelo y entidad
  (las líneas donde hoy se copia `call_number`).
- `TenderDetailResponse` contiene un `Tender`, así que el `GET` de la ficha los
  devuelve sin tocar el caso de uso ni el router. Un `None` se serializa como
  `null`.

### 4.5 Suma de los dos llamados

En Compra Ágil la cifra de ofertas recibidas corresponde al llamado actual, por
lo que en un segundo llamado cuenta solo las ofertas de ese segundo llamado.
La ficha muestra la suma de los dos llamados (decisión 10):

- Columna `tender.first_call_offers_count` (integer null, sin default), en la
  misma migración de §3.
- Regla única, en sync-estados y en la ingesta: si el cambio trae
  `call_number == 1` y una cifra, `first_call_offers_count` toma esa cifra. Con
  cualquier otro llamado, o sin cifra, conserva la que tenía. Al abrirse el
  segundo llamado queda congelada la última cifra vista del primero.
- En sync-estados va en el mismo `UPDATE`, con `call_number` en el `VALUES`. Se
  mira el `call_number` del cambio y no el guardado, porque
  `overwrite_call_info` corre antes y ya lo cambió.
- `Tender` y la API exponen `first_call_offers_count`. El frontend calcula el
  total:

| Llamado | `first_call_offers_count` | Valor de la tarjeta | Pista |
| --- | --- | --- | --- |
| 1, `null` u otro | cualquiera | `formatOffersCount(received_offers_count)` | "Revisado el …" |
| 2 | conocida | `formatOffersCount(primero + received_offers_count)` | "N en el 1.er llamado y M en el 2.º · Revisado el …" |
| 2 | `null` | "M en el 2.º llamado" | "1.er llamado: No disponible · Revisado el …" |
| 2 | cualquiera, con `received_offers_count` `null` | "No disponible" | ninguna |

Las licitaciones que ya estaban en segundo llamado sin dato previo del primero
quedan en la tercera fila.

---

## 5. Frontend

### 5.1 Tipos y utilidades

- `tenderTypes.ts`: `received_offers_count?: number | null`,
  `first_call_offers_count?: number | null` y
  `offers_checked_at?: string | null` en `Tender`. Un comentario dice que `null`
  o ausente es "la fuente no lo informó", no 0.
- `utils/offers.ts`, `formatOffersCount(count)`:
  - `null` o `undefined` da `"No disponible"`;
  - 1 da `"1 cotización"`, y cualquier otro número, 0 incluido, da
    `"N cotizaciones"`;
  - el chequeo es `count == null`, no `!count`, porque `!0` es verdadero.
- `utils/secondCall.ts`, `callBadge(tender)`, que devuelve etiqueta y tono:

| `call_number` | Etiqueta | Tono |
| --- | --- | --- |
| `1` | "Primer llamado" | `info` |
| `2` | `SECOND_CALL_LABEL` ("Segundo llamado") | `warning` |
| `null`, ausente u otro valor | "Llamado no disponible" | `neutral` |

- `Badge` suma `data-tone={tone}`, para que las pruebas comprueben el tono sin
  depender de las clases de Tailwind.

### 5.2 `TenderDetailView.tsx`

**Encabezado.** Conserva el título, el organismo (`buyer_name`, `buyer_unit` y
`region`), el puntaje y las acciones. Se quita el badge "Segundo llamado" del
encabezado (líneas 494-496). El llamado pasa a la grilla.

**Grilla de métricas.** Tres `KeyValueCard`, en `sm:grid-cols-3` (decisión 11):

| Tarjeta | Valor | Pista |
| --- | --- | --- |
| Monto estimado | `formatCLP(available_amount_clp)` | |
| Cierre | `formatClosingDate(closing_at)` | `closing.label` |
| Llamado y cotizaciones | `Badge` de `callBadge` y, debajo, `offersSummary(tender).value` | Desglose por llamado (§4.5) y "Revisado el {`formatDateTime(offers_checked_at)`}", unidos por " · " |

`KeyValueCard` recibe hoy `value: string`. Pasa a `ReactNode` para aceptar el
badge. La tarjeta "Publicación" sale de la grilla y su fecha pasa a "Hitos y
fechas importantes".

**Secciones, en este orden:**

1. "Entrega y requisitos": `CallClosingDates`, ítems y `DigestCard`. #294 agrega
   aquí la dirección y el plazo de entrega para que la HU quede 100% funcional.
2. "Documentos": `TenderAttachmentsPanel`.
3. "Descripción": el texto de la licitación.
4. Análisis IA y propuesta, como hoy.
5. "Hitos y fechas importantes" (con la publicación) y "Enlaces relacionados",
   como hoy.

Todo queda montado y visible, así que los avisos `onReadyKeyChange` y
`onAnalysisFinished` de `TenderAttachmentsPanel` siguen funcionando sin cambios.

### 5.3 Pruebas existentes que cambian

- `TenderDetailView.test.tsx` busca la sección "Requisitos y descripción"
  (línea 198). Pasa a "Entrega y requisitos".
- Las pruebas de llamado (líneas 604-660):
  - la de segundo llamado sigue buscando "Segundo llamado", ahora dentro de la
    tarjeta "Llamado y cotizaciones";
  - la de primer llamado pasa a exigir "Primer llamado";
  - las dos de "sin los campos" dejan de exigir que no haya nada: la tarjeta
    muestra "Llamado no disponible".
- `TenderDetailView.telemetry.test.tsx` no cambia: no hay contenido oculto.

---

## 6. Plan de pruebas

El detalle, tarea por tarea y en orden TDD, está en [task.md](./task.md).

```bash
# Backend, desde monorepo/backend con .venv activo y `supabase start`
pytest
python -m scripts.migraciones   # una sola cabeza

# Frontend, desde monorepo/frontend
pnpm run test
pnpm run lint
pnpm run build
```

Resultado de la tarea de cierre de suite (2026-10-25, Supabase local, sin `.env`):
3630 pruebas pasan y 7 fallan. Las 7 fallan igual en `origin/develop` y no tocan
esta HU: 3 de `test_gemini_guardrails_live.py` y 3 de
`test_tender_chat_multidoc_integration.py` llaman a Gemini real, y
`test_un_admin_pide_la_url_y_la_lista_refleja_el_cupo` responde 503 sin
configuración de storage. `python -m scripts.migraciones` da una sola cabeza
(`2868884ba7ee`). La migración se autogeneró contra una base recién migrada,
porque la base local de desarrollo está marcada en `2510718f486e` sin la tabla
`tender_milestone_document`.

### Prueba manual

Resultado: _pendiente_ (tarea de prueba manual en el navegador).

---

## 7. Despliegue y rollback

### Despliegue

Un solo PR hacia `develop` (decisiones 3 y 4). La migración es el primer commit
y es compatible hacia atrás: la versión vieja del backend convive con las
columnas nuevas. Un frontend sin el campo muestra "No disponible".

Desplegar en dev test aplica la migración sobre la base de producción, porque
las dos comparten base. El `downgrade` también la afecta.

Los crons de producción tienen que desplegar desde una rama que incluya este
código. Si no, nunca escriben la cifra y la ficha muestra siempre "No
disponible". Hay que confirmarlo en el dashboard de Railway (tarea 0.4). La API
despliega antes que los crons, porque su `preDeployCommand` aplica la
migración. No se mergea a `main` entre las 06:00 y las 12:00 UTC.

### Rollback

- **Código.** Revertir el PR sin el commit de la migración. Las columnas quedan
  con los valores escritos y nadie las lee.
- **Esquema.** El `downgrade` borra las columnas nuevas. Se corre solo después
  de revertir el código, porque un backend que las usa falla sin ellas. Los
  valores se recuperan con las corridas siguientes de sync-estados.

### Riesgos

1. **Dependencia con #294.** Mientras no esté resuelto el issue #294, la
   sección "Entrega y requisitos" no muestra la dirección ni el plazo de
   entrega, y el campo del detalle sigue sin verificarse con datos reales. Para
   que esta HU esté 100% funcional primero se debe hacer #294.
2. **La cifra puede no refrescarse cada hora.** sync-estados lista solo las
   licitaciones con `fecha_ultimo_cambio` dentro de la ventana. No está
   verificado si una cotización nueva mueve esa fecha (tarea 0.3). Si no la
   mueve, la cifra solo se refresca cuando cambia el estado, y "Revisado el"
   muestra una fecha vieja.
3. **Las licitaciones existentes empiezan sin cifra.** Quedan en "No
   disponible" hasta que sync-estados las liste. Las que ya estaban en segundo
   llamado nunca tendrán la cifra de su primer llamado.
4. **Un `None` conserva el último valor conocido.** Si Mercado Público deja de
   informar la cifra, la ficha muestra la última que vio, con la fecha de esa
   revisión. Es la misma regla que el llamado.
5. **Migración en una rama con feature.** AGENTS.md recomienda un PR propio para
   el esquema. Se decidió un solo PR. Para acotar el riesgo de cabezas
   múltiples, la rama se mantiene corta y se corre `python -m scripts.migraciones`
   antes de abrir el PR y antes de mergear.

---

## 8. Decisiones (2026-10-25)

1. **Secciones apiladas, sin pestañas.** CA4 pide secciones. Se elimina el
   componente `Tabs`.
2. **La fecha de CA1 es la última revisión.** Columna `offers_checked_at`. Se
   muestra en formato absoluto: "Revisado el 25 oct, 14:05".
3. **Un solo PR** con migración, backend y frontend.
4. **Rama base y destino: `develop`.**
5. **Etiquetas "Primer llamado" y "Segundo llamado"**, iguales a las de Mercado
   Público y a `SECOND_CALL_LABEL`.
6. **El llamado va solo en la tarjeta de la grilla.** Se quita del encabezado.
7. **Para que la HU esté 100% funcional primero hay que hacer #294.** La
   dirección y el plazo de entrega, y la verificación del detalle con datos
   reales, corresponden a #294. Esta HU lee y guarda la cifra desde sync-estados
   y la ingesta, la expone en dominio y API, y deja la sección "Entrega y
   requisitos" lista en el frontend.
8. **Orden de las secciones:** entrega y requisitos, documentos, descripción,
   análisis IA, hitos y enlaces.
9. **El panel de anexos baja a "Documentos".** El plan 233 (decisión 2) lo
   puso bajo el encabezado para que la subida manual quede a la vista. CA4
   pide los documentos debajo de las métricas, así que pasa a la sección
   "Documentos", que sigue antes de la tarjeta de análisis IA. La prueba
   "muestra el panel de anexos justo bajo el encabezado" se reemplazó por una
   que exige esa posición nueva.
10. **La cifra suma los dos llamados.** La API cuenta solo el llamado actual.
    Se guarda aparte la última cifra del primer llamado y la ficha muestra la
    suma, con el desglose en la pista (§4.5).
11. **Llamado y cotizaciones en una sola tarjeta.** La cifra depende del
    llamado, así que van juntos: el badge arriba y la cifra debajo. La grilla
    queda en tres tarjetas. Para que "No disponible" no salga dos veces en la
    misma tarjeta, el badge sin dato dice "Llamado no disponible".
