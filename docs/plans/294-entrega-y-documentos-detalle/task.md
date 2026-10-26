# Tareas: #294, entrega y documentos del detalle de Compra Ágil

**Issue asociada**: Closes #294  
**Plan**: [plan.md](./plan.md) (decisiones en §8)  
**Fecha**: 2026-10-26

---

## Cómo usar este archivo

- Cada tarea cambia una sola cosa, se prueba con un comando y termina en un
  commit. Primero la prueba que falla (Red), después el código mínimo (Green).
- Una tarea **(invariante)** agrega una prueba que puede pasar sin código
  nuevo. Si falla, se arregla dentro de la misma tarea.
- Backend desde `monorepo/backend`, con `supabase start` para integración y
  e2e. Frontend desde `monorepo/frontend`.
- Formato de commit (SKILL.md §2), con `Refs #294`. Sin `git push` sin
  confirmación explícita (SKILL.md §4). Siempre `git add` con rutas explícitas.

---

## Bloque 1. Esquema (criterio 1)

- [x] **1.1 Migración con las cuatro columnas.**
  - Antes: skills `supabase` y `supabase-postgres-best-practices`.
  - Red: `tests/integration/test_migraciones.py` exige `delivery_address`
    (text), `delivery_term_days` (integer) y los dos flags (boolean), todas
    nullable y sin default.
  - Green: los campos en `TenderModel` y `alembic revision --autogenerate`
    contra una base temporal recién migrada. Probar `upgrade`, `downgrade -1` y
    `upgrade`, y `python -m scripts.migraciones`.
  - Commit: `feat(db): entrega y requisitos del detalle en tender`

## Bloque 2. Lectura del detalle (criterio 1)

- [x] **2.1 `leer_entrega` y `leer_requisitos`.**
  - Red: `tests/unit/infrastructure/test_entrega_mp.py`, con `parametrize`
    sobre valores normales y raros.
  - Green: `app/infrastructure/services/tenders/entrega.py`.
  - Commit: `feat(ingesta): leer entrega y requisitos del detalle`
- [x] **2.2 El DTO trae los cuatro campos.**
  - Red: `tests/unit/infrastructure/test_detalle_entrega.py`, siguiendo a
    `test_detalle_ofertas.py`.
  - Green: los campos en `TenderIngestaDTO` y en `_parse_to_dto`.
  - Commit: `feat(ingesta): pasar entrega y requisitos del detalle al dto`
- [x] **2.3 (invariante) Los nombres de los documentos llegan al DTO.** Ya cubierto por `test_detalle_documentos.py::test_con_documentos_los_lee`.
  - Prueba: si `test_detalle_documentos.py` ya cubre los nombres, solo se cita
    en el PR. Si no, se agrega.

## Bloque 3. Ingesta (criterio 1)

- [x] **3.1 El alta guarda los cuatro campos.**
  - Red: `tests/unit/application/test_ingesta_entrega.py`, clase `TestAlta`.
  - Green: los campos en el `TenderModel(...)` del alta.
  - Commit: `feat(ingesta): guardar entrega al crear una licitación`
- [x] **3.2 Una actualización solo de entrega no toca Qdrant.**
  - Red: resultado `updated`, `updated_at` igual, sin llamadas a embeddings ni
    a Qdrant. El mismo valor da `unchanged`. Con cambio de metadatos también
    se aplica.
  - Green: `_entrega_cambio` y `_aplicar_entrega`, en las dos ramas.
  - Commit: `feat(ingesta): actualizar entrega sin mover updated_at`
- [x] **3.3 (invariante) Un `None` no borra.**
  - Prueba: un detalle sin entrega ni flags conserva lo guardado.
  - Commit: `test(ingesta): un detalle sin entrega no borra lo guardado`

## Bloque 4. Dominio y API (criterio 2)

- [x] **4.1 La entidad trae los campos.**
  - Red: `tests/integration/test_tender_repository.py`, con datos y con `NULL`.
  - Green: `Tender` y las dos conversiones de `TenderRepository`.
  - Commit: `feat(dominio): exponer entrega y requisitos en tender`
- [x] **4.2 (invariante) La ficha devuelve los campos.**
  - Prueba: `tests/e2e/api/test_tender_router.py`, la clave viaja también en
    `null`.
  - Commit: `test(api): ficha devuelve la entrega, también en null`

## Bloque 5. Frontend (criterios 2 y 4)

- [x] **5.1 `formatDeliveryAddress` y `formatDeliveryTerm`.**
  - Red: `src/features/matches/utils/__tests__/entrega.test.ts`.
  - Green: campos opcionales en `tenderTypes.ts` y `utils/entrega.ts`.
  - Commit: `feat(matches): formatear dirección y plazo de entrega`
- [x] **5.2 La ficha muestra la dirección y el plazo.**
  - Red: `TenderDetailView.test.tsx`, con datos, sin datos, plazo 0 y 1.
  - Green: bloque en "Entrega y requisitos", sin el comentario de #294.
  - Commit: `feat(matches): dirección y plazo de entrega en la ficha`
- [x] **5.3 `nombrarDocumentos`.**
  - Red: `src/features/proposals/utils/__tests__/proposal.test.ts`.
  - Green: la función en `proposals/utils/proposal.ts`.
  - Commit: `feat(proposals): nombrar documentos en una frase`
- [x] **5.4 `basesNotice` nombra los documentos pendientes.**
  - Red: análisis sin adjuntos, sin subidas nuevas y con pendientes nombra los
    documentos, también con `mentions_attachments`. Sin pendientes, igual que
    hoy.
  - Green: tercer parámetro `pendientes` en `basesNotice` y su llamada en
    `ProposalView.tsx`.
  - Commit: `feat(proposals): la recomendación de bases nombra los documentos`
- [x] **5.5 El aviso previo al análisis nombra los documentos.**
  - Red: `ProposalView.test.tsx`, sin subidas y con anexos oficiales.
  - Green: el texto del aviso en `ProposalView.tsx`.
  - Commit: `feat(proposals): el aviso sin anexos nombra los documentos`

## Bloque 6. Cierre y PR

- [ ] **6.1 Suites.** `pytest`, `python -m scripts.migraciones`, Ruff sobre los
      archivos de la rama, `pnpm run test`, `pnpm run lint` y `pnpm run build`.
      Anotar el resultado en §6 del plan.
- [ ] **6.2 Prueba manual en el navegador**, con datos de prueba cargados con
      SQL y restaurados al terminar. Anotar el resultado en §6 del plan.
- [ ] **6.3 PR hacia `develop`** con `Closes #294`. Mostrar el texto antes de
      crearlo y pedir confirmación antes de `git push`.
- [ ] **6.4 Issues** (pedir confirmación antes de publicar): una nueva con los
      criterios 3 y 5, y un comentario en #314 (HU-22) sobre los textos de la
      dirección en la ficha.
