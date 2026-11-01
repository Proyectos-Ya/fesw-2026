# Plan Técnico: #314, HU-22, mapa de las direcciones de entrega de mi zona

**Issue asociada**: Refs #314  
**Estado**: Implementado; falta la prueba con datos reales (§6)  
**Fecha**: 2026-10-28  
**Tareas**: [task.md](./task.md)

---

## 1. Contexto y objetivo

HU-22 agrega una vista "Mapa de licitaciones" donde el representante ve, en su
zona, dónde hay que entregar lo que piden las licitaciones abiertas. Los
criterios están en la issue; aquí se numeran del 1 al 8 en el orden en que
aparecen.

La dirección de entrega ya se guarda desde #294 (`tender.delivery_address`),
pero es texto libre y sin comuna (p. ej. `"Yerbas Buenas #915"`). Para ponerla
en un mapa hacen falta coordenadas, y hoy no existen en ninguna parte del
sistema. El grueso de esta historia es obtenerlas.

**Fuera de alcance** (además de lo que dice la issue):

- Geocodificar licitaciones cerradas. El mapa muestra solo las abiertas
  (decisión 3).
- Llenar `delivery_address` de las licitaciones existentes: se completa cuando
  la ingesta vuelve a bajar su detalle (decisión 4 de #294).
- Filtrar por comuna o provincia dentro de la región.

## 2. Lo que ya existe

- **Criterio 7 ya está cumplido por #294.** `formatDeliveryAddress`
  (`frontend/src/features/matches/utils/entrega.ts`) devuelve "Dirección de
  entrega no disponible" sin dato, y `DeliveryInfo.tsx` lo muestra en la ficha.
  Está probado en `TenderDetailView.test.tsx` y `utils/__tests__/entrega.test.ts`.
  Aquí solo se verifica.
- **Ubicación del organismo.** `buyer_institution` tiene `region_id` (requerido)
  y `comuna_id` (nullable, resuelto por `resolve_comuna` en
  `app/shared/comunas.py`). `TenderRepository._to_entity` ya arma
  `region`, `province` y `commune`, y `search_tenders` ya filtra por región con
  esos joins.
- **Zona de la empresa.** `supplier.regions` es una lista de nombres del
  wizard ("Metropolitana", "O'Higgins"), no canónicos. Se normalizan con
  `normalize_region_name` (`app/shared/regions.py`) en el backend y con
  `toSearchRegion` (`frontend/src/features/search/data/profileRegions.ts`) en
  el frontend. En la UI se lee con `useCompany()`.
- **Patrones a copiar.**
  - Cliente HTTP con puerto y settings: `company_lookup_service.py` +
    `http_company_lookup_service.py` + `company_lookup_*` en `config.py`.
  - Tarea periódica en proceso: `MilestoneRefreshScheduler`, cableado en
    `app/main.py` y `bootstrap/runners.py`.
  - Endpoint de listado con 422/503: `GET /tenders/search` en `routers/tender.py`.
  - Error con reintento en la UI: `SavedTendersList.tsx`.
- **Nada de mapas en el frontend**: no hay librería, ni `next/dynamic`, ni
  coordenadas de regiones.
- Cabeza de Alembic: `e7123e26c0be`.

## 3. Cambios en BD

Una migración encadenada tras `e7123e26c0be`. Todo es nullable o tabla nueva,
así que la versión anterior del backend lo ignora durante el despliegue.

**Columnas en `tender`:**

| Columna | Tipo | Significado |
| --- | --- | --- |
| `delivery_lat` | double precision | Latitud del punto de entrega |
| `delivery_lng` | double precision | Longitud |
| `delivery_geo_precision` | text | `direccion`, `comuna` o `no_encontrada` |
| `delivery_geocoded_at` | timestamp | Cuándo se intentó. `NULL` = pendiente |

Índice parcial `ix_tender_geocodificacion_pendiente` sobre `(closing_at)` con
`WHERE delivery_address IS NOT NULL AND delivery_geocoded_at IS NULL`: la cola
es una fracción mínima de la tabla, y el scheduler la recorre por cierre. Se
crea sin `CONCURRENTLY`, como los demás índices del repositorio: bloquea las
escrituras de `tender` los segundos que tarda en recorrerla.

**Tabla `geocoding_cache`:** `query` (text, PK, la consulta normalizada),
`lat`, `lng` (nullable: `NULL` = Nominatim no encontró nada), `geocoded_at`.
Los organismos repiten la misma dirección en muchas licitaciones, y la política
de uso de Nominatim pide no repetir consultas. RLS la activa el event trigger
`ensure_rls` del panel, como en las otras tablas nuevas.

## 4. Backend

- **Puerto** `app/application/services/geocoding_service.py`:
  `IGeocodingService.geocode(query) -> GeoPoint | None`. `None` es "no
  encontrado"; la caída del servicio se lanza como `GeocodingUnavailable`.
- **Implementación** `app/infrastructure/services/geocoding/nominatim_geocoding_service.py`
  con `httpx`, igual que el lookup de empresas: `format=jsonv2`,
  `countrycodes=cl`, `limit=1` y un `User-Agent` con correo de contacto, que
  exige la política de Nominatim.
- **Caso de uso** `GeocodePendingTendersUseCase`. Toma un lote de pendientes
  abiertas y, por cada una:
  1. Consulta `"<dirección>, <comuna>, <región>, Chile"` (caché primero). Si
     hay resultado, precisión `direccion`.
  2. Si no, `"<comuna>, <región>, Chile"`, precisión `comuna`. La UI lo
     muestra como ubicación aproximada.
  3. Sin resultado o sin comuna, `no_encontrada`, sin coordenadas: no se
     inventa una ubicación (fuera de alcance de la issue).
  Si Nominatim está caído, la licitación queda pendiente y se reintenta en la
  vuelta siguiente.
- **Scheduler** `GeocodingScheduler`, como `MilestoneRefreshScheduler`. Un
  lote lleno sigue sin esperar el intervalo, porque queda cola. El límite de
  Nominatim lo pone `ThrottledGeocodingService`, que envuelve al cliente y
  separa las llamadas reales por al menos 15 s (decisión 7); los de la caché no
  llegan a él.
- **Settings**, como `company_lookup_*`: `geocoding_provider` (default
  `"none"`, apagado en local y en tests), `geocoding_contact_email`,
  `geocoding_interval_seconds`, `geocoding_batch_size`. Activarlo en Railway
  es poner `GEOCODING_PROVIDER=nominatim` y el correo.
- **Ingesta.** Si `_aplicar_entrega` cambia la dirección, también borra el
  punto guardado (era de la dirección anterior) y pone `delivery_geocoded_at`
  en `NULL` para que se vuelva a geocodificar. Sigue la regla de #294: solo
  SQL, sin mover `updated_at` ni tocar Qdrant.
- **Repositorio.** `SqlTenderLocationRepository` implementa dos puertos chicos,
  `ITenderGeocodingRepository` (cola y caché) e `ITenderMapRepository` (el
  mapa), en vez de ensanchar `ITenderRepository`, igual que
  `ITenderStatusSyncRepository`.
- **Endpoint** `GET /tenders/map?region=<nombre>`, antes de `/{tender_id}`,
  con `summary`, `response_model` y `tags`.
  - `GetTendersMapUseCase` normaliza la región; una desconocida da 422.
  - Método nuevo del repositorio `list_open_with_location(region_id, limit)`:
    estado publicada, `closing_at` futuro, región del organismo y coordenadas
    no nulas. Devuelve entidades de dominio, como pide la nota del puerto.
  - Respuesta `TenderMapResponse{region, items, total, is_truncated}`, con
    `id, name, buyer_name, delivery_address, closing_at, lat, lng, precision`
    por ítem. El tope es 3.000 marcadores (decisión 6).
  - Un error de base de datos da 503, como en `/search`. Es lo que la UI
    traduce en el criterio 8.

## 5. Frontend

- **Dependencias nuevas** (pnpm, versión exacta): `leaflet` 1.9.4,
  `react-leaflet` 5.0.0, `react-leaflet-cluster` 4.1.3, y de desarrollo
  `@types/leaflet` 1.9.22 y `@types/leaflet.markercluster` 1.5.6 (los tipos de
  `react-leaflet-cluster` lo necesitan). Teselas de OpenStreetMap con su
  atribución; no piden key.
- **Ruta y menú.** `src/app/(app)/mapa/page.tsx` de una línea, y
  `{ icon: "map", label: "Mapa de licitaciones", href: "/mapa" }` en
  `NAV_ITEMS` de `Sidebar.tsx` (criterio 1).
- **Feature** `src/features/tender-map/`:
  - `services/tenderMapService.ts`: `getTendersMap(region)` con `apiFetch`.
  - `hooks/useTenderMap.ts`: carga, error, datos y `retry`, como
    `useSavedTenders`.
  - `data/regionCenters.ts`: centro y zoom de las 16 regiones, con las claves
    de `SEARCH_REGIONS`. Centra el mapa aunque no haya marcadores (criterios 1,
    5 y 6).
  - `TenderMapView`: la zona inicial es la primera región de la empresa,
    normalizada con `toSearchRegion`. Un `<select>` nativo cambia la zona
    (criterio 5). Sin empresa o sin regiones, pide elegir una y enlaza a
    `/empresa`, o a `/perfil` si no hay empresa (criterio 2).
  - `TenderMap`, cargado con `next/dynamic` y `ssr: false` porque Leaflet usa
    `window`. Usa `MarkerClusterGroup` (criterio 4), un `divIcon` propio para
    no depender de las rutas de las imágenes de Leaflet, y `flyTo` al cambiar
    de zona.
  - `TenderMapSummary`, el popup: nombre, organismo, dirección, cierre con
    `formatClosingDate` y enlace a `/matches/{id}` (criterio 3). Con precisión
    `comuna` agrega "Ubicación aproximada (comuna del organismo)".
  - Estado vacío que sugiere otra zona (criterio 6), y "No se pudo cargar el
    mapa" con Reintentar, que cubre tanto la API como la carga del módulo del
    mapa (criterio 8).

## 6. Plan de pruebas

El detalle, tarea por tarea y en orden TDD, está en [task.md](./task.md).

```bash
# Backend, desde monorepo/backend (en contenedor), con `supabase start`
pytest
python -m scripts.migraciones   # una sola cabeza

# Frontend, desde monorepo/frontend
pnpm run test && pnpm run lint && pnpm run build
```

jsdom no tiene canvas, así que las pruebas de Vitest mockean `TenderMap`. La
agrupación y el centrado se prueban a mano.

Resultado tras sincronizar con develop (2026-11-01), que trajo la HU-31 (modo
oscuro y accesibilidad), retroalimentación de usuario y cuatro migraciones:

- **Backend**: 3.492 pruebas unitarias en verde. Las 22 de integración y API del
  mapa y de migraciones, también. `alembic upgrade head` aplica las 57
  migraciones sobre una base limpia, `alembic check` no detecta deriva entre
  modelos y migraciones, y queda **una sola cabeza** (`7c1fa735a495`, repuntada
  a `a3f9c8e1d402`).
- **Frontend**: 1.346 pruebas en 165 archivos, todas en verde. `eslint` da 0
  errores y 29 advertencias, ninguna en archivos de esta rama. `next build`
  compila, pasa TypeScript e incluye `/mapa`.
- Dos adaptaciones que exigió el merge: registrar el ícono `map`, que el
  `Icon.tsx` nuevo de develop ya no resolvía solo —el ítem del menú quedaba sin
  ícono, en silencio—, y cambiar el `bg-white` del selector de zona por
  `bg-surface-card`, que en modo oscuro salía blanco.
- **Pendiente de modo oscuro**: las teselas del mapa son las claras de
  OpenStreetMap, así que el mapa sigue claro con el tema oscuro. Cambiarlo
  requiere otro proveedor de teselas.

Resultado tras el bloque 7 (2026-11-01): la suite de CI da **3.249 pasadas y 0
fallidas**, las 17 de integración y API del mapa pasan, y `scripts.migraciones`
sigue dando una sola cabeza (`7c1fa735a495`). El frontend no cambió en esa
ronda.

Resultado de la tarea 6.1 (2026-10-28, Postgres local en Docker, sin `.env`):

- **Backend.**
  - La suite de CI (`pytest tests/unit/ -m "not integration and not network"`)
    da 3243 pasadas y 0 fallidas.
  - Las pruebas nuevas de integración y de API pasan: `test_migraciones.py`
    (5), `test_tender_location_repository.py` (10), `test_tender_map_router.py`
    (6) y `test_tender_router.py` (33).
  - `alembic upgrade`, `check`, `downgrade -1`, `upgrade` y `check` funcionan
    de punta a punta, y queda una sola cabeza (`7c1fa735a495`).
  - La suite completa no terminó en esta máquina: las de integración recrean
    el esquema en cada prueba y avanzaban a unas 9 por minuto. Antes de
    cortarla fallaron dos pruebas de anexos que este cambio no toca.
    `test_dos_empresas_que_suben_lo_mismo_lo_comparten_con_una_tercera` falla
    porque la base de desarrollo local no tiene `attachment_extraction`.
    `test_un_admin_pide_la_url_y_la_lista_refleja_el_cupo` es una de las 7 que
    #294 ya registra como fallidas en develop.
- **Frontend.**
  - `pnpm run test` da 1166 de 1167. La que falla es
    `useTenderExport.test.ts`, que es de otra feature y pasa sus 7 pruebas al
    correrla sola: depende del tiempo y falla con la máquina cargada.
  - `pnpm run lint` da 0 errores y 26 advertencias, las mismas de develop.
  - `pnpm run build` compila e incluye `/mapa`.

### Prueba manual

Con `GEOCODING_PROVIDER=nominatim`, geocodificar un lote real y recorrer
`/mapa`: los 8 criterios, forzando un 503 para el 8.

Resultado parcial (2026-10-28). En esta máquina no se puede iniciar sesión en
el navegador (Supabase Auth local no levanta), así que la vista se montó sola
con Vite, como el fixture de `proposal.spec.ts`. La API y la empresa eran dobles
y Leaflet corría de verdad, con teselas reales de OpenStreetMap. En el
navegador integrado:

- Criterio 1: el mapa se centra en la primera región del perfil
  ("Metropolitana" se envía como "Metropolitana de Santiago").
- Criterio 2: sin regiones pide elegir una zona y enlaza a `/empresa`; sin
  empresa enlaza a `/perfil`, y no hace ningún pedido.
- Criterio 3: el popup muestra nombre, organismo, dirección y cierre, con
  enlace a `/matches/{id}`.
- Criterio 4: cinco licitaciones cercanas se ven como un "5" y se separan al
  hacer clic o zoom.
- Criterio 5: al cambiar a Los Lagos el mapa se recentra y pide la región
  nueva.
- Criterio 6: Ñuble vacía muestra el aviso y sugiere otra zona.
- Criterio 8: un 503 muestra "No se pudo cargar el mapa" y Reintentar vuelve a
  pedir y carga.
- En celular (375 px) no hay scroll horizontal y la consola no muestra errores.

**Pendiente**, con el backend desplegado y `GEOCODING_PROVIDER=nominatim`:
geocodificar un lote real y recorrer `/mapa` con sesión real. No se probó
contra Nominatim real porque el `User-Agent` necesita el correo de contacto
del equipo. El criterio 7 lo cubre #294 (§2).

## 7. Despliegue y rollback

- La migración va en el mismo PR, es compatible hacia atrás y se comprueba con
  `python -m scripts.migraciones` antes de abrir y antes de mergear.
- Desplegar en dev test aplica la migración sobre la base de producción,
  porque comparten base.
- La geocodificación queda apagada hasta poner `GEOCODING_PROVIDER` en
  Railway. Hasta entonces el mapa sale vacío, sin errores.
- **Rollback.** Revertir el PR sin el commit de la migración. El `downgrade`
  borra las cuatro columnas y la tabla, y se corre solo después de revertir el
  código.

### Riesgos

1. **Precisión.** Nominatim es aproximado con direcciones chilenas. El
   respaldo por comuna y la marca "ubicación aproximada" lo dejan visible.
2. **Cola inicial lenta.** A 4 consultas por minuto son 5.760 al día, así que
   una cola inicial de varios miles tarda cerca de un día. Solo las
   direcciones distintas gastan cuota, y la caché acorta el resto.
3. **Una sola instancia.** El scheduler, como los demás, asume una sola
   instancia de la API; con dos se duplicarían llamadas a Nominatim.

## 8. Decisiones (2026-10-28)

1. **Nominatim (OpenStreetMap)** para geocodificar, sin key ni costo, con
   caché propia y respaldo por comuna.
2. **Leaflet + react-leaflet + react-leaflet-cluster** en el frontend.
3. **Solo licitaciones abiertas**: estado publicada y cierre futuro.
4. **Se geocodifica en segundo plano**, no en la ingesta ni al abrir el mapa:
   la ingesta no se frena y el mapa responde con una sola consulta SQL.
5. **La zona es la región del organismo**, igual que en la búsqueda. El punto
   geocodificado no decide la región.
6. **Tope de 3.000 marcadores por zona** (2026-11-01, revisando el primero de
   500). El criterio 1 pide un marcador por licitación, y un tope que se
   alcanza esconde la mayoría justo en la región con más licitaciones. El
   corpus vigente completo es de ~9.000 en todo Chile y no crece (spike 2.1),
   así que con 3.000 ninguna región se acerca. Se mantiene un tope porque la
   consulta no pagina; cuando recorta, `is_truncated` lo dice en la UI.

   Medido en el navegador el 2026-11-01, con el mapa montado solo sobre Vite en
   modo desarrollo (sin minificar) y en escritorio:

   | | 500 marcadores | 3.000 marcadores |
   |---|---|---|
   | Dibujo estable desde la respuesta | 762 ms | 1.327 ms |
   | Nodos en el DOM | 5 | 14 |
   | Bloqueo del hilo principal al hacer zoom | ≤ 5 ms | ≤ 5 ms |
   | Memoria del heap | — | 66 MB |

   La agrupación mantiene el DOM en unos pocos nodos pase lo que pase, y las
   etiquetas de los grupos suman exactamente 3.000: no se pierde ninguno. El
   peso en la red son ~0,9 MB de JSON, unos 130 KB comprimidos. **Falta medirlo
   en un celular de gama baja**, que es donde podría notarse.
7. **El ritmo es de 4 consultas por minuto, no de una por segundo**
   (2026-11-01). El máximo de 1/s que encabeza la política de Nominatim es
   para uso interactivo; un proceso que consulta a intervalos regulares y
   corre más de un día cae en el tramo de 4 por minuto, y pasarse hace que
   bloqueen al proyecto sin que nada falle de forma visible. Configurable con
   `GEOCODING_MIN_INTERVAL_SECONDS`, para poder subirlo contra una instancia
   propia. Verificado contra el Nominatim real el 2026-11-01: encuentra la
   dirección del fixture (`"Yerbas Buenas #915, Ancud, Los Lagos, Chile"`) a
   nivel de calle, no encuentra una dirección mal escrita como
   `"SERVIU REGION DE AYSEN RAMON FREIRE 5"` —que entonces cae al respaldo por
   comuna— y reconoce tanto las comunas como nuestros nombres canónicos de
   región. El `#` de las direcciones chilenas no le estorba: con y sin él
   devuelve el mismo punto, así que no se limpia.
8. **No se encolan las licitaciones sin región informada** (2026-11-01). La
   ingesta guarda `region_id = 0` ("Desconocida") cuando Mercado Público no la
   informa. El mapa filtra por las 16 reales, así que esas licitaciones no
   pueden verse nunca: geocodificarlas gastaba cuota y mandaba la palabra
   "Desconocida" dentro de la consulta.
