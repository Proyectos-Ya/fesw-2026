# Plan técnico: importar los datos de la empresa por RUT (HU-23)

**Issue asociada**: Refs #310  
**Estado**: Borrador  
**Fecha**: 2026-10-25  
**Tareas**: [task.md](./task.md)

---

## 1. Contexto

Al crear su empresa en el wizard, el usuario escribe a mano la razón social, las
regiones y los rubros. Con esta HU, el usuario ingresa el RUT, aprieta "Importar
datos" y la plataforma precarga esos campos desde la fuente externa (SRE o Web
Empresario). Después el usuario revisa cada campo antes de avanzar. Los criterios de
aceptación están en la issue y aquí se citan como CA1 a CA4.

La HdU 16 dejó hecho el backend y una primera versión de la tarjeta de importación.
Esta HU es casi solo de frontend.

## 2. Qué se reutiliza

| Pieza | Dónde | Estado |
|---|---|---|
| `GET /suppliers/profile-import?rut=` | `app/infrastructure/routers/supplier.py` | Sin cambios. Valida el DV antes de consultar la fuente y responde 400, 404, 502 o 503 con un `detail` en español. |
| `importCompanyProfile` y `CompanyProfileImport` | `services/supplierService.ts` | Sin cambios. |
| `CompanyImportCard` | `components/CompanyImportCard.tsx` | Se mueve del paso 2 al paso 1. |
| Acción `IMPORT` | `hooks/useProfileWizard.ts` | Hoy solo une rubros. Se amplía. |
| `step1Schema.shape.rut` | `profileSchema.ts` | Valida el RUT antes de importar. |
| `Badge` y `ChipSelect` | `features/shared/components/` | `ChipSelect` recibe la prop `disabled`. |

Las rutas de frontend son relativas a `monorepo/frontend/src/features/company-profile/`.

## 3. Decisiones

1. **Solo el wizard de creación.** La "vista de edición" del CA4 son los pasos del
   wizard. Una vez creada la empresa, el RUT no se puede cambiar: `CompanyView` lo
   muestra como no editable y `PATCH /suppliers/me` no lo acepta. Esta HU no cambia eso.
2. **El usuario dispara la importación.** El botón está en el paso 1, debajo del RUT.
   No se consulta al escribir ni en `onBlur`, porque cada consulta a la fuente se paga.
3. **El RUT inválido no sale del navegador (CA1).** La tarjeta valida con
   `step1Schema.shape.rut`. Si falla, el campo RUT muestra el error y no se llama al
   servicio.
4. **Ningún error de la fuente bloquea (CA2).** `describeImportError(err)` devuelve
   `{ kind, message }`. El 404 se muestra como aviso informativo. El 502, el 503 y el
   timeout se muestran como advertencia. "Siguiente" sigue habilitado en todos los casos.
5. **Cómo se aplica el borrador (CA3).** La razón social se reemplaza si la fuente trae
   un valor. Las regiones y los rubros se suman a los ya elegidos, sin duplicar y
   descartando lo que no está en `REGIONS` o `SECTORS`. Las palabras clave siguen como
   sugerencias del paso 3 y no se marcan.
6. **Reimportar con otro RUT.** Aplica solo dentro del wizard, antes de guardar. Si el
   usuario vuelve al paso 1, cambia el RUT y aprieta "Importar datos", se vacían la
   razón social, las regiones y los rubros, y se aplica la importación nueva. Con el mismo RUT se aplica la regla 5 y los tres campos vuelven
   a quedar pendientes.

   Si el usuario cambia el RUT después de importar y no vuelve a importar, la
   importación se descarta al escribir en el campo: se quitan la razón social, las
   regiones y los rubros importados, aunque ya estén confirmados, y la tarjeta vuelve a
   ofrecer "Importar datos". Lo elegido a mano se conserva. Sin esto, la empresa se
   guardaría con el RUT nuevo y los datos de la empresa del RUT anterior.
7. **Revisión por campo (CA4).** Cada campo importado (razón social, regiones, rubros)
   muestra la insignia "Pendiente de revisión" y queda de solo lectura, con tres botones:
   - Confirmar: la insignia cambia a "Revisado".
   - Editar: habilita el campo. Sigue pendiente hasta que el usuario aprieta Confirmar.
   - Borrar: vacía la razón social, o quita de la lista solo las regiones o rubros que
     trajo la importación. El campo deja de estar en revisión.

   Regiones y rubros se confirman como lista completa, no chip por chip.
8. **Bloqueo por paso.** El "Siguiente" de un paso queda deshabilitado mientras ese paso
   tenga un campo importado sin confirmar: razón social en el paso 1, regiones en el 2 y
   rubros en el 3. `ProfileWizard.handleSubmit` repite el chequeo antes de
   `createSupplier`.
9. **Término de giro.** Si `is_active` es `false`, se precarga igual y se muestra el
   aviso que ya genera el backend.
10. **La confirmación no se guarda.** Es una regla de la interfaz. `POST /suppliers` no
    cambia y no hay migración.

## 4. Fuera de alcance

- Importar o resincronizar desde `CompanyView` (editar perfil).
- Cambios en el backend. Sus tests actuales ya cubren 401, 200, 400, 404, 502 y 503.
- Botón "Reintentar", aviso nuevo de razón social vacía, `summary` en OpenAPI y tests
  de Playwright.
- Guardar en la base quién confirmó los datos importados o cuándo.

## 5. Estado del reducer

En `hooks/useProfileWizard.ts`:

```ts
export type ImportedField = "legal_name" | "regions" | "sectors";
export type ReviewStatus = "pending" | "editing" | "confirmed";

interface ImportReview {
  /** RUT de la última importación, para detectar la reimportación con otro RUT. */
  rut: string | null;
  status: Partial<Record<ImportedField, ReviewStatus>>;
  /** Lo que sumó la importación. Borrar quita solo esto. */
  added: { regions: string[]; sectors: string[] };
}
```

Acciones nuevas: `CONFIRM_FIELD`, `EDIT_FIELD` y `CLEAR_FIELD`, todas con un
`ImportedField`. El hook expone `isStepBlocked(step)`, que es verdadero si algún campo
del paso está en `pending` o `editing`.

Los pasos guardan sus valores en formularios de react-hook-form. Cuando una acción
cambia un valor (importar o borrar), el paso montado también llama a `setValue`. Los
pasos que se montan después toman los valores de `defaultValues`.

El componente nuevo `components/ImportedFieldReview.tsx` muestra la insignia y los tres
botones. Lo usan los pasos 1, 2 y 3.

## 6. Verificación

```bash
# monorepo/frontend
pnpm run test -- src/features/company-profile
pnpm run test
pnpm run lint

# monorepo/backend, con .venv activo (no debería cambiar nada)
pytest tests/e2e/api/test_supplier_router.py -k profile_import
```

Prueba manual con la fuente configurada en local:

1. Un RUT con DV incorrecto (`76.668.304-0`) muestra el error bajo el campo, y la
   pestaña Red no registra ninguna petición a `/suppliers/profile-import`.
2. Un RUT válido que la fuente no conoce muestra un aviso informativo, y "Siguiente"
   sigue habilitado.
3. Con `76.668.304-5`, la razón social, las regiones y los rubros llegan precargados,
   pendientes y de solo lectura. "Siguiente" se habilita al confirmar cada uno.
4. Editar y Borrar se comportan como dice la decisión 7.
5. Volver al paso 1, importar con otro RUT y comprobar que los tres campos se vacían y
   se vuelven a llenar.
