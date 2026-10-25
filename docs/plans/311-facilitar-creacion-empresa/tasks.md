# Desglose de tareas: facilitar la creación de empresa

**Issue asociada**: Refs #311 (HU-29)  
**Plan técnico**: [plan.md](./plan.md)  
**Metodología**: TDD (Red, Green, Refactor)

Los criterios de aceptación están en la issue #311. Cada bloque indica qué CA cubre.

---

## Bloque A: rubros de ChileProveedores (CA 1)

### A0. Registrar la lista oficial
- [ ] Copiar la lista de rubros de ChileProveedores, con su fecha de consulta, en el
  docstring de `monorepo/backend/app/shared/sectors.py`.
- [ ] Anotar aquí cuántos rubros tiene y si alguno tiene subrubros.

### A1 (backend). Reemplazar `PRODUCT_SECTORS` y lo que depende del nombre
- **Archivos**:
  - `monorepo/backend/app/shared/sectors.py`
  - `monorepo/backend/app/application/services/company_profiling/activity_dictionary.py`
  - `monorepo/backend/app/application/services/company_profiling/sector_classifier.py`
  - `monorepo/backend/app/application/use_cases/questions/smart_question_use_case.py`
  - `monorepo/backend/app/infrastructure/services/field_weighting_service.py`
  - `monorepo/backend/tests/unit/test_sectors_alignment.py` (nuevo)
- [ ] **[Red]** `test_sectors_alignment.py`: `PRODUCT_SECTORS` es la lista de A0, y todo
  rubro que sugieren el diccionario y el clasificador existe en ella.
- [ ] **[Red]** Test de `smart_question_use_case` que elige la categoría correcta con los
  nombres nuevos.
- [ ] **[Green]** Actualizar la lista, el mapeo de actividades, las palabras del
  clasificador y las reglas de `smart_question_use_case`.
- [ ] **[Refactor]** Confirmar que `field_weighting_service` sigue sumando con nombres
  largos (busca la frase completa y luego palabras sueltas).

### A2 (frontend). Sincronizar `SECTORS`
- **Archivos**:
  - `monorepo/frontend/src/features/company-profile/data/sectors.ts`
  - `monorepo/frontend/src/features/company-profile/components/__tests__/Step3Specialization.test.tsx`
- [ ] **[Red]** Test que renderiza los rubros nuevos en el `ChipSelect` del paso 3 y
  permite elegirlos.
- [ ] **[Green]** Copiar la lista de A0 en `sectors.ts`.

### A3 (backend). Script de borrado de perfiles antiguos
- **Archivos**:
  - `monorepo/backend/scripts/borrar_perfiles_antiguos.py` (nuevo)
- [ ] Listar en el script todas las tablas con FK hacia `supplier`, en orden de borrado.
- [ ] Modo `--dry-run` por defecto: imprime cuántas filas borraría por tabla y cuántos
  puntos de Qdrant.
- [ ] Con `--ejecutar`, borra todo en una transacción de Postgres y después los puntos
  de Qdrant de esas empresas.
- [ ] Lo ejecuta un humano después del despliegue de A1 y A2. El entorno dev test
  comparte la base de producción.

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
