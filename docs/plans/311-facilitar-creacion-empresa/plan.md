# Plan técnico: facilitar la creación de empresa

**Issue asociada**: Refs #311 (HU-29)  
**Estado**: En revisión  
**Fecha**: 2026-10-25  
**Documento de tareas**: [tasks.md](./tasks.md)

---

## 1. Contexto y objetivo

El wizard de creación de empresa y la vista "Mi empresa" piden rubros, palabras clave y
certificaciones. Esta HdU alinea los rubros con Mercado Público, ayuda a elegir palabras
clave y agrega fecha de vencimiento a las certificaciones con alertas.

Los criterios de aceptación viven en la issue #311. Este plan registra las decisiones
técnicas; el desglose por tareas está en [tasks.md](./tasks.md).

---

## 2. Decisiones técnicas

### 2.1 Rubros de ChileProveedores (CA 1)

- **Situación actual**: `app/shared/sectors.py` y
  `frontend/src/features/company-profile/data/sectors.ts` tienen 19 rubros definidos a
  mano (el docstring de `sectors.py` ya los marca como provisionales).
- **Fuente**: la lista de rubros que ve un proveedor al inscribirse en ChileProveedores.
  Se copia tal cual, con la fecha de consulta anotada en el docstring de `sectors.py`.
  La lista exacta y su número de rubros quedan registrados en la tarea A0 antes de
  tocar código.
- **Dependencias del nombre del rubro**. Cambiar los nombres afecta a:
  - `activity_dictionary.py` y `sector_classifier.py`, que sugieren rubros desde la
    actividad del SII y desde la descripción.
  - `start_feasibility.categoria_de()`, que usa el primer rubro como clave del banco de
    preguntas.
  - `smart_question_use_case`, que busca "construcción" o "tecnología" en los rubros.
  - `field_weighting_service`, que busca el nombre del rubro en el texto de la licitación.
  - El embedding de la empresa (`sectors` está en `_MATCHING_FIELDS`).
- **Perfiles existentes**: se borran, también en producción. Las empresas actuales
  tienen rubros de la lista provisional y no se migran. El borrado lo hace un script
  (tarea A3) que:
  - recorre las tablas con FK hacia `supplier` en orden (equipo, postulaciones, anexos
    de la empresa, respuestas del banco de capacidades, ranking guardado y el resto que
    aparezca al revisar el esquema);
  - borra los puntos de la empresa en Qdrant;
  - tiene modo `--dry-run` por defecto, que solo cuenta filas;
  - lo ejecuta un humano, nunca el `preDeployCommand`.
  El entorno dev test de Railway comparte la base de producción: ejecutarlo ahí ya es
  borrar en producción.

### 2.2 Sugerencias de palabras clave por RUT (CA 2)

- **Situación actual**: el paso 2 importa el perfil con el botón "Importar datos"
  (`CompanyImportCard`, `GET /suppliers/profile-import`) y `ProfileWizard` pasa
  `importedProfile.keywords` al paso 3, donde `KeywordSuggestions` las muestra.
- **Decisión**: el botón de importar basta como "ingresar su RUT". No se precarga en
  segundo plano.
- **Cambio**: cada chip de `KeywordSuggestions` se puede aceptar o descartar con un
  clic. Los descartados no vuelven a aparecer mientras el usuario siga en el wizard, y
  "Agregar todas" ignora los descartados.

### 2.3 Sugerencias de palabras clave desde la descripción (CA 3)

- **Endpoint nuevo**: `POST /suppliers/suggest-keywords-from-description`
  - Request: `{ description: str, existing_keywords: list[str] = [] }`
  - Response: `{ suggested_keywords: list[str] }`
  - Requiere sesión, como el resto de `/suppliers`.
- **Extracción léxica, sin IA**: stopwords en español, n-gramas de una a tres palabras
  y cruce con los términos de `activity_dictionary` y `sector_classifier`. No llama a
  Gemini ni a otro servicio externo, así que es determinista y no gasta cuota.
- **Deduplicación**: contra `existing_keywords`, comparando en minúsculas y sin tildes.
- **Edición**: aceptar o quitar cuenta como editar. Las sugerencias aceptadas pasan al
  `TagInput`, donde se pueden borrar antes de guardar.
- **Frontend**: botón "Sugerir palabras clave desde la descripción" junto al campo
  `description` del paso 3. Muestra las sugerencias con `KeywordSuggestions`.

### 2.4 Certificaciones con fecha de vencimiento (CA 4)

- `supplier.certifications` sigue en la misma columna JSON. Cada elemento pasa de
  string a objeto:
  ```python
  class CertificationItem(BaseModel):
      name: str
      expires_at: date | None = None
  ```
- **Compatibilidad**: la entidad y los esquemas aceptan strings sueltos de registros
  antiguos y los convierten en `CertificationItem`. No hace falta migración de Alembic.
- **Validación en la API**: `name` se recorta y no puede quedar vacío, y la lista se
  deduplica por nombre en minúsculas y sin tildes, conservando la primera aparición.
- La propiedad `Supplier.certification_names` reemplaza a `', '.join(certifications)`
  en prompts, texto del embedding y catálogo de experiencia.
- **Cambio de contrato**: `GET /suppliers/me` devuelve objetos en vez de strings. Dentro
  del repositorio solo `company-profile` lee el campo.
- **Frontend**: `CertificationListInput` reemplaza a `TagInput` en el paso 3 del wizard
  y en `CompanyEditForm`. Pide nombre y, opcionalmente, fecha.
- Lo que el usuario escribe y no agrega con el botón se pierde al avanzar, igual que con
  `TagInput`. Se acepta así.

### 2.5 Alertas de certificaciones vencidas o por vencer (CA 5)

- `utils/certification.ts` calcula el estado comparando días de calendario:
  - `expired`: la fecha ya pasó. Badge rojo "Vencida".
  - `expiring_soon`: vence entre hoy y 30 días. Badge ámbar "Vence en X días".
  - `valid` o `no_date`: sin badge.
- La alerta se muestra solo en `CompanyView` ("Mi empresa"). El paso 4 del wizard
  muestra la fecha sin badge.
- Cada certificación tiene "Editar fecha" y "Eliminar" (con confirmación). Ambos
  guardan con `PATCH /suppliers/me`.

### 2.6 Fuera de este plan

- Las respuestas del banco de capacidades también guardan vigencia de certificaciones
  (`valid_until`, plan 230) y no se sincronizan con `supplier.certifications`. Se
  dejan separadas y se abre una issue para unificarlas.

---

## 3. Verificación

```bash
# Backend (monorepo/backend, con .venv activo)
pytest tests/unit/test_certification_backward_compatibility.py
pytest
python -m scripts.migraciones

# Frontend (monorepo/frontend)
pnpm run test src/features/company-profile
```
