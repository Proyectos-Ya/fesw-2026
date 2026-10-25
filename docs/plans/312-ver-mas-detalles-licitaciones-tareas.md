# Tareas: HU-30, ver más detalles de las licitaciones

**Issue asociada**: Refs #312  
**Plan**: [312-ver-mas-detalles-licitaciones.md](./312-ver-mas-detalles-licitaciones.md) (decisiones en §8)  
**Fecha**: 2026-10-25

---

## Cómo usar este archivo

- Cada tarea cambia una sola cosa, se prueba con un solo comando y termina en
  un solo commit. Si una tarea no cabe en 30 minutos, se parte.
- En las tareas de código, primero se escribe la prueba y se ve fallar (Red),
  después el código mínimo para que pase (Green).
- Una tarea marcada **(invariante)** agrega una prueba que puede pasar sin
  código nuevo. Si falla, se arregla dentro de la misma tarea.
- Los comandos de backend corren desde `monorepo/backend` con `.venv` activo.
  Las pruebas de integración y e2e necesitan `supabase start`. Los de frontend
  corren desde `monorepo/frontend`.
- Formato de commit (SKILL.md §2):

  ```text
  <tipo>(<alcance>): <descripción corta en minúsculas>

  [AI Generated] Commit realizado por el agente de IA <Nombre-Agente>.
  Refs #312
  ```

  Si el commit lo hace una persona, se omite la línea `[AI Generated]`.

- No se hace `git push` sin confirmación explícita (SKILL.md §4).

---

## Bloque 0. Verificaciones previas

Sin código de producción.

- [ ] **0.1 Rama desde `develop`.** `git fetch origin` y confirmar que
      `origin/develop` contiene la rama actual (`git log HEAD..origin/develop`).
      Si `develop` avanzó, rebasar sobre `origin/develop`.
- [ ] **0.2 ¿El detalle trae las cotizaciones?** Con
      `MercadoPublicoClient.get_tender_detail`, pedir el detalle de 3 Compras
      Ágiles publicadas y buscar `resumen.total_ofertas_recibidas`. Anotar el
      resultado en §4.3 del plan. Si no lo trae, borrar el bloque 4 de este
      archivo.
      Commit: `docs(plans): detalle de compra ágil y cotizaciones en plan hu-30`
- [ ] **0.3 ¿Una cotización nueva mueve `fecha_ultimo_cambio`?** Con
      `MercadoPublicoClient.get_tenders`, listar las últimas 3 h y anotar
      `codigo`, `total_ofertas_recibidas` y `fecha_ultimo_cambio` de 5
      licitaciones publicadas. Repetir 3 h después. Si alguna sumó cotizaciones
      sin cambiar `fecha_ultimo_cambio`, la cifra no se refresca sola (riesgo 1).
      Anotar el resultado en el riesgo 1 del plan.
      Commit: `docs(plans): frescura de cotizaciones en plan hu-30`
- [ ] **0.4 Rama de los crons.** Con la skill `use-railway` y el MCP de Railway,
      solo lectura, ver desde qué rama despliegan `sync-estados` y la ingesta.
      Corregir §7 del plan si hace falta.

---

## Bloque 1. Esquema

- [ ] **1.1 Cargar skills y anotar la cabeza.** Invocar `supabase` y
      `supabase-postgres-best-practices`. `alembic heads` devuelve una línea
      (hoy `2510718f486e`).
- [ ] **1.2 Migración con las dos columnas.**
  - Red: en `tests/integration/test_migraciones.py`, una prueba que inspecciona
    `tender` en `engine_migrado` y exige `received_offers_count` integer nullable
    y `offers_checked_at` timestamp nullable, las dos sin default.
  - Green: los dos campos en `TenderModel`
    (`app/infrastructure/repositories/tender_model.py`, junto a `call_number`)
    y `alembic revision --autogenerate -m "cotizaciones recibidas en tender"`.
  - Revisar el archivo: solo dos `op.add_column(..., nullable=True)` en
    `upgrade` y dos `op.drop_column` en `downgrade`. Sin `server_default`.
  - Verificar: `pytest tests/integration/test_migraciones.py -q && python -m scripts.migraciones`
  - Commit: `feat(db): cotizaciones recibidas y fecha de revisión en tender`

---

## Bloque 2. Lectura del dato

- [x] **2.1 `leer_total_ofertas`.**
  - Red: `tests/unit/infrastructure/test_ofertas_mp.py`, con `parametrize`
    sobre cada fila de §4.1 del plan: `0`, `17`, `None`, clave ausente,
    `resumen` ausente, `resumen` como lista, `True`, `False`, `-1`, `"17"` y
    `17.0`.
  - Green: `app/infrastructure/services/tenders/ofertas.py`, con
    `type(valor) is int and valor >= 0` y un docstring con la forma verificada,
    como el de `llamados.py`.
  - Verificar: `pytest tests/unit/infrastructure/test_ofertas_mp.py -q`
  - Commit: `feat(ingesta): leer total de ofertas recibidas de mercado público`

---

## Bloque 3. sync-estados

- [ ] **3.1 El listado trae la cifra.**
  - Red: en `tests/unit/infrastructure/test_listado_cambios.py`, los cuatro
    ítems del fixture dan 0, 17, 1 y 0, y un ítem sin `resumen` sigue dando un
    `CambioDeEstado` con `received_offers_count is None`.
  - Green: `received_offers_count: int | None = None` en `CambioDeEstado`
    (`app/domain/models/cambio_estado.py`) y `leer_total_ofertas(item)` en
    `cambio_desde_item`. Sumar `resumen` al docstring de `listado_cambios.py`.
  - Verificar: `pytest tests/unit/infrastructure/test_listado_cambios.py -q`
  - Commit: `feat(sync-estados): leer cotizaciones del listado de cambios`
- [ ] **3.2 (invariante) La cifra no cuenta como llamado.**
  - Prueba: un ítem que trae cotizaciones y no trae `convocatoria` tiene
    `trae_llamado` en falso.
  - Commit: `test(sync-estados): las cotizaciones no activan trae_llamado`
- [ ] **3.3 El caso de uso elige qué registrar.**
  - Red: en `tests/unit/application/test_sync_tender_statuses.py`, a
    `overwrite_received_offers_count` llega una conocida con cifra 3 y una
    reabierta con cifra, y no llegan una conocida con `None` ni una desconocida.
  - Green:
    - el método abstracto en
      `app/application/repositories/tender_status_sync_repository.py`;
    - `RepoFalso` lo implementa guardando los cambios recibidos;
    - `SyncTenderStatusesUseCase.execute` arma `a_registrar_ofertas` junto a
      `a_registrar_llamado`.
  - Verificar: `pytest tests/unit/application/test_sync_tender_statuses.py -q`
  - Commit: `feat(sync-estados): registrar cotizaciones de licitaciones conocidas`
- [ ] **3.4 Orden de escritura.**
  - Red: con el `log` de `RepoFalso`, `sql-ofertas` va después de `sql-llamado`
    y antes de los punteros.
  - Green: mover la llamada si hace falta.
  - Commit: `test(sync-estados): cotizaciones se escriben antes de los punteros`
- [ ] **3.5 Contador `ofertas_revisadas`.**
  - Red: el resultado trae lo que devuelve `RepoFalso`, y `sumar` lo acumula
    entre dos páginas.
  - Green: `ofertas_revisadas: int = 0` en `ResultadoSyncEstados`.
  - Commit: `feat(sync-estados): contar cotizaciones revisadas por corrida`
- [ ] **3.6 El resumen del cron muestra el contador.**
  - Red: en `tests/unit/test_sync_estados.py`, el resumen impreso incluye
    "con cotizaciones revisadas".
  - Green: una línea en el `print` de `scripts/sync_estados.py:317`.
  - Commit: `feat(sync-estados): imprimir cotizaciones revisadas`
- [ ] **3.7 El repositorio escribe la cifra y la fecha.**
  - Red: en `tests/integration/test_sync_estados_repository.py`, un lote con
    0 y 17 deja esas cifras y `offers_checked_at` con la hora de la corrida.
    Devuelve 2.
  - Green: `overwrite_received_offers_count` en `TenderRepository`, con un
    `UPDATE ... FROM (VALUES ...)` por lote de `_LOTE_ESTADOS` y
    `offers_checked_at=utc_now_naive()`.
  - Verificar: `pytest tests/integration/test_sync_estados_repository.py -q`
  - Commit: `feat(repositorio): guardar cotizaciones y fecha de revisión en lote`
- [ ] **3.8 (invariante) La misma cifra igual mueve la fecha.**
  - Prueba: escribir 5 sobre 5 cuenta como revisada y mueve `offers_checked_at`.
  - Commit: `test(repositorio): revisar la misma cifra mueve offers_checked_at`
- [ ] **3.9 (invariante) No mueve `updated_at` ni `last_change_at`.**
  - Prueba: siguiendo a `test_no_toca_last_change_at`, las dos fechas quedan
    iguales después de `overwrite_received_offers_count`.
  - Commit: `test(repositorio): cotizaciones no mueven updated_at ni last_change_at`

---

## Bloque 4. Ingesta (solo si la tarea 0.2 dice que el detalle trae la cifra)

- [ ] **4.1 El DTO trae la cifra.**
  - Red: `tests/unit/infrastructure/test_detalle_ofertas.py`. Un detalle con 4,
    con 0 y sin `resumen` da `dto.received_offers_count` igual a 4, 0 y `None`.
  - Green: el campo en `TenderIngestaDTO` y
    `TotalOfertasRecibidas=leer_total_ofertas(detail)` en `_parse_to_dto`.
  - Commit: `feat(ingesta): pasar cotizaciones del detalle al dto`
- [ ] **4.2 El alta guarda la cifra.**
  - Red: en `tests/unit/application/test_tender_ingestion_use_case.py`, una
    licitación nueva con cifra 2 se guarda con 2 y con `offers_checked_at`. Con
    `None`, las dos quedan en `None`.
  - Green: los dos campos en el `TenderModel(...)` del alta
    (`tender_ingestion_use_case.py:123`).
  - Commit: `feat(ingesta): guardar cotizaciones al crear una licitación`
- [ ] **4.3 La actualización no toca Qdrant.**
  - Red: `tests/unit/application/test_ingesta_ofertas.py`, que sigue a
    `test_ingesta_segundo_llamado.py`. Si solo cambia la cifra, el resultado es
    `updated`, `updated_at` no se mueve y el doble de Qdrant no recibe llamadas.
  - Green: `_aplicar_ofertas` junto a `_aplicar_llamado`, llamado en las dos
    ramas, y la condición de la rama sin cambio semántico pasa a
    `cambio_llamado or cambio_ofertas`.
  - Commit: `feat(ingesta): actualizar cotizaciones sin mover updated_at`
- [ ] **4.4 Un `None` no borra.**
  - Red: un detalle sin cifra no borra la que dejó sync-estados y devuelve
    `unchanged`.
  - Green: `_aplicar_ofertas` no escribe si la cifra es `None`.
  - Commit: `test(ingesta): un detalle sin cotizaciones no borra la cifra`

---

## Bloque 5. Dominio y API

- [ ] **5.1 La entidad trae los campos.**
  - Red: en `tests/integration/test_tender_repository.py`, una fila con cifra 0
    y fecha se lee con 0 y esa fecha, y una fila en `NULL` se lee con `None`.
  - Green: los dos campos en `app/domain/entities/tender.py` y en las dos
    conversiones de `tender_repository.py` (líneas 78 y 121).
  - Commit: `feat(dominio): exponer cotizaciones recibidas en tender`
- [ ] **5.2 (invariante) La ficha devuelve los campos.**
  - Prueba: en `tests/e2e/api/test_tender_router.py`, el `GET` del detalle trae
    `received_offers_count` como 4, como 0 y como `null`, y la clave existe en
    los tres casos.
  - Commit: `test(api): ficha devuelve received_offers_count, también en null`

---

## Bloque 6. Cierre del backend

- [ ] **6.1 Suite y lint.**
      `pytest && python -m scripts.migraciones`. Ruff solo sobre los archivos
      de la rama: el backend completo arrastra cientos de hallazgos previos y el
      CI no corre Ruff.
      ```bash
      ruff check $(git diff --name-only origin/develop -- '*.py')
      ruff format --check $(git diff --name-only origin/develop -- '*.py')
      ```
- [ ] **6.2 Prueba manual de sync-estados.** `python -m scripts.sync_estados --ventana-horas 1`
      contra Supabase local. Con SQL, revisar que `received_offers_count` y
      `offers_checked_at` se llenan y que `updated_at` no cambia. Anotar el
      resultado en §6 del plan.
      Commit: `docs(plans): prueba manual de sync-estados en plan hu-30`

---

## Bloque 7. Utilidades del frontend

- [x] **7.1 `formatOffersCount`.**
  - Red: `src/features/matches/utils/__tests__/offers.test.ts`. `null` y
    `undefined` dan "No disponible", 0 da "0 cotizaciones", 1 da
    "1 cotización" y 17 da "17 cotizaciones".
  - Green: los dos campos opcionales en `src/features/matches/tenderTypes.ts`
    (junto a `call_number`, línea 21) y `src/features/matches/utils/offers.ts`
    con `count == null`.
  - Verificar: `pnpm run test src/features/matches/utils`
  - Commit: `feat(matches): formatear cotizaciones recibidas`
- [x] **7.2 `callBadge`.**
  - Red: en `src/features/matches/utils/__tests__/secondCall.test.ts`, 1 da
    "Primer llamado" e `info`, 2 da "Segundo llamado" y `warning`, y `null`,
    ausente y 3 dan "No disponible" y `neutral`.
  - Green: `callBadge(tender: Pick<Tender, "call_number">)` en
    `utils/secondCall.ts`, que devuelve `{ label: string; tone: BadgeTone }`.
    Para el 2 reutiliza `SECOND_CALL_LABEL`.
  - Commit: `feat(matches): etiqueta y tono del llamado`
- [x] **7.3 `Badge` expone el tono.**
  - Red: en `src/features/shared/components/__tests__/Badge.test.tsx`, un
    `Badge tone="warning"` tiene `data-tone="warning"`, y uno sin `tone` tiene
    `data-tone="neutral"`.
  - Green: `data-tone={tone}` en el elemento raíz de `Badge.tsx`.
  - Commit: `feat(shared): badge expone su tono en data-tone`

---

## Bloque 8. Ficha de la licitación

Archivo: `src/features/matches/components/TenderDetailView.tsx`.
Pruebas: `src/features/matches/components/__tests__/TenderDetailView.test.tsx`.
Verificar cada tarea con `pnpm run test src/features/matches`.

- [x] **8.1 `KeyValueCard` acepta `ReactNode`.** Refactor sin cambio de
      comportamiento: `value: string` pasa a `value: ReactNode` (línea 899). Las
      pruebas actuales siguen en verde.
      Commit: `refactor(matches): keyvaluecard acepta contenido react`
- [ ] **8.2 Tarjeta de cotizaciones.**
  - Red: con cifra 0 muestra "0 cotizaciones". Con `null` y con el campo
    ausente muestra "No disponible" y ningún "0 cotizaciones".
  - Green: tarjeta "Cotizaciones recibidas" en la grilla con
    `formatOffersCount`.
  - Commit: `feat(matches): mostrar cotizaciones recibidas en la ficha`
- [ ] **8.3 Fecha de revisión.**
  - Red: con cifra y `offers_checked_at` muestra
    "Revisado el {formatDateTime(...)}". Sin cifra, o sin fecha, no muestra la
    pista.
  - Green: `hint` de la tarjeta de cotizaciones.
  - Commit: `feat(matches): fecha de revisión de las cotizaciones`
- [ ] **8.4 Tarjeta del llamado.**
  - Red: `call_number: 1` muestra "Primer llamado" con `data-tone="info"`,
    `call_number: 2` muestra "Segundo llamado" con `data-tone="warning"`, y
    `null` muestra "No disponible" dentro de la tarjeta "Llamado".
  - Green: tarjeta "Llamado" con el `Badge` de `callBadge`.
  - Commit: `feat(matches): tarjeta de primer y segundo llamado en la ficha`
- [ ] **8.5 Quitar el badge del encabezado.**
  - Red: ajustar las pruebas de las líneas 604-660 según §5.3 del plan, y
    exigir que el encabezado ya no tenga "Segundo llamado".
  - Green: borrar el badge de las líneas 494-496. Quitar los imports que
    queden sin uso.
  - Commit: `refactor(matches): el llamado se muestra solo en la grilla`
- [ ] **8.6 Publicación pasa a hitos.**
  - Red: la grilla tiene exactamente cuatro tarjetas (Monto estimado, Cierre,
    Llamado y Cotizaciones recibidas), y la fecha de publicación aparece en
    "Hitos y fechas importantes".
  - Green: sacar la tarjeta "Publicación", sumar la fecha a la sección de
    hitos y pasar la grilla a `sm:grid-cols-2 lg:grid-cols-4`.
  - Commit: `feat(matches): grilla de cuatro métricas en la ficha`
- [ ] **8.7 Separar requisitos y descripción.**
  - Red: hay una sección "Entrega y requisitos" con los cierres por llamado,
    los ítems y el resumen de anexos, y otra "Descripción" con el texto.
    Ajustar la prueba de la línea 198, que busca "Requisitos y descripción".
  - Green: partir la sección actual en dos. Dejar un comentario en
    "Entrega y requisitos" que diga que #294 agrega allí la dirección y el plazo.
  - Commit: `feat(matches): secciones de entrega y requisitos y de descripción`
- [ ] **8.8 Sección de documentos.**
  - Red: las secciones aparecen en este orden: "Entrega y requisitos",
    "Documentos", "Descripción". `TenderAttachmentsPanel` está dentro de
    "Documentos".
  - Green: mover `TenderAttachmentsPanel` (línea 571) a una sección
    "Documentos" entre las otras dos.
  - Commit: `feat(matches): sección de documentos en la ficha`
- [ ] **8.9 (invariante) Los avisos de anexos siguen llegando.** Correr
      `TenderDetailView.telemetry.test.tsx` y las pruebas de las líneas 205-221
      sin cambios. Si alguna falla, el movimiento de 8.8 rompió algo y se
      arregla ahí.

---

## Bloque 9. Cierre y PR

- [ ] **9.1 Suite, lint y build del frontend.**
      `pnpm run test && pnpm run lint && pnpm run build`
- [ ] **9.2 Prueba manual en el navegador.** Abrir fichas con 0 cotizaciones,
      con varias, en `NULL`, en primer llamado y en segundo. Subir un anexo y
      ver que el puntaje y los hitos se recalculan. Anotar el resultado en §6
      del plan y marcar las tareas hechas en este archivo.
      Commit: `docs(plans): prueba manual de la ficha en plan hu-30`
- [ ] **9.3 `graphify update .`** desde la raíz del repo.
- [ ] **9.4 Backend otra vez.** `pytest && python -m scripts.migraciones`, por si
      `develop` avanzó. Si hay dos cabezas, repuntar el `down_revision` de la
      migración de 1.2 (todavía no se aplicó en ningún entorno compartido).
- [ ] **9.5 Abrir el PR hacia `develop`.** Con `Refs #312`, el enlace al plan, la
      salida de `alembic heads`, capturas de la ficha y la nota de que dev test
      comparte base con producción. Pedir confirmación antes de `git push`.
- [ ] **9.6 Avisar en las issues** (pedir confirmación antes de publicar):
  - en #312, que CA4 queda parcial hasta #294 y por qué;
  - en #294, que la sección "Entrega y requisitos" ya existe y dónde agregar
    los campos;
  - si la tarea 0.3 confirmó el riesgo 1, una issue nueva para refrescar la
    cifra de las licitaciones que no cambian de estado.

---

## Orden y dependencias

| Bloque | Depende de |
| --- | --- |
| 0 | nada |
| 1 | 0.1 |
| 2 | nada |
| 3 | 1 y 2 |
| 4 | 0.2, 1 y 2 |
| 5 | 1 |
| 6 | 3, 4 y 5 |
| 7 | nada |
| 8 | 7 |
| 9 | 6 y 8 |

Los bloques 2 y 7 se pueden empezar en paralelo con el bloque 1.
