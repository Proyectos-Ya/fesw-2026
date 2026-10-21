# Plan Técnico: Ingesta y sync-estados con etiquetado de pendientes

**Issue asociada**: Refs #305  
**Estado**: Implementado, pendiente de PR  
**Fecha**: 2026-10-13  

---

## 1. Contexto y Objetivo

Chiripa trae las Compras Ágiles con dos crons de Railway, ambos desde la imagen
de `monorepo/backend`:

| Cron | Script | Horario | Qué hace hoy |
|---|---|---|---|
| `ingesta-Ptyv` | `scripts/sync_diaria.py` | 06:00 UTC | Lista lo publicado desde el cursor, encola y baja el detalle de las nuevas |
| `sync-estados` | `scripts/sync_estados.py` | cada hora | Lista lo que cambió en las últimas 2 h y aplica estado y cierre a lo que ya tenemos |

Lo que se midió en producción entre el 2026-10-05 y el 2026-10-12:

- **La ingesta no cerró ninguna corrida `ok` en 7 días.** El cursor quedó en el
  2026-10-05 06:06. La ventana crece cada día, la corrida vence el tope de 6 h y
  no mueve el cursor, aunque el listado haya venido completo. El 10-06 la cortó
  un despliegue de `main`.
- **240 Compras Ágiles dan 504 siempre** al pedir el detalle, también en la
  página oficial. Tienen entre 13 y 21 intentos y gastan unas 2 h y ~2.400
  peticiones cada noche.
- **sync-estados no ve cambios entre las 12:00 y las 20:00 UTC de los días
  hábiles.** A las 12:00 la primera página da 504 y el listado se corta en 0.
  Después vence el tope de 50 min, y como los cambios se aplican al terminar el
  listado, se pierde todo y la corrida no queda en `sync_estados_run`. Del 10-06
  al 10-09 quedaron 30,6 h sin cubrir.
- **2.637 licitaciones activas** no se escriben desde el último tramo sin
  cobertura y pueden tener cambios que no vimos.
- **Latencia.** Una Compra Ágil está abierta 47,5 h (mediana) y tarda 17,2 h
  (mediana) en entrar a Chiripa. El 5,8 % entra ya cerrada.
- **Los errores son 504 y 500 del gateway** de Mercado Público, en horario de
  oficina de Chile. El fin de semana no hay fallas. No hay 403 ni bloqueos, así
  que no se cambia nada de IP.

El objetivo es separar responsabilidades. sync-estados lista y deja cada código
etiquetado en `tender_metadata` como `nueva` o `actualizar`. La ingesta corre
cada 2 h y baja los detalles de lo etiquetado. Ninguna corrida pierde lo que ya
listó, y una compra que falla siempre deja de pedirse después de 5 noches.

**Fuera de alcance:**

- La frecuencia y el tamaño de la ventana de sync-estados. Se deciden con una
  medición de latencia y 504 por tamaño de ventana, en otro PR.
- Que una primera página caída no corte el listado de sync-estados. Se cruza con
  el tamaño de la ventana.
- Mostrar en Chiripa las compras sin detalle.
- Una política distinta para la hora punta. Por ahora la ingesta trabaja igual
  todo el día y se revisa con los datos de consumo.
- Guardar una huella del ítem del listado. Primero se mide cuántas `actualizar`
  terminan sin cambios.

---

## 2. Decisiones Técnicas y Arquitectura

### 2.1 Quién hace qué

| Paso | Quién | Cuándo |
|---|---|---|
| Listar cambios, aplicar estado, cierre, llamado y anexos, y etiquetar | sync-estados | cada hora |
| Bajar el detalle de `nueva` y `actualizar` | ingesta, modo `frecuente` | cada 2 h |
| Red de seguridad: listar por publicación, en tramos, lo que sync-estados no vio | ingesta, modo `nocturna` | 06:00 UTC |
| Reintentos de las que fallaron (máximo 5) | ingesta, modo `nocturna` | 06:00 UTC |

Las dos ingestas son el mismo script y el mismo servicio de Railway.
`--modo auto` elige `nocturna` en la corrida de las 06:00 UTC y `frecuente` en el
resto. El cron pasa de `0 6 * * *` a `0 */2 * * *` desde el panel, después del
merge y con confirmación.

### 2.2 Esquema

Una migración, encadenada tras `1ddfcce953b7`, con columnas nullable y
compatible hacia atrás. Antes de escribirla se usan las skills `supabase` y
`supabase-postgres-best-practices`.

`tender_metadata`:

| Columna | Tipo | Uso |
|---|---|---|
| `pending_reason` | varchar null | `nueva` o `actualizar` mientras `is_processed=false` |
| `api_status_code` | varchar null | Estado según el último listado |
| `api_changed_at` | timestamp null | `fecha_ultimo_cambio` más reciente vista. Se escribe con `GREATEST` |
| `detail_fetched_at` | timestamp null | Cuándo se **pidió** el último detalle que se procesó bien. Se rellena desde `tender.last_change_at` |
| `night_retries` | int, default 0 | Reintentos nocturnos usados (máximo 5). Un default constante tampoco reescribe la tabla |
| `discarded_at` | timestamp null | Estado terminal: no se vuelve a pedir ni a encolar |
| `discard_reason` | varchar null | `reintentos_agotados`, `inactiva_en_listado` o `abandono_por_error` |

`ingestion_run` suma `kind` y `requests`. Los tipos son tres:

- `tramo`: un tramo listado de la nocturna. Son las únicas filas que mueven el
  cursor, junto con las de antes del plan, que no tienen tipo.
- `nocturna`: la corrida nocturna entera. Queda en `running` mientras se vacía
  la cola, para que una frecuente no se cruce.
- `frecuente`: la corrida que solo vacía la cola.

`sync_estados_run` suma `finished_at` y `requests`: la fila se inserta al
empezar y se cierra al terminar.

Hay un índice parcial para la cola:
`(attempts, created_at) WHERE is_processed = false AND discarded_at IS NULL`.

Hay un paso de datos que pasa a terminal las 240 actuales:
`last_error LIKE 'ErrorTransitorioMercadoPublico:%' AND attempts >= 3`.

### 2.3 sync-estados: aplicar por página y etiquetar

- `MercadoPublicoClient.get_tenders` recibe un callback opcional por página.
  `listar_cambios` lo expone y `sincronizar_estados` aplica cada página apenas
  llega. Por página van:
  - `SyncTenderStatusesUseCase.execute`, con estado, cierre, llamado,
    Qdrant y etiquetado;
  - `aplicar_documentos_oficiales`, aislado en su try/except, como hoy.
- Un puerto nuevo en `app/application/services/` reemplaza a `reencolar` en el
  caso de uso. Su implementación en `TenderIngestionService` hace el upsert del
  puntero con estas reglas:
  - **No está en `tender`, sigue publicada y pasa los filtros de cierre vencido y
    región:** `nueva`. Los filtros se extraen de `fetch_tenders_metadata` a una
    función compartida.
  - **Está en `tender`, activa, con `changed_at` posterior a
    `detail_fetched_at` - 5 min, o reabierta:** `actualizar`. El margen va en
    el sentido de bajar de más: un cambio de hasta 5 min antes del pedido pudo
    no salir en ese detalle. Solo pone
    `attempts=0` si la fila venía procesada, y nunca toca `night_retries`.
  - **Pendiente en la cola pero inactiva según el listado:** `discarded_at`
    con motivo `inactiva_en_listado`.
  - **Filas con `discarded_at`:** no se reactivan.
  - **Guarda de escritura:** solo escribe si cambió `api_changed_at` o
    `api_status_code`.
- `sync_estados_run` se inserta al empezar y se cierra al terminar. Si vence el
  tope, queda incompleta con lo listado hasta ahí y cuenta para la racha de
  incompletas: sale con 0 hasta juntar `--incompletas-toleradas` seguidas,
  igual que un listado cortado por 504.

### 2.4 Ingesta

- **Modo `frecuente`** (tope de 100 min, que termina con salida 0):
  - Vacía las filas con `is_processed=false`, `discarded_at IS NULL` y
    `attempts=0` (modo `NUEVAS`), con `nueva` primero.
  - Hace 2 intentos HTTP por detalle.
  - Una fila que falla queda para la noche. Con eso la regla es 1 intento al
    descubrirla y después solo reintentos nocturnos.
- **Modo `nocturna`** (tope de 6 h), en este orden:
  1. **Red de seguridad.** Lista por publicación en tramos de 6 h. Cada tramo
     completo cierra su fila de `ingestion_run` en `ok` y mueve el cursor. Al
     primer tramo incompleto se detiene. Los anexos se aplican después de cada
     tramo, para los códigos que ya están en `tender`.
  2. **Vaciar la cola**, con 3 intentos HTTP por detalle.
  3. **Reintentos.** Una pasada sobre las filas que fallaron antes de que
     empezara esta corrida, con 1 intento HTTP. Cada una gasta un
     `night_retries`. Al llegar a 5 pasa a `discarded_at` con motivo
     `reintentos_agotados`.
  4. **Retención, una vez por semana.** Borra las procesadas de licitaciones
     inactivas de más de 30 días y las descartadas de más de 60.
- **Cortacircuito.** Cuando fallan 27 de los últimos 30 detalles con error
  transitorio, se corta la pasada, igual que con `cuota_agotada`. Las filas que
  no se alcanzaron no gastan intento. Hasta el 2026-10-19 cortaba con 10
  errores seguidos (ver 2.9).
- **Presupuesto.** El cliente cuenta sus peticiones. `--max-peticiones` corta la
  corrida al llegar al tope. El total se guarda en `requests`, junto con las
  llamadas a la API de embeddings.
- **Carrera con sync-estados.** `_marcar_procesada` solo limpia la etiqueta si
  `api_changed_at <= detail_fetched_at`. Si hubo un cambio después de pedir el
  detalle, la fila sigue como `actualizar` y la ingesta no escribe estado,
  cierre ni llamado desde ese detalle.
- `_registrar_fallo` cambia el abandono silencioso de hoy por `discarded_at`
  con motivo `abandono_por_error`.
- `contar_pendientes` usa el mismo filtro que `_pendientes`, y `vaciar_cola`
  mide el avance con `pasada.procesadas`.
- `_parse_to_dto` no reemplaza fechas faltantes por "ahora". Usa la misma guarda
  que `refresh_tender`.
- `get_items_by_tender_id` ordena las partidas, para no detectar falsos cambios
  de texto. Con los vectores por partida, un falso cambio regenera todos.

### 2.5 Otros consumidores de cuota

- **Refresher de hitos.** `RefreshSyncedTenderDatesUseCase` deja de pedir el
  detalle. Compara los hitos con `tender.closing_at` y `published_at`, y mantiene
  fuera el cierre del segundo llamado. El scheduler deja de correr al arrancar
  la API.
- **Tickets.** Cada servicio de Railway ordena `MERCADO_PUBLICO_API_KEYS` de
  forma distinta, para partir de un ticket propio. Es un cambio de variables
  que se hace con confirmación, sin código.

### 2.6 Recuperación de una sola vez

`scripts/recuperar_activas.py` hace estos pasos:

1. Toma las activas con cierre a más de 1 h y `updated_at` anterior al
   2026-10-09 20:00 UTC.
2. Lista por publicación su rango de fechas, unas 300 páginas.
3. Aplica estado y cierre con `SyncTenderStatusesUseCase`.
4. Etiqueta `actualizar` solo las que cambiaron.
5. Las que ya no aparecen como publicadas también quedan como `actualizar`, para
   que su detalle confirme el estado.

Tiene `--dry-run` y `--limite`. No se corre la misma noche que la primera
nocturna después del despliegue.

### 2.7 Consumo esperado

Lo estimó una revisión aparte contra el código, en peticiones al día a
Mercado Público:

| Escenario | Hoy | Con este plan |
|---|---|---|
| Día hábil normal | ~9.800-10.600 | ~7.000-8.500 |
| Día malo de 504 | ~12.000-13.000 | ~10.000 |

La cuota es de 10.000 al día por ticket. Con 2 tickets hay margen, y un tercero
queda de reserva para la recuperación.

Con los vectores por partida de develop, cada licitación nueva cuesta 2 llamadas
a la API de embeddings y ~3,8 textos (2,77 partidas en promedio). Este PR no
cambia ese total, pero lo registra.

Railway pasa de ~6 a ~8-10 h de contenedor al día, con 0,36 GB de memoria. La
diferencia es de menos de un dólar al mes.

### 2.8 Operación

- `AGENTS.md`: no se mergea a `main` entre las 06:00 y las 12:00 UTC (03:00 a
  09:00 de Chile). Un despliegue corta los crons en curso.
- Este PR no debería salir en el mismo release que el spike 2 de matching, para
  poder medir por separado el consumo de cada uno.

### 2.9 Prueba en producción y ajustes (2026-10-13 y 2026-10-14)

Los crons de producción desplegaron desde esta rama desde el 2026-10-13 a las
17:20 UTC. Cada corrida deja una línea `RESUMEN {json}` en el log.

**Por qué fallaba el listado en hora punta.** Se midió en la API una petición
por caso, sin reintentos, entre las 18:22 y las 20:38 UTC del 10-13:

| Página | Éxito | Segundos si responde |
|---|---|---|
| 10 por página | 92 a 100% | ~15 |
| 20 por página | 50 a 75% | ~22 a 25 |
| 50 por página | 0% | — |

Lo que decide el 504 es el tamaño de la página, no el de la ventana: una
ventana de 15 min fallaba igual que una de 2 h. El listado pasó a 10 por
página y se pide de a 4 páginas a la vez después de la primera
(`MERCADOPUBLICO_LISTING_CONCURRENCY`).

**Resultado del 10-14.** sync-estados completó las 22 corridas del día. La más
pesada (15:02 UTC) listó 3.624 cambios en 45 min con 3 páginas a la vez; con 4
debería bajar a ~34. El 504 del listado quedó entre 3 y 7%.

**Ajustes que salieron de la prueba.**

- El 429 del detalle usaba el mismo conteo que los 5xx (2 de día, 3 de noche),
  y una ráfaga del balde de tokens se tomaba por cuota agotada: cortó la
  nocturna con 1.585 pendientes y dos frecuentes. Ahora tiene 4 intentos
  propios, como el listado. Con 2 tickets y ~12.350 peticiones en el día, la
  cuota real alcanzaba.
- Un intento de día era poco: con 17% de 504 en el detalle, ~1.100 nuevas
  esperaron la noche. Ahora son hasta 3 intentos de día (`MAX_INTENTOS_DIURNOS`)
  y después los 5 reintentos nocturnos.
- La red de seguridad nocturna encola como `nueva`, y una corrida que vence el
  tope registra lo que alcanzó a procesar.
- `preparar_destino` crea también la colección `tender_lexical` del spike 2;
  sin ella, la ingesta fallaba en cada licitación con texto nuevo.
- El 10-16 a las 14:02 UTC sync-estados venció el tope de 50 min en la página
  337, con 3.330 cambios aplicados, 504 al 15% y 19,7 s por página (p50).
  Railway lo reportó como caída aunque la ventana de 2 h de la corrida
  siguiente cubría lo que faltó. Se cambiaron tres cosas: el listado se pide de
  a 6 páginas, el tope sube a 55 min y vencerlo cuenta como incompleta en vez
  de salir siempre con 1.
- El 10-19, primer día hábil con esos cambios, sync-estados completó todas las
  corridas, pero la de las 15:03 tardó 53 min (3.868 cambios, 25% de 504 y 500
  en el listado). Con la ventana fija de 2 h cada corrida volvía a listar la
  hora anterior entera. Ahora la ventana va desde el inicio de la última
  corrida completa más 15 min (~1 h 15 en lo normal) y crece sola después de
  una incompleta, sin pasar de `SYNC_ESTADOS_VENTANA_HORAS` (2 h). Una corrida
  que toca el techo de ítems se cierra como incompleta, para que la siguiente
  no arranque desde ella.
- El mismo día la ingesta de las 16:02 se cortó a los 2,8 min por el
  cortacircuito, con 938 pendientes y procesando 1 de cada 3. Con 10 detalles
  a la vez y la API fallando entre el 30 y el 67%, 10 errores seguidos salían
  solos. Ahora corta cuando fallan 27 de los últimos 30.
- El 10-20 sync-estados tuvo dos incompletas seguidas en hora punta (18:00 y
  19:03). Con el máximo de 2 h, la completa siguiente no podía mirar hasta la
  última completa (17:01), y una hora quedó vista solo por corridas que no
  terminaron. El máximo de la ventana pasa a 3 h.
- El mismo día el cortacircuito cortó la pasada de reintentos nocturna con 94
  de 147 detalles en 504, y 130 filas no gastaron su reintento. Esa pasada toma
  justo lo que viene fallando, así que ya no se corta: cada fila tiene su
  límite de 5 noches.
- La frecuente que llega a su tope cierra como `tope` en vez de `failed`. Sale
  con 0 y lo pendiente sigue en la cola.

---

## 3. Desglose de Tareas (Checklist)

### Backend

**Esquema**
- [x] Red: `tests/integration/test_migraciones.py` detecta las columnas nuevas.
- [x] Green: modelos en `tender_model.py` y `sync_estados_run_model.py`, y la
      migración con el paso de datos.

**Cliente**
- [x] Red (respx): el callback se llama una vez por página y en orden.
- [x] Red (respx): los intentos de detalle son configurables.
- [x] Red (respx): el contador de peticiones.
- [x] Green: `mercado_publico_client.py`.

**Puntero**
- [x] Red: `SyncTenderStatusesUseCase` etiqueta `nueva` y `actualizar`.
- [x] Red: descarta las inactivas.
- [x] Red: no reencola sin cambio posterior a `detail_fetched_at`.
- [x] Red: conserva el llamado.
- [x] Red (integración): el upsert con `GREATEST` y la guarda.
- [x] Red (integración): `discarded_at` no se reactiva.
- [x] Green: el puerto, su implementación y el caso de uso.

**sync-estados**
- [x] Red (`Piezas`): aplica por página.
- [x] Red (`Piezas`): los anexos van por página y aislados.
- [x] Red (`Piezas`): la corrida queda registrada cuando vence el tope.
- [x] Green: `scripts/sync_estados.py` y `sync_estados_run_repository.py`.

**Cola de la ingesta**
- [x] Red (integración): el filtro y el orden por modo.
- [x] Red (integración): el cortacircuito.
- [x] Red (integración): `_marcar_procesada` condicional.
- [x] Red (integración): `abandono_por_error`.
- [x] Red (integración): `contar_pendientes` alineado.
- [x] Green: `tender_ingestion_service.py` e `ingesta_compartida.py`.

**Modos de la ingesta**
- [x] Red (`ServicioFalso`): el orden de cada modo.
- [x] Red (`ServicioFalso`): el cursor por tramo y el corte en el primer
      incompleto.
- [x] Red (`ServicioFalso`): los reintentos nocturnos hasta el descarte.
- [x] Red (`ServicioFalso`): el tope del modo frecuente sale con 0.
- [x] Red (`ServicioFalso`): `--modo auto`.
- [x] Green: `scripts/sync_diaria.py`.

**Arreglos menores**
- [x] Red y Green: fechas faltantes en `_parse_to_dto`.
- [x] Red y Green: orden de las partidas. Se ordenan al comparar el texto en
      `_actualizar`, no en `get_items_by_tender_id`: así el texto del embedding
      conserva el orden de la API.

**Refresher de hitos**
- [x] Red: compara con la base sin llamar al cliente.
- [x] Green: `refresh_synced_tender_dates.py` y el scheduler.

**Retención**
- [x] Red (integración): qué se borra y qué no.
- [x] Green: el paso semanal de la nocturna.

**Recuperación**
- [x] Red (fakes): la selección, el etiquetado y `--dry-run`.
- [x] Green: `scripts/recuperar_activas.py`.

**Refactor y documentación**
- [x] Docstrings de `sync_diaria.py` y `sync_estados.py`.
- [x] `AGENTS.md`.
- [x] Este plan.

**Pendiente de este plan**
- [x] Contar las llamadas a la API de embeddings. Van en una columna aparte,
      `ingestion_run.embedding_calls`, porque se cobran por separado.

### Frontend

No aplica.

### Después del merge (con confirmación)

- [ ] Cron de `ingesta-Ptyv`: `0 */2 * * *`.
- [ ] Orden de `MERCADO_PUBLICO_API_KEYS` por servicio.
- [ ] Correr `scripts/recuperar_activas.py` de noche.
- [ ] Revisar durante 48 h:
  - que la nocturna cierre `ok`;
  - que haya una fila por hora en `sync_estados_run` en día hábil;
  - que la demora de entrada baje de 17 h;
  - el valor de `requests` por corrida.

---

## 4. Plan de Verificación y Pruebas

```bash
# Backend, desde monorepo/backend con .venv activo y `supabase start`
pytest
python -m scripts.migraciones
alembic heads   # una sola línea

# Corridas locales
python -m scripts.sync_estados --ventana-horas 1
python -m scripts.sync_diaria --modo frecuente --limite 50
python -m scripts.sync_diaria --modo nocturna
```

En producción, después del despliegue, se revisan con el MCP de Railway y el de
Supabase:

- los logs de la primera corrida de cada modo;
- `ingestion_run` y `sync_estados_run`;
- la cola de `tender_metadata` agrupada por `pending_reason` y `discarded_at`.
