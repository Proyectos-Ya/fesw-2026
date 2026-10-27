# Plan técnico: facilitar la creación de empresa

**Issue asociada**: Refs #311 (HU-29)  
**Estado**: En revisión  
**Fecha**: 2026-10-25 (sección 2.1 rehecha el 2026-10-26)  
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

### 2.1 Rubros de Mercado Público (CA 1)

**Resumen**: los 19 rubros provisionales se reemplazan por los 58 rubros de primer nivel
del catálogo ONU de ChileCompra. Los nombres largos obligan a filtrar palabras genéricas
en el matching léxico, el paso 3 agrupa y filtra los rubros, y las empresas actuales se
borran con un modo nuevo de `scripts/reset_cuentas.py` que no toca las cuentas ni los
datos compartidos.

| Tema | Decisión |
|---|---|
| Fuente | `Listado_rubros_ONU.xlsx` de Datos Abiertos de ChileCompra (`https://transparenciachc.blob.core.windows.net/oc-da/Listado_rubros_ONU.xlsx`), consultado el 2026-10-26. La URL y la fecha van en el docstring de `sectors.py`. |
| Nivel | Solo el primer nivel (columna `Nivel1`). El catálogo tiene 362 rubros de segundo nivel; quedan fuera de esta HdU. El primer nivel cumple el CA 1 (decisión del 2026-10-26). |
| Cantidad | 58 rubros: 19 de tipo Servicios, 35 de Bienes y 4 de tipo `SinInfo` (Obras, Obras MINVU, Servicios de construcción y mantenimiento, y Organizaciones y consultorías políticas, demográficas, económicas, sociales y de administración pública). Se excluyen `x` y `eCommerce`. |
| Nombres | Se copian tal cual del Excel, con sus mayúsculas y tildes (por ejemplo "Consultoria", sin tilde). |
| Agrupación | Seis grupos por rangos de segmentos UNSPSC (cada rubro es un segmento, según los dos primeros dígitos de `CodigoProducto`): Materias primas (10-15, 6), Maquinaria y equipamiento industrial (20-27, 8), Componentes y suministros (30-41, 6), Productos de uso final (42-60, 15), Servicios (70-94, 20) y Obras y consultorías de ChileCompra (Obras, Obras MINVU y Consultoria, 3). Tecnologías de la información (43) va en Servicios porque ChileCompra lo marca como servicio. Dentro de cada grupo, orden de segmento. Decisión del 2026-10-27; reemplaza los tres grupos por `Tipo`, que dejaban 35 rubros en Bienes. |

#### Una sola lista y su copia en el frontend

- `PRODUCT_SECTORS` sigue siendo una tupla plana de strings, así que `Supplier.sectors`
  no cambia de forma y no hace falta migración.
- `sectors.py` agrega `SECTOR_GROUPS`, de la que se deriva `PRODUCT_SECTORS`.
- `sectors.ts` repite los mismos grupos. Un test de backend lee `sectors.ts` y falla si
  los títulos de grupo, los nombres o su orden no coinciden con `SECTOR_GROUPS`.
  - `sectors.ts` usa un formato fijo, documentado en su cabecera: un string por línea,
    entre comillas dobles, y cada grupo abre con `title: "..."`. El test lo lee con
    expresiones regulares sobre ese formato.
  - Corre en el job `test-unit-backend` del CI, que tiene el repositorio completo. La
    imagen Docker del backend no corre tests.
- Se descartó un endpoint `GET /sectors`: agrega una petición al wizard para una lista
  que cambia una vez por año.
- El test que exige que todo rubro sugerido exista en la lista ya está en
  `tests/unit/application/test_company_profiling.py`. Se extiende ese, no se crea otro.

#### Quién depende del nombre del rubro

| Consumidor | Qué hace con el nombre | Cambio |
|---|---|---|
| `activity_dictionary.py` (18 códigos SII) y `sector_classifier.py` (`_RULES`, `_CATCHALL_SECTORS`) | Sugieren rubros desde la actividad del SII y la descripción | Reapuntar cada regla a un rubro nuevo |
| `field_weighting_service.py:62-92` | Suma el 25% de peso de rubro si el nombre completo o cualquier palabra de 4 letras o más aparece en el resumen de la licitación | Usar solo palabras significativas (ver abajo) |
| `rank_tenders.py:424` | Mete los rubros en la búsqueda léxica BM25 junto con las palabras clave | Ninguno. La colección usa `Modifier.IDF` (`qdrant_lexical_tender_repository.py:50`), que ya baja el peso de las palabras comunes, y el tokenizador quita tildes y stopwords |
| `smart_question_use_case.py:33-46` | Elige la categoría del banco de preguntas | Mapa explícito de rubro a categoría (ver abajo) |
| `start_feasibility.categoria_de()` | Usa el slug del primer rubro como `capability_question.category` | Ninguno. Las preguntas guardadas con slugs viejos quedan sin uso; se acepta |
| Embedding de la empresa, prompts de Gemini, `text_builder`, `create_supplier`, `build_experience_catalog` | Unen los rubros en un texto | Ninguno |

#### Correspondencia de los rubros viejos

Las reglas de `activity_dictionary` y `sector_classifier` hoy apuntan a los 19 rubros
viejos. Cada regla se reapunta según esta tabla:

| Rubro viejo | Rubro nuevo |
|---|---|
| Obras de Construcción e Infraestructura | Servicios de construcción y mantenimiento |
| Mantención y Reparación | Servicios de construcción y mantenimiento; la reparación doméstica (952200 y su glosa) va a Servicios de cuidado personal y domésticos (ver las excepciones abajo) |
| Arquitectura e Ingeniería | Servicios basados en ingeniería, ciencias sociales y tecnología de la información |
| Tecnología y Telecomunicaciones | Tecnologías de la información, telecomunicaciones y radiodifusión |
| Desarrollo de Software | Tecnologías de la información, telecomunicaciones y radiodifusión |
| Consultoría y Asesoría Técnica | Servicios profesionales, administrativos y consultorías de gestión empresarial |
| Salud y Equipamiento Médico | Salud, servicios sanitarios y alimentación; lo farmacéutico (464907 y la raíz FARMAC) va a Medicamentos y productos farmacéuticos |
| Educación y Capacitación | Educación, formación, entrenamiento y capacitación |
| Transporte y Logística | Servicios de transporte, almacenaje y correo |
| Alimentación y Gastronomía | Servicios de Viajes, alimentación, alojamiento y entretenimiento (restaurantes y comida preparada); Alimentos, bebidas y tabaco (cultivo, producción y venta de alimentos) |
| Limpieza y Aseo Industrial | Servicios de limpieza industrial |
| Seguridad y Vigilancia | Servicios de defensa nacional, orden público y seguridad |
| Medio Ambiente y Sustentabilidad | Servicios medioambientales |
| Energía y Electricidad | Maquinaria para generación y distribución de energía |
| Servicios de Imprenta y Diseño | Servicios editoriales, de diseño, publicidad, gráficos y artistas |
| Jardinería y Paisajismo | Servicios agrícolas, pesqueros, forestales y relacionados con la fauna |
| Equipos e Insumos Industriales (también `_CATCHALL_SECTORS`) | Artículos de fabricación y producción |
| Recursos Humanos | Servicios profesionales, administrativos y consultorías de gestión empresarial |
| Contabilidad y Auditoría | Servicios financieros, pensiones y seguros |

Excepciones: la regla de reparación del clasificador (REPARACION, MANTENCION,
MANTENIMIENTO) también se dispara con la reparación de vehículos, maquinaria,
equipos informáticos, software o aparatos domésticos. Apuntada a un rubro de
construcción, esas empresas recibirían preguntas MOP/MINVU. Se le agregan
excepciones para esos casos. La reparación de aparatos domésticos tiene su propia
regla, que apunta a Servicios de cuidado personal y domésticos, el rubro donde el
catálogo ONU pone ese servicio.

#### Palabras genéricas en el matching léxico

Hoy `field_weighting_service` suma 0,75 del peso de rubro si **cualquier** palabra de 4
letras o más del rubro aparece en el resumen de la licitación. Con los nombres ONU,
palabras como "Servicios", "Equipos", "suministros" o "Artículos" aparecen en casi toda
licitación, así que casi todas las empresas sumarían ese peso.

- `sectors.py` expone `significant_terms(sector) -> list[str]`:
  - quita la puntuación ("información," pasa a "información"), pasa a minúsculas y quita
    las tildes;
  - deja las palabras de 4 letras o más que no estén en `GENERIC_SECTOR_WORDS`.
- `GENERIC_SECTOR_WORDS` es una lista escrita a mano en `sectors.py`: servicios,
  servicio, equipos, equipamiento, suministros, articulos, accesorios, productos,
  relacionados, industria, industrial, general, y los conectores "para", "sobre",
  "entre", "desde", "hasta".
- `field_weighting_service` busca primero la frase completa, como hoy. Después busca
  cada término de `significant_terms` contra el resumen de la licitación también sin
  tildes, y acepta singular y plural: el término `tecnologias` encuentra "tecnología"
  y "tecnologías".
- Un test recorre los 58 rubros y exige que cada uno tenga al menos un término
  significativo. Si alguno queda vacío, se ajusta la lista de genéricas, no el test.

#### Categoría del banco de preguntas

Hoy no funciona: el use case compara cada rubro por igualdad con "construcción" o
"tecnología", y ningún rubro se llama así. Además devuelve `"construction"`, pero
`smart_question_service` espera `"construccion"`, `"obras_civiles"` o `"constructora"`.

Se reemplaza por un mapa explícito en el use case:

| Rubros | Categoría |
|---|---|
| Obras; Obras MINVU; Servicios de construcción y mantenimiento; Artículos para estructuras, obras y construcciones; Maquinaria para construcción y edificación | `construccion` |
| Tecnologías de la información, telecomunicaciones y radiodifusión; Servicios basados en ingeniería, ciencias sociales y tecnología de la información | `ti` |
| Cualquier otro | `general` |

Si la empresa tiene rubros de las dos categorías, gana el primero de su lista.

- Un test exige que cada clave del mapa exista en `PRODUCT_SECTORS`, para que un nombre
  mal copiado no caiga en `general` sin aviso.
- Efecto visible: las ramas `construccion` y `ti` de `smart_question_service`, hoy
  inalcanzables, empiezan a ofrecerse. Las empresas de obras reciben las preguntas
  MOP/MINVU. Es lo que esas ramas buscaban; se corrige en esta HdU porque el cambio de
  nombres obliga a rehacer el mapa igual.

#### Paso 3 con 58 rubros

- `ChipSelect` (compartido) no cambia. En `company-profile` se agrega
  `SectorSelect`, que muestra los grupos con su título, cada uno con un
  `ChipSelect`, y un campo de texto que filtra por nombre sin distinguir tildes ni
  mayúsculas.
- Los grupos empiezan plegados (decisión del 2026-10-27, porque 58 chips a la vista
  eran demasiados). La cabecera de cada grupo dice cuántos rubros tiene y cuántos
  están elegidos ("Servicios (19) · 1 elegido") y se abre o cierra con un clic.
  Mientras hay texto en el buscador se abren solos los grupos con coincidencias y se
  ocultan los que no tienen; al borrar la búsqueda vuelven a como los dejó el
  usuario.
- Se usa en el paso 3 del wizard y en la edición de `CompanyView`.
- A cada `ChipSelect` le pasa como `options` los rubros del grupo que pasan el filtro
  más los ya elegidos de ese grupo, para que un rubro elegido no desaparezca al filtrar.
- A cada `ChipSelect` le pasa la selección completa, no la del grupo, y `onChange`
  devuelve la selección completa. Así elegir en un grupo no borra lo elegido en otro, y
  se conserva el orden de selección, que importa porque `categoria_de()` y el mapa del
  banco de preguntas usan el primer rubro.

#### Empresas existentes

Se borran todas, también en producción: son pocas y todas de prueba (decisión del
2026-10-26). No se migran a los rubros nuevos.

`scripts/reset_cuentas.py` no sirve tal como está. Hace `TRUNCATE ... CASCADE`, que
vacía tablas enteras sin mirar el `ON DELETE`. Solo aparta los anexos compartidos de
`attachment_file`, así que también vaciaría las filas compartidas (`workspace_id`
nulo) de `attachment_processing_job` y `tender_digest`, que cuestan llamadas a Gemini.
Además borraría todas las cuentas de `users`, y eso esta HdU no lo pide.

Se agrega a `reset_cuentas.py` un modo `--solo-empresas` (tarea A4) que reutiliza su
cierre del grafo de claves foráneas en `pg_constraint` y su borrado en Qdrant, pero:

- borra con `DELETE`, no con `TRUNCATE`, en una transacción. Primero borra las filas de
  las empresas en las tablas que apuntan a `supplier` sin `CASCADE` (hoy
  `deep_analysis`, `matching_result`, `quotation`, `tender_ai_analysis`), en el orden
  que da el grafo, y después `DELETE FROM supplier`. El resto lo resuelve el `ON DELETE`
  de cada clave foránea, que no toca las filas con `workspace_id` nulo;
- no toca `users`. Las cuentas siguen y vuelven a pasar por el wizard;
- sin `--ejecutar` imprime cuántas filas borraría por tabla y cuántos puntos de Qdrant;
- después del commit borra los puntos de esas empresas en la colección `suppliers`.

Lo ejecuta un humano después del despliegue de A1 a A4 (tarea A5), nunca el
`preDeployCommand`. Antes de `--ejecutar` se guarda la salida del modo de prueba en
`tasks.md`.
  El entorno dev test de Railway comparte la base de producción: ejecutarlo ahí ya es
  borrar en producción.
- No hace falta regenerar embeddings: las empresas nuevas se embeben al crearse.

### 2.2 Sugerencias de palabras clave por RUT (CA 2)

- **Situación actual**: el paso 2 importa el perfil con el botón "Importar datos"
  (`CompanyImportCard`, `GET /suppliers/profile-import`) y `ProfileWizard` pasa
  `importedProfile.keywords` al paso 3, donde `KeywordSuggestions` las muestra.
- **Decisión**: el botón de importar basta como "ingresar su RUT". No se precarga en
  segundo plano.
- **Cambio**: cada chip de `KeywordSuggestions` se puede aceptar o descartar con un
  clic. Los descartados no vuelven a aparecer mientras el usuario siga en el wizard, y
  "Agregar todas" ignora los descartados.
- **Cobertura** (2026-10-27): las palabras clave salen solo del diccionario curado, y
  solo 18 de los 674 códigos del SII tenían. Se curaron 53 más, elegidos de los 15
  rubros con más gasto del Estado, con palabras tomadas del vocabulario de productos de
  `Listado_rubros_ONU.xlsx`. Un código sin curar sigue sin sugerencias y muestra el
  aviso "agrégalas a mano". Se descartó usar la glosa del SII como respaldo: probada
  sobre 10 códigos, la mitad de las sugerencias eran lenguaje tributario ("mayor de
  maquinaria", "a cambio de una retribución").

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
- **Validación en la API**: `name` se recorta, deja un solo espacio entre palabras y
  no puede quedar vacío. La lista se deduplica conservando la primera aparición, con
  una clave que ignora mayúsculas, tildes, espacios, guiones, puntos y guiones bajos:
  "ISO-9001" e "iso 9001" son la misma, pero "ISO 9001:2015" no, porque una base puede
  exigir la versión. El texto que escribió el usuario se guarda tal cual, sin pasarlo a
  mayúsculas (decisión del 2026-10-27).
- `CertificationListInput` usa la misma clave (`certificationKey` en
  `utils/certification.ts`) y rechaza el duplicado al agregarlo, en vez de que la API
  lo descarte al guardar.
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
- En el paso 3 y en el editor de "Mi empresa", `CertificationListInput` avisa "Esta
  certificación ya está vencida." bajo una certificación con fecha pasada. No impide
  guardarla: las fechas son declarativas y el CA 5 necesita poder señalarla.
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
pytest tests/unit/application/test_company_profiling.py
pytest tests/unit/test_sectors_frontend_parity.py
pytest tests/integration/test_reset_cuentas_compartidos.py
pytest
python -m scripts.migraciones

# Frontend (monorepo/frontend)
pnpm run test src/features/company-profile
```
