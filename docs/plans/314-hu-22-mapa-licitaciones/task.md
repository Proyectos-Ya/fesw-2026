# Tareas: #314, HU-22, mapa de las direcciones de entrega de mi zona

**Issue asociada**: Refs #314  
**Plan**: [plan.md](./plan.md) (decisiones en §8)  
**Fecha**: 2026-10-28

---

## Cómo usar este archivo

- Cada tarea cambia una sola cosa, se prueba con un comando y termina en un
  commit. Primero la prueba que falla (Red), después el código mínimo (Green).
- Una tarea **(invariante)** agrega una prueba que puede pasar sin código
  nuevo. Si falla, se arregla dentro de la misma tarea.
- Backend desde `monorepo/backend`, con `supabase start` para integración y
  e2e. Frontend desde `monorepo/frontend`.
- Formato de commit (SKILL.md §2), con `Refs #314`. Sin `git push` sin
  confirmación explícita (SKILL.md §4). Siempre `git add` con rutas explícitas.
- Los criterios se numeran del 1 al 8 en el orden de la issue.

---

## Bloque 1. Esquema

- [x] **1.1 Migración con las columnas de ubicación y la caché.**
  - Antes: skills `supabase` y `supabase-postgres-best-practices`.
  - Red: `tests/integration/test_migraciones.py` exige las cuatro columnas de
    `tender` (nullable, sin default), el índice parcial y `geocoding_cache`.
  - Green: campos en `TenderModel`, `GeocodingCacheModel`, y
    `alembic revision --autogenerate` contra una base temporal recién migrada.
    Probar `upgrade`, `downgrade -1` y `upgrade`, y `python -m scripts.migraciones`.
  - Commit: `feat(db): coordenadas de entrega en tender y caché de geocodificación`

## Bloque 2. Geocodificación

- [x] **2.1 Cliente Nominatim.**
  - Red: `tests/unit/infrastructure/test_nominatim_geocoding.py` con
    `httpx.MockTransport`: resultado normal, lista vacía (`None`), respuesta
    rara, 5xx y error de red (`GeocodingUnavailable`), y que mande
    `countrycodes=cl` y el `User-Agent`.
  - Green: puerto `geocoding_service.py` y `nominatim_geocoding_service.py`.
  - Commit: `feat(geocodificacion): cliente de nominatim`
- [x] **2.2 Settings y armado.**
  - Red: `provider="none"` no arma cliente; `nominatim` sin correo falla la
    validación, como `company_lookup_*`.
  - Green: `config.py`, `bootstrap/builders.py`.
  - Commit: `feat(geocodificacion): configuración del proveedor`
- [x] **2.3 Caso de uso de la cola.**
  - Red: `tests/unit/application/test_geocodificar_licitaciones.py` con fakes:
    dirección encontrada (`direccion`), respaldo por comuna (`comuna`), sin
    comuna (`no_encontrada`, sin coordenadas), acierto de caché sin llamar al
    servicio, y servicio caído (queda pendiente).
  - Green: `GeocodePendingTendersUseCase` y los métodos del puerto del
    repositorio (pendientes, guardar resultado, caché).
  - Commit: `feat(geocodificacion): geocodificar licitaciones pendientes`
- [x] **2.4 Repositorio contra Postgres.**
  - Red: `tests/integration/test_tender_geocoding_repository.py`: la cola trae
    solo abiertas con dirección y sin intento; guardar saca de la cola; la
    caché guarda también los no encontrados.
  - Green: implementación en `TenderRepository` y repositorio de la caché.
  - Commit: `feat(geocodificacion): cola y caché en postgres`
- [x] **2.5 Scheduler en el lifespan.**
  - Red: el loop sobrevive a un error y espera 1 s entre llamadas reales.
  - Green: `GeocodingScheduler`, runner en `bootstrap/runners.py`, arranque
    en `app/main.py` solo si el proveedor no es `none`.
  - Commit: `feat(geocodificacion): scheduler de la cola`
- [x] **2.6 La ingesta re-encola una dirección cambiada.**
  - Red: en `test_ingesta_entrega.py`, cambiar la dirección limpia
    `delivery_geocoded_at` sin mover `updated_at`; la misma dirección no.
  - Green: `_aplicar_entrega` en `tender_ingestion_use_case.py`.
  - Commit: `feat(ingesta): volver a geocodificar si cambia la dirección`

## Bloque 3. API del mapa (criterios 1, 5, 6 y 8)

- [x] **3.1 Consulta del mapa.**
  - Red: `tests/integration/test_tender_repository.py`: por región, solo
    publicadas con cierre futuro y coordenadas; tope y `total`.
  - Green: `list_open_with_location` y la entidad `TenderMapPoint`.
  - Commit: `feat(mapa): licitaciones abiertas con ubicación por región`
- [x] **3.2 Caso de uso.**
  - Red: nombres del wizard y canónicos dan la misma región; desconocida
    lanza `InvalidSearchCriteria`.
  - Green: `GetTendersMapUseCase` y su proveedor en `bootstrap/matching.py`.
  - Commit: `feat(mapa): caso de uso del mapa de licitaciones`
- [x] **3.3 Endpoint `GET /tenders/map`.**
  - Red: `tests/e2e/api/test_tender_router.py` con `dependency_overrides`:
    200 con ítems, 422 región desconocida, 503 con error de base, 401 sin
    sesión, y que no lo capture `/{tender_id}`.
  - Green: ruta con `summary`, `response_model` y `tags`; `TenderMapResponse`.
  - Commit: `feat(api): endpoint del mapa de licitaciones`

## Bloque 4. Frontend

- [x] **4.1 Dependencias.**
  - `pnpm add leaflet react-leaflet react-leaflet-cluster` y
    `pnpm add -D @types/leaflet`. `pnpm run build` compila.
  - Commit: `build(frontend): leaflet para el mapa de licitaciones`
- [ ] **4.2 Servicio y tipos.**
  - Red: `tender-map/services/__tests__/tenderMapService.test.ts`: arma
    `/tenders/map?region=...` y propaga `ApiError`.
  - Green: `types/index.ts`, `services/tenderMapService.ts`, `test-utils.ts`
    con `buildTenderMapPoint`.
  - Commit: `feat(mapa): servicio del mapa de licitaciones`
- [ ] **4.3 Hook con reintento.**
  - Red: `hooks/__tests__/useTenderMap.test.ts`: carga, error, `retry` vuelve
    a pedir, cambiar región vuelve a pedir y descarta la respuesta vieja.
  - Green: `hooks/useTenderMap.ts`.
  - Commit: `feat(mapa): hook del mapa con reintento`
- [ ] **4.4 Centros de región.**
  - Red: hay centro para cada una de `SEARCH_REGIONS`, y toda región del
    perfil se resuelve vía `toSearchRegion`.
  - Green: `data/regionCenters.ts`.
  - Commit: `feat(mapa): centro y zoom de cada región`
- [ ] **4.5 Resumen del marcador (criterio 3).**
  - Red: `TenderMapSummary` muestra nombre, organismo, dirección y cierre,
    enlaza a `/matches/{id}`, y avisa "aproximada" con precisión `comuna`.
  - Green: `components/TenderMapSummary.tsx`.
  - Commit: `feat(mapa): resumen de la licitación en el marcador`
- [ ] **4.6 Mapa Leaflet (criterios 1 y 4).**
  - Green: `components/TenderMap.tsx` con `MarkerClusterGroup`, `divIcon` y
    `flyTo`. Sin prueba unitaria (jsdom sin canvas); se prueba a mano en 6.2.
  - Commit: `feat(mapa): mapa con marcadores agrupados`
- [ ] **4.7 Vista (criterios 1, 2, 5, 6 y 8).**
  - Red: `components/__tests__/TenderMapView.test.tsx` con `TenderMap`
    mockeado: zona inicial de la empresa; sin zona pide elegir y enlaza al
    perfil; cambiar zona pide de nuevo; vacío sugiere otra zona; error dice
    "No se pudo cargar el mapa" y Reintentar vuelve a pedir.
  - Green: `components/TenderMapView.tsx` y `src/app/(app)/mapa/page.tsx`.
  - Commit: `feat(mapa): vista del mapa de licitaciones`
- [ ] **4.8 Entrada en el menú (criterio 1).**
  - Red: el test del `Sidebar` encuentra "Mapa de licitaciones" con
    `href="/mapa"`.
  - Green: `NAV_ITEMS` en `shared/components/Sidebar.tsx`.
  - Commit: `feat(mapa): mapa de licitaciones en el menú`

## Bloque 5. Criterio 7

- [ ] **5.1 (invariante) La ficha muestra la dirección o el texto sin dato.**
  Ya cubierto por #294 en `TenderDetailView.test.tsx` y `entrega.test.ts`;
  solo se cita en el PR.

## Bloque 6. Cierre

- [ ] **6.1 Suites completas.** `pytest`, `python -m scripts.migraciones`,
  `pnpm run test`, `pnpm run lint` y `pnpm run build`. Resultado en el plan §6.
- [ ] **6.2 Prueba manual** de los 8 criterios con geocodificación real.
  Resultado en el plan §6.
- [ ] **6.3 Documentación.** Plan en estado Completado y enlazado en
  `docs/README.md`; variables `GEOCODING_*` en `monorepo/backend/README.md`.
