# Plan Técnico: #314, HU-22, mapa de las direcciones de entrega de mi zona

**Issue asociada**: Refs #314  
**Estado**: En revisión  
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

Índice parcial `ix_tender_geocodificacion_pendiente` sobre `(id)` con
`WHERE delivery_address IS NOT NULL AND delivery_geocoded_at IS NULL`: la cola
es una fracción mínima de la tabla.

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
- **Scheduler** `GeocodingScheduler`, como `MilestoneRefreshScheduler`, espera
  al menos 1 s entre llamadas reales (límite de Nominatim; los aciertos de la
  caché no esperan).
- **Settings**, como `company_lookup_*`: `geocoding_provider` (default
  `"none"`, apagado en local y en tests), `geocoding_contact_email`,
  `geocoding_interval_seconds`, `geocoding_batch_size`. Activarlo en Railway
  es poner `GEOCODING_PROVIDER=nominatim` y el correo.
- **Ingesta.** Si `_aplicar_entrega` cambia la dirección, también pone
  `delivery_geocoded_at` en `NULL` para que se vuelva a geocodificar. Sigue la
  regla de #294: solo SQL, sin mover `updated_at` ni tocar Qdrant.
- **Endpoint** `GET /tenders/map?region=<nombre>`, antes de `/{tender_id}`,
  con `summary`, `response_model` y `tags`.
  - `GetTendersMapUseCase` normaliza la región; una desconocida da 422.
  - Método nuevo del repositorio `list_open_with_location(region_id, limit)`:
    estado publicada, `closing_at` futuro, región del organismo y coordenadas
    no nulas. Devuelve entidades de dominio, como pide la nota del puerto.
  - Respuesta `TenderMapResponse{region, items, total, is_truncated}`, con
    `id, name, buyer_name, delivery_address, closing_at, lat, lng, precision`
    por ítem. El tope es 500 marcadores, como el máximo de `/search`.
  - Un error de base de datos da 503, como en `/search`. Es lo que la UI
    traduce en el criterio 8.

## 5. Frontend

- **Dependencias nuevas** (pnpm): `leaflet`, `react-leaflet`,
  `react-leaflet-cluster` y `@types/leaflet`. Teselas de OpenStreetMap con su
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

### Prueba manual

Con `GEOCODING_PROVIDER=nominatim`, geocodificar un lote real y recorrer
`/mapa`: los 8 criterios, forzando un 503 para el 8.

Resultado: _pendiente_.

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
2. **Cola inicial lenta.** Con 1 req/s, miles de abiertas tardan horas la
   primera vez. La caché lo acorta en las vueltas siguientes.
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
