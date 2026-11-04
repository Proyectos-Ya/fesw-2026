# Tareas: importar los datos de la empresa por RUT (HU-23)

**Issue asociada**: Refs #310  
**Plan técnico**: [plan.md](./plan.md)  
**Rama**: `310-importar-datos-empresa-por-rut`

Cada tarea toca un archivo de código y su test. Primero se escribe el test y se ve
fallar, y después el código. Las rutas son relativas a
`monorepo/frontend/src/features/company-profile/`, salvo las de `shared/`. Las tareas
van en orden.

## Errores y validación del RUT (CA1, CA2)

- [x] **T1. `describeImportError`.** Traduce `ApiError` 400, 404, 502 y 503, y
  `TimeoutError`, a `{ kind, message }` (plan, decisión 4).
  Archivos: `services/supplierService.ts`, `services/__tests__/importCompanyProfile.test.ts`.

- [x] **T2. La tarjeta no importa con un RUT inválido.** Antes de llamar al servicio,
  valida con `step1Schema.shape.rut`. Si falla, llama a la prop `onInvalidRut(message)`.
  Test: con `76.668.304-0` el servicio no se llama.
  Archivos: `components/CompanyImportCard.tsx`, `components/__tests__/CompanyImportCard.test.tsx`.

- [x] **T3. Avisos por tipo de error en la tarjeta.** Usa `describeImportError`. El 404
  se muestra con `role="status"` y tono informativo, y el resto como advertencia.
  Archivos: `components/CompanyImportCard.tsx`, `components/__tests__/CompanyImportCard.test.tsx`.

- [x] **T4. Tarjeta en el paso 1.** Se monta debajo del RUT con `watch("rut")`.
  `onInvalidRut` llama a `setError("rut", …)`. Test: con un 404, "Siguiente" llama a
  `onNext`.
  Archivos: `components/steps/Step1Identity.tsx`, `components/__tests__/Step1Identity.test.tsx`.

- [x] **T5. Quitar la tarjeta del paso 2.** Borrar `CompanyImportCard` y
  `handleImported` de `Step2Operations` y pasar las props nuevas desde `ProfileWizard`.
  Archivos: `components/steps/Step2Operations.tsx`, `components/ProfileWizard.tsx`.

## Precarga en el reducer (CA3)

- [x] **T6. `IMPORT` aplica el borrador.** Reemplaza la razón social si viene con valor,
  suma regiones y rubros filtrando el catálogo, guarda `added` y deja los campos que
  cambiaron en `pending`.
  Archivos: `hooks/useProfileWizard.ts`, `hooks/__tests__/useProfileWizard.test.ts`.

- [x] **T7. `IMPORT` con otro RUT.** Si `importReview.rut` es distinto del RUT nuevo,
  vacía la razón social, las regiones y los rubros antes de aplicar.
  Archivos: `hooks/useProfileWizard.ts`, `hooks/__tests__/useProfileWizard.test.ts`.

- [x] **T8. Acciones de revisión.** `CONFIRM_FIELD`, `EDIT_FIELD`, `CLEAR_FIELD` y
  `isStepBlocked(step)`. `CLEAR_FIELD` en regiones quita solo lo que está en `added`.
  Archivos: `hooks/useProfileWizard.ts`, `hooks/__tests__/useProfileWizard.test.ts`.

## Revisión por campo (CA4)

- [x] **T9. `disabled` en `ChipSelect`.** Con `disabled`, un clic no cambia la selección.
  Archivos: `features/shared/components/ChipSelect.tsx`,
  `features/shared/components/__tests__/ChipSelect.test.tsx` (nuevo).

- [x] **T10. `nextDisabled` en `WizardNavigation`.** Con la prop activa, el botón está
  deshabilitado y no llama a `onNext`.
  Archivos: `components/WizardNavigation.tsx`, `components/__tests__/WizardNavigation.test.tsx` (nuevo).

- [x] **T11. Componente `ImportedFieldReview`.** Muestra la insignia "Pendiente de
  revisión" (`warning`) o "Revisado" (`success`), y los botones Confirmar, Editar y
  Borrar según el estado.
  Archivos: `components/ImportedFieldReview.tsx`, `components/__tests__/ImportedFieldReview.test.tsx` (nuevo).

- [x] **T12. Paso 1 con revisión.** La razón social importada se llena con `setValue`,
  queda de solo lectura mientras está pendiente y "Siguiente" se bloquea hasta
  confirmarla.
  Archivos: `components/steps/Step1Identity.tsx`, `components/__tests__/Step1Identity.test.tsx`.

- [x] **T13. Paso 2 con revisión.** Regiones con `ImportedFieldReview`, `ChipSelect`
  deshabilitado mientras están pendientes y "Siguiente" bloqueado.
  Archivos: `components/steps/Step2Operations.tsx`, `components/__tests__/Step2Operations.test.tsx` (nuevo).

- [x] **T14. Paso 3 con revisión.** Lo mismo que T13, para los rubros.
  Archivos: `components/steps/Step3Specialization.tsx`, `components/__tests__/Step3Specialization.test.tsx` (nuevo).

- [x] **T15. Guarda en `handleSubmit`.** Si algún campo sigue sin confirmar, no llama a
  `createSupplier`.
  Archivos: `components/ProfileWizard.tsx`, `components/__tests__/ProfileWizard.test.tsx`.

## Cierre

- [ ] **T16. Recorrido completo.** Test en `ProfileWizard.test.tsx`: importar, confirmar
  en cada paso, reimportar con otro RUT y guardar. Después, `pnpm run test`,
  `pnpm run lint`, la prueba manual del plan (§6) y marcar estas casillas.
