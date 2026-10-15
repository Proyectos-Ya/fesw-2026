# Plan Técnico: Retención de licitaciones cerradas

**Issue asociada**: Refs #306  
**Estado**: Implementado, pendiente de PR  
**Fecha**: 2026-10-13  
**Depende de**: la rama 305 (corrida nocturna de `sync_diaria.py`, `purgar_cola`
y la migración `2510718f486e`). Mientras la 305 no entre en `develop`, las dos
ramas de este plan van apiladas sobre ella: `306-indices-tender-id` sale de la
305 y `306-retencion-licitaciones-cerradas` sale de la de índices.  

---

## 1. Contexto y Objetivo

Chiripa guarda en Postgres todas las licitaciones que descarga, también las
cerradas. Lo medido en producción el 2026-10-13, con el corpus empezando el
2026-09-26:

| Tabla | Filas | Tamaño |
|---|---|---|
| `tender_item` | ~104.000 | 31 MB |
| `tender` | ~41.500 | 27 MB |
| `tender_metadata` | ~41.600 | 9 MB |
| Resto de la base | | ~15 MB |

- Entraron 20.912 licitaciones en los últimos 7 días, unas 3.000 por día. Con
  ~1,4 KB por licitación entre la fila y sus partidas, la base crece unos
  130 MB al mes.
- 18.776 licitaciones cerraron hace más de 7 días y ninguna tiene uso. Son
  ~11 MB de partidas y ~8,7 MB de filas de `tender`, sin contar índices.
- Ninguna licitación que cerró hace más de 7 días tiene uso según la lista de
  2.2, ni filas en `tender_interaction`. Las que tienen uso son todas activas o
  recientes.

El objetivo es borrar cada noche las licitaciones no activas que cerraron hace
más de N días y que nadie usó, de Postgres y de las tres colecciones de Qdrant.
N se configura por entorno y por defecto es 7.

---

## 2. Decisiones Técnicas y Arquitectura

### 2.1 Qué se borra

Una licitación es borrable si cumple todo esto:

- Su estado no está en `ACTIVE_TENDER_STATUSES`.
- `closing_at < ahora - N días`.
- No tiene filas en ninguna tabla de uso (2.2).

Se usa `closing_at` y no la fecha en que cambió de estado. Una desierta o
cancelada antes de su cierre original se conserva hasta N días después de ese
cierre, lo que es más conservador y no necesita columna nueva.

Si una licitación borrada reabre (segundo llamado), sync-estados no la conoce,
la ve activa con cierre futuro y deja el puntero `NUEVA`. La ingesta la vuelve a
bajar entera. Si aparece de nuevo en el listado ya cerrada, queda como
`INACTIVA` y no se baja. No hace falta tocar la ingesta.

### 2.2 Qué cuenta como uso

Medido en la base (`pg_constraint`), 30 tablas apuntan a `tender`. Se dividen
así:

**Uso de una persona: la licitación se conserva.**

| Tabla | `ON DELETE` en la base |
|---|---|
| `saved_tender` | NO ACTION |
| `kanban_card` | NO ACTION |
| `tender_milestone` | NO ACTION |
| `quotation` | NO ACTION |
| `deep_analysis` | NO ACTION |
| `tender_chat_sessions`, `tender_chat_messages`, `tender_chat_documents` | NO ACTION |
| `proposal_drafts` | CASCADE |
| `tender_share_link` | CASCADE |
| `tender_milestone_document`, `tender_milestone_attachment` | CASCADE |
| `attachment_file` | CASCADE |
| `extension_fetch_job` | CASCADE |

Las que tienen CASCADE también cuentan como uso. Si no se revisaran, el borrado
se llevaría por delante un borrador de propuesta o un archivo subido.

**Generadas por el sistema: se borran con la licitación.**

| Tabla | `ON DELETE` | Cómo se borra |
|---|---|---|
| `tender_item` | NO ACTION | DELETE explícito antes de `tender` |
| `matching_result` | NO ACTION | DELETE explícito |
| `notification` | NO ACTION | DELETE explícito |
| `tender_ai_analysis` | NO ACTION | DELETE explícito |
| `calendar_oauth_state` | NO ACTION | DELETE explícito (estado temporal del OAuth) |
| `tender_attachment`, `tender_attachment_item`, `attachment_extraction`, `attachment_processing_job`, `tender_digest`, `export_job` | CASCADE | solo |
| `ranking_impression`, `tender_interaction`, `matching_shadow_score`, `attachment_priority_shadow` | CASCADE | solo |
| `capability_answer` | SET NULL | solo, la respuesta se conserva |

`tender_interaction` no cuenta como uso (decidido el 2026-10-13). Es telemetría
del ranking (clics, aperturas) y se borra con la licitación por CASCADE. Al
medir, ninguna licitación borrable tenía filas ahí.

`extension_fetch_job` cuenta como uso por precaución, aunque hoy ningún código
crea esas tareas. Si se activa, revisar si las crea una persona o el sistema.

`tender_metadata` no tiene clave foránea (se une por `code`). La poda semanal de
la cola (`purgar_cola`) ya borra sus filas procesadas de licitaciones no
activas, así que no hace falta tocarla.

### 2.3 Qdrant

Hay tres colecciones de licitaciones, y hoy se tratan distinto:

| Colección | Repositorio | ¿Se borra al cerrar? |
|---|---|---|
| `tenders` | `QdrantTenderRepository` | Sí. sync-estados y `MarkExpiredTendersUseCase` llaman a `delete_many`, y hay un barrido diario por payload |
| `tender_items` | `QdrantTenderItemVectorRepository` | No |
| `tender_lexical` | `QdrantLexicalTenderRepository` | No |

`tender_items` y `tender_lexical` solo borran puntos cuando la ingesta reindexa
una licitación o cuando `RankTendersUseCase` (paso 3.3.1) encuentra un punto sin
fila en SQL. Su payload `status_code` tampoco se actualiza (`set_payloads` solo
existe en `tenders`), así que una cerrada sigue diciendo `publicada`, pasa el
filtro de estado del matching y ocupa un cupo de candidata hasta que SQL la
descarta. Es el mismo problema que `mark_expired_tenders.py` ya resolvió para
`tenders`.

Decisión: sacar las cerradas de las tres colecciones **al cerrar**, no al
retener. Concretamente:

1. Agregar `delete_many` a `ITenderItemVectorRepository` e
   `ILexicalTenderRepository` (y sus implementaciones Qdrant, por filtro de
   `tender_id`).
2. sync-estados y `MarkExpiredTendersUseCase` borran de las tres colecciones lo
   que hoy borran solo de `tenders`.
3. El borrado por retención también llama a las tres, por si quedó algo de
   antes. Borrar un punto que no existe no es un error.
4. Una purga única extiende `scripts/purgar_vectores_inactivos.py` a las tres
   colecciones, para limpiar lo acumulado hasta hoy.

Antes de la purga hay que medir cuántos puntos tiene cada colección (la
credencial de Qdrant de producción está en Railway, no en el repo).
`purgar_vectores_inactivos --dry-run` sirve si se extiende para contar las tres.

Con Qdrant limpio al cerrar, el paso 3.3.1 de `RankTendersUseCase` sigue
sirviendo de red para los huérfanos que deje un borrado a medias.

### 2.4 Dónde corre

Un caso de uso nuevo, `PurgarLicitacionesCerradasUseCase`, en
`app/application/use_cases/`. Depende de:

- `ITenderRepository` (o una interfaz nueva `ITenderRetentionRepository`) con
  `ids_borrables(corte: datetime, limite: int) -> list[UUID]` y
  `borrar(ids: list[UUID]) -> int`.
- Las tres interfaces de vectores.

Lo llama la corrida **nocturna** de `scripts/sync_diaria.py`, al final, después
de vaciar la cola y antes de la poda semanal. Corre todas las noches. Si falla,
la corrida no falla: imprime un aviso, igual que la poda de la cola, y la noche
siguiente lo vuelve a intentar.

Orden por lote, igual que el resto de la ingesta: **Qdrant antes que SQL**. Si
SQL falla después, la licitación sigue en SQL, sigue siendo borrable y la noche
siguiente se repite. Al revés quedaría un punto que nadie volvería a señalar.

### 2.5 El borrado en SQL

Lotes de 1.000 ids, cada uno en su propia transacción
(`SqlTenderRetentionRepository.borrar`):

1. `SELECT id FROM tender WHERE id = ANY(:ids) ORDER BY id FOR UPDATE`. Un
   INSERT que referencie una de esas filas toma `FOR KEY SHARE` y queda
   esperando hasta que el lote termine, así que desde ahí no aparece uso nuevo.
2. Otra sentencia vuelve a revisar las condiciones de 2.1 sobre las filas
   bloqueadas. En READ COMMITTED cada sentencia toma su propio snapshot y ve el
   uso que alguien confirmó entre la selección y el bloqueo. Dentro de la
   sentencia del bloqueo, la subconsulta seguiría viendo el snapshot viejo.
3. Para las confirmadas: DELETE en `tender_item`, `matching_result`,
   `notification`, `tender_ai_analysis` y `calendar_oauth_state`, y después en
   `tender`. El resto cae por CASCADE.

Una licitación que alguien usó entre medio se conserva entera, con sus
partidas. Lo cubre `test_uso_entre_la_seleccion_y_el_borrado_conserva_todo`.

Las tres listas de tablas (uso, sistema sin cascada, sistema en cascada) están
en `sql_tender_retention_repository.py`.
`test_toda_tabla_que_apunta_a_tender_esta_clasificada` falla si aparece una
tabla nueva con clave foránea a `tender` que no esté en ninguna.

**Índices.** En la base faltaban índices sobre la columna `tender_id` de
`tender_item`, `matching_result`, `export_job` y `calendar_oauth_state`. Sin
ellos, cada DELETE de `tender` revisa esas tablas completas para comprobar la
clave foránea, y el `DELETE FROM tender_item WHERE tender_id = ANY(...)` también
recorre la tabla entera. La migración `3e7ba2172180`, en la rama
`306-indices-tender-id`, los agrega con `CREATE INDEX CONCURRENTLY` dentro de
`autocommit_block()`, y los cuatro modelos declaran `index=True`.

Va en un PR propio y previo para que no se acumule con otras migraciones en una
rama larga (`AGENTS.md` §3). Revisa `2510718f486e`, la migración de la 305, así
que se mergea después de ella.

### 2.6 Configuración

En `app/config.py`, junto a la configuración de sync-estados:

```python
retencion_cerradas_dias: int | None = Field(default=7, ge=1)
```

Se fija en Railway con `RETENCION_CERRADAS_DIAS`. Sin la variable son 7. Vacía,
`off`, `none` o `no` apagan el borrado: la API comparte esta configuración, y
una variable vacía no debe impedir que arranque. `ge=1` rechaza 0 o negativos,
que borrarían licitaciones recién cerradas; ahí sí falla el arranque, a
propósito. El script acepta `--retencion-dias` (también mínimo 1) para una
corrida local.

### 2.7 Efectos visibles

- El filtro "Cerradas" del buscador solo muestra las que cerraron hace menos de
  N días y las que tienen uso. Es lo acordado en la issue.
- Nada más del frontend lee licitaciones cerradas sin uso. Verificarlo con
  `grep` sobre los servicios de `features/` antes de cerrar el plan.

### 2.8 Estado `proveedor_seleccionado`

En la base hay 4.684 licitaciones con estado `proveedor_seleccionado`, que no
está en `TENDER_STATUS_CODE_BY_ID`. No afecta la retención, porque no es activo
y se borra igual que una cerrada. Se deja anotado porque el filtro de cerradas
del buscador no lo incluye.

---

## 3. Desglose de Tareas (Checklist)

Antes de tocar el esquema o escribir SQL: invocar las skills `supabase` y
`supabase-postgres-best-practices` (ver `CLAUDE.md`).

### Backend

- [x] Confirmar la decisión sobre `tender_interaction` (2.2).
- [x] Migración (rama `306-indices-tender-id`): índices sobre `tender_id` en `tender_item`, `matching_result`,
      `export_job` y `calendar_oauth_state`, con `CONCURRENTLY`. Ajustar los
      modelos. `python -m scripts.migraciones` con una sola cabeza.
- [x] Red: tests de `delete_many` en los repositorios de `tender_items` y
      `tender_lexical`.
- [x] Green: implementar `delete_many` en las dos interfaces y sus repositorios.
- [x] Red: sync-estados y `MarkExpiredTendersUseCase` borran de las tres
      colecciones.
- [x] Green: inyectar los dos repositorios nuevos en esos casos de uso y en sus
      scripts.
- [x] Red: tests del repositorio de retención contra Postgres local. Casos:
      cerrada vieja sin uso (se borra con sus partidas, resultados y
      notificaciones), cerrada vieja con cada tipo de uso de 2.2 (se conserva),
      cerrada reciente (se conserva), publicada con cierre vencido (se
      conserva, la cierra `MarkExpired` primero), uso agregado entre la
      selección y el borrado (no pierde partidas).
- [x] Green: `ids_borrables` y `borrar` por lotes.
- [x] Red: tests del caso de uso con dobles. Qdrant antes que SQL, las tres
      colecciones, `None` en la configuración no borra nada.
- [x] Green: `PurgarLicitacionesCerradasUseCase`.
- [x] Agregar `retencion_cerradas_dias` a `app/config.py` y
      `--retencion-dias` al script.
- [x] Llamarlo al final de la corrida nocturna de `sync_diaria.py`, con aviso
      en vez de fallo. Lo borrado queda en el log de la corrida; no hay columna
      en `ingestion_run` y agregarla sería otra migración.
- [x] Extender `scripts/purgar_vectores_inactivos.py` a las tres colecciones,
      con `--dry-run` que cuente por colección.

### Frontend

- [x] Ninguna tarea. Lo que podría apuntar a una licitación borrada se conserva
      (guardadas, links compartidos) o se borra con ella (notificaciones,
      resultados de matching).

### Después del merge (con confirmación)

- [ ] Medir los puntos de las tres colecciones de Qdrant de producción
      (`purgar_vectores_inactivos --dry-run --confirmar-produccion`).
- [ ] Correr la purga única de Qdrant.
- [ ] Revisar el log de la primera corrida nocturna: ~18.800 licitaciones
      borradas o más.
- [ ] Medir el tamaño de `tender` y `tender_item` una semana después.
- [ ] No mergear a `main` entre las 06:00 y las 12:00 UTC (`AGENTS.md` §3).

---

## 4. Plan de Verificación y Pruebas

```bash
# Backend, desde monorepo/backend con .venv activo y `supabase start`
pytest
python -m scripts.migraciones

# Corrida local de la nocturna con un plazo corto
python -m scripts.sync_diaria --modo nocturna --limite 100 --retencion-dias 1

# Purga de Qdrant, solo contando
python -m scripts.purgar_vectores_inactivos --dry-run
```

Consulta de control en la base, antes y después de la corrida:

```sql
SELECT s.code, count(*)
  FROM tender t JOIN tender_status s ON s.id = t.status_id
 WHERE t.closing_at < now() - interval '7 days'
 GROUP BY s.code;
```
