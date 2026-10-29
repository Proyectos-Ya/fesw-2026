# Desglose de tareas: facilitar la creación de empresa

**Issue asociada**: Refs #311 (HU-29)  
**Plan técnico**: [plan.md](./plan.md)  
**Metodología**: TDD (Red, Green, Refactor)

Los criterios de aceptación están en la issue #311. Cada bloque indica qué CA cubre.

---

## Bloque A: rubros de Mercado Público (CA 1)

Decisiones en [plan.md §2.1](./plan.md#21-rubros-de-mercado-público-ca-1). Cada tarea de
A1 a A4 va en su propio commit; A5 se hace después de desplegar.

### A0. Registrar la lista oficial
- [x] Fuente: `Listado_rubros_ONU.xlsx` de Datos Abiertos de ChileCompra, consultado el
  2026-10-26.
- [x] 58 rubros de primer nivel (19 Servicios, 35 Bienes, 4 `SinInfo`), sin `x` ni
  `eCommerce`. Tienen 362 rubros de segundo nivel, que no se usan.
- [x] Copiar los 58 nombres, la URL y la fecha en `monorepo/backend/app/shared/sectors.py`
  (se hace dentro de A1). Se copian del Excel, no de este documento.

### A1 (backend). Lista nueva y diccionarios que sugieren rubros
- **Archivos**:
  - `monorepo/backend/app/shared/sectors.py`
  - `monorepo/backend/app/application/services/company_profiling/activity_dictionary.py`
  - `monorepo/backend/app/application/services/company_profiling/sector_classifier.py`
  - `monorepo/backend/tests/unit/application/test_company_profiling.py`
  - Tests que hoy esperan nombres viejos y hay que actualizar:
    `tests/unit/application/test_import_company_profile_use_case.py`,
    `tests/e2e/api/test_supplier_router.py`,
    `tests/unit/application/test_start_feasibility.py`,
    `tests/unit/application/test_capability_use_cases.py`,
    `tests/unit/shared/test_slug.py`
- [x] **[Red]** En `test_company_profiling.py`: `PRODUCT_SECTORS` tiene 58 rubros, sin
  repetidos, en el orden de `SECTOR_GROUPS`; todo rubro que sugieren el diccionario y el
  clasificador existe en la lista (el test actual, que debe seguir pasando).
- [x] **[Red]** Casos de clasificación con la tabla de correspondencia del plan: una
  actividad SII de construcción sugiere "Servicios de construcción y mantenimiento";
  una descripción de desarrollo de software sugiere "Tecnologías de la información,
  telecomunicaciones y radiodifusión"; "reparación de vehículos" no sugiere ningún
  rubro de construcción.
- [x] **[Green]** `SECTOR_GROUPS` y `PRODUCT_SECTORS` derivado; reapuntar los 18 códigos
  SII, `_RULES` y `_CATCHALL_SECTORS` según la tabla; excepciones de la regla de
  reparación.
- [x] Actualizar los tests de la lista de arriba a los nombres nuevos. `pytest` en verde.
  Solo fallaban `test_import_company_profile_use_case.py` y `test_supplier_router.py`, y
  se actualizaron (5b08e52). Los demás llevan nombres viejos solo como datos y pasan
  igual, porque el backend no valida `sectors` contra `PRODUCT_SECTORS`.

### A2 (backend). Peso de rubro y banco de preguntas con los nombres nuevos
- **Archivos**:
  - `monorepo/backend/app/shared/sectors.py` (`significant_terms`, `GENERIC_SECTOR_WORDS`)
  - `monorepo/backend/app/infrastructure/services/field_weighting_service.py`
  - `monorepo/backend/app/application/use_cases/questions/smart_question_use_case.py`
  - Tests junto a cada uno
- [x] **[Red]** `significant_terms`: "Servicios de limpieza industrial" da `["limpieza"]`;
  "Tecnologías de la información, telecomunicaciones y radiodifusión" da
  `["tecnologias", "informacion", "telecomunicaciones", "radiodifusion"]`, sin comas
  ni tildes; cada uno de los 58 rubros tiene al menos un término.
- [x] **[Red]** `field_weighting_service`: una empresa de "Servicios de limpieza
  industrial" no suma peso de rubro contra una licitación de "servicios de transporte" y
  sí suma contra una de "limpieza de oficinas"; una de "Tecnologías de la información..."
  suma contra "soporte de tecnología"; "Consultoria" suma contra "consultoría". El caso
  de frase completa sigue sumando 1. Los tests actuales con rubros cortos ("TI") siguen
  pasando.
- [x] **[Red]** `smart_question_use_case`: "Obras" da `construccion`, "Tecnologías de la
  información, telecomunicaciones y radiodifusión" da `ti`, "Productos de papel" da
  `general`, con rubros de las dos categorías gana el primero, y cada clave del mapa
  existe en `PRODUCT_SECTORS`.
- [x] **[Green]** `significant_terms` y su uso en `field_weighting_service`; mapa de
  rubro a categoría en el use case.
- **Risk**: item 6 parcial. Cambia el puntaje de todas las empresas; los tests de arriba
  son los que lo cubren.
- Commits: d9928b6 y ad3ed78 (plurales en -es, que encontró el verificador).

### A3 (frontend). `SECTORS` agrupado y `SectorSelect`
- **Archivos**:
  - `monorepo/frontend/src/features/company-profile/data/sectors.ts`
  - `monorepo/frontend/src/features/company-profile/components/SectorSelect.tsx` (nuevo)
  - `monorepo/frontend/src/features/company-profile/components/__tests__/SectorSelect.test.tsx` (nuevo)
  - `monorepo/frontend/src/features/company-profile/components/steps/Step3Specialization.tsx`
  - `monorepo/frontend/src/features/company-profile/components/CompanyView.tsx`
  - `monorepo/backend/tests/unit/test_sectors_frontend_parity.py` (nuevo)
  - Tests y fixtures que hoy usan nombres viejos: `useProfileWizard.test.ts`,
    `importCompanyProfile.test.ts`, `CompanyImportCard.test.tsx`,
    `e2e/certifications-fixture/main.tsx`, `e2e/certifications.spec.ts`
- [x] **[Red]** `test_sectors_frontend_parity.py`: los títulos de grupo, los nombres y su
  orden en `sectors.ts` son iguales a `SECTOR_GROUPS`.
- [x] **[Red]** `SectorSelect`: muestra los tres grupos con su título; escribir "limpieza"
  deja visibles solo los rubros que la contienen; "tecnologia" sin tilde encuentra
  "Tecnologías..."; un rubro elegido sigue visible aunque el filtro no lo incluya;
  elegir un rubro en Servicios y otro en Bienes conserva los dos, en el orden en que se
  eligieron; quitar uno llama a `onChange` sin él.
- [x] **[Green]** `SECTOR_GROUPS` en `sectors.ts` con `SECTORS` derivado y la cabecera
  que documenta el formato; `SectorSelect`; reemplazar el `ChipSelect` de rubros en el
  paso 3 y en `CompanyView`.
- [x] Actualizar los tests y fixtures de la lista de arriba. `pnpm run test` en verde.
  Ninguno fallaba: llevan nombres viejos solo como datos. Los e2e de certificaciones
  no están commiteados y no se tocaron.

### A4 (backend). Modo `--solo-empresas` en `reset_cuentas.py`
- **Archivos**:
  - `monorepo/backend/scripts/reset_cuentas.py`
  - `monorepo/backend/tests/integration/test_reset_cuentas_compartidos.py`
- [x] **[Red]** Test de integración: con dos empresas, un `tender_digest` y un
  `attachment_processing_job` compartidos (`workspace_id` nulo) y uno de cada empresa,
  `--solo-empresas --ejecutar` borra las empresas y sus filas, y conserva los
  compartidos y las filas de `users`.
- [x] **[Red]** Sin `--ejecutar` no cambia ninguna fila e informa el conteo por tabla.
- [x] **[Red]** El modo sin `--solo-empresas` sigue haciendo lo de antes (el test actual
  pasa sin cambios).
- [x] **[Green]** Reutilizar el cierre del grafo (`_DEPENDIENTES`) con raíz `supplier`,
  borrar con `DELETE` las tablas sin `CASCADE` y luego `supplier`, y reutilizar
  `_borrar_vectores` para Qdrant.
- [x] Actualizar el docstring del script con el modo nuevo.
- **Risk**: item 1. El script borra datos; los tests prueban qué conserva.

### A5 (operación). Borrar las empresas de prueba
- [ ] Después de desplegar A1 a A4, correr
  `python -m scripts.reset_cuentas --solo-empresas` contra producción y pegar aquí la
  salida.
- [ ] Si el conteo es el esperado, correrlo con `--ejecutar`. Lo hace un humano. El
  entorno dev test comparte la base de producción.
- [ ] Anotar aquí la fecha y cuántas empresas y puntos de Qdrant se borraron.
- **Risk**: item 1. Borra datos de producción; se acepta porque son de prueba.

---

## Bloque B: sugerencias por RUT con aceptar o descartar (CA 2)

El paso 3 ya recibe `importedProfile.keywords` desde `ProfileWizard`. Falta el descarte.

### B1 (frontend). Descarte individual en `KeywordSuggestions`
- **Archivos**:
  - `monorepo/frontend/src/features/company-profile/components/KeywordSuggestions.tsx`
  - `monorepo/frontend/src/features/company-profile/components/__tests__/KeywordSuggestions.test.tsx` (nuevo)
- [x] **[Red]** Tests: un clic agrega la palabra, un clic en `×` la descarta, "Agregar
  todas" omite las descartadas y una descartada no reaparece al volver al paso 3.
- [x] **[Green]** Botón de descarte por chip. Los descartados viven en el estado del
  wizard para sobrevivir al cambio de paso.
- [x] **[Refactor]** `aria-label` "Agregar X" y "Descartar X".

---

## Bloque C: sugerencias desde la descripción (CA 3)

### C1 (backend). Extracción léxica
- **Archivos**:
  - `monorepo/backend/app/application/services/company_profiling/keyword_extractor.py` (nuevo)
  - `monorepo/backend/tests/unit/test_keyword_extractor.py` (nuevo)
- [x] **[Red]** Tests: extrae términos del texto, quita stopwords, no repite
  `existing_keywords` (sin tildes ni mayúsculas), devuelve lista vacía con texto vacío
  y prioriza los términos que existen en `activity_dictionary`.
- [x] **[Green]** Función pura, sin llamadas externas.

### C2 (backend). Endpoint `POST /suppliers/suggest-keywords-from-description`
- **Archivos**:
  - `monorepo/backend/app/application/schemas/supplier_schema.py`
  - `monorepo/backend/app/infrastructure/routers/supplier.py`
  - `monorepo/backend/tests/e2e/api/test_supplier_endpoints.py`
- [x] **[Red]** Test HTTP: con sesión devuelve 200 y las sugerencias; sin sesión, 401.
- [x] **[Green]** Ruta con `summary`, `tags` y `response_model`.

### C3 (frontend). Botón en el paso 3
- **Archivos**:
  - `monorepo/frontend/src/features/company-profile/services/supplierService.ts`
  - `monorepo/frontend/src/features/company-profile/services/__tests__/supplierService.test.ts`
  - `monorepo/frontend/src/features/company-profile/components/steps/Step3Specialization.tsx`
- [x] **[Red]** Tests de `suggestKeywordsFromDescription` y del botón (carga, resultado y
  error).
- [x] **[Green]** Botón "Sugerir palabras clave desde la descripción". Las sugerencias se
  muestran con `KeywordSuggestions` y las aceptadas van al `TagInput`.

---

## Bloque D: certificaciones con fecha de vencimiento (CA 4)

### D1 (backend). `CertificationItem` y compatibilidad con strings
- [x] **[Red]** `test_certification_backward_compatibility.py`: strings, dicts, mezcla,
  `certification_names` y serialización a JSON en el repositorio.
- [x] **[Green]** `CertificationItem`, `normalize_certifications` y
  `Supplier.certification_names`; esquemas de creación y edición.

### D2 (frontend). Esquema Zod
- [x] **[Red]** `profileSchema.test.ts` con strings y objetos con fecha.
- [x] **[Green]** `certificationItemSchema` y `step3Schema`.

### D3 (frontend). `CertificationListInput`
- [x] **[Red]** Agregar con y sin fecha, quitar, ignorar nombres vacíos.
- [x] **[Green]** Componente nuevo.

### D4 (frontend). Wizard, resumen del wizard y edición de empresa
- **Archivos**: `Step3Specialization.tsx`, `Step4Summary.tsx` y `CompanyEditForm`
  (dentro de `CompanyView.tsx`).
- [x] **[Red]** Las certificaciones con fecha llegan del paso 3 al paso 4.
- [x] **[Green]** `CertificationListInput` en el paso 3 y en `CompanyEditForm`; fecha
  visible en el paso 4.

### D5 (backend). Validación en la API
- **Archivos**:
  - `monorepo/backend/app/domain/entities/supplier.py`
  - `monorepo/backend/app/infrastructure/repositories/supplier_model.py`
  - `monorepo/backend/tests/unit/test_certification_backward_compatibility.py`
- [x] **[Red]** Tests: nombre vacío o con solo espacios da error de validación, el nombre
  se recorta y los duplicados (sin tildes ni mayúsculas) se eliminan conservando el
  primero.
- [x] **[Green]** `min_length=1` y recorte en `CertificationItem.name`; deduplicación en
  `normalize_certifications`.
- [x] **[Refactor]** Tipar `SupplierModel.certifications` como lo que guarda la columna
  (dicts, o strings en registros antiguos).

---

## Bloque E: alertas en "Mi empresa" (CA 5)

### E1 (frontend). `getCertificationStatus`
- [x] **[Red]** Fechas pasadas, entre 0 y 30 días, más de 30 días, sin fecha y fechas
  imposibles.
- [x] **[Green]** `utils/certification.ts`.

### E2 (frontend). Badges en `CompanyView`
- [x] **[Red]** Vencida muestra badge rojo y por vencer muestra badge ámbar con los días.
- [x] **[Green]** Badges por certificación.

### E3 (frontend). Editar fecha y eliminar en `CompanyView`
- [x] **[Red]** Editar fecha llama a `updateSupplier`; eliminar pide confirmación y
  actualiza la lista.
- [x] **[Green]** Controles por certificación.

---

## Bloque F: verificación

- [ ] **F1**: `pytest` en `monorepo/backend`.
- [ ] **F2**: `python -m scripts.migraciones` (una sola cabeza; esta HdU no agrega
  migraciones).
- [ ] **F3**: `pnpm run test` en `monorepo/frontend`.
- [ ] **F4**: sin `any`, Ruff y ESLint limpios.

## Bloque G: seguimiento

- [ ] Abrir una issue para unificar la vigencia de las respuestas del banco de
  capacidades (`valid_until`) con `supplier.certifications`.
