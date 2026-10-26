# ADR-0002: Confianza de Anexos Compartidos

* **Fecha**: 2026-10-04  
* **Estado**: Propuesto  
* **Autores**: Equipo Chiripa  

---

## 1. Contexto

El plan 233 introduce la capacidad de adjuntar documentos oficiales de licitaciones (anexos de Mercado Público) para extraer su contenido con Gemini. Dado que múltiples empresas MiPymes licitan sobre las mismas convocatorias, compartir los documentos oficiales ahorra cupo, tiempo y costos de almacenamiento/procesamiento.

Sin embargo, compartir archivos entre empresas independientes introduce tensiones críticas:

1. **Privacidad y ausencia de oráculos:** Ninguna empresa debe poder deducir si un competidor está trabajando o subiendo antecedentes a una licitación. Si subir un archivo cualquiera revelara inmediatamente un "conflicto de versiones", la funcionalidad actuaría como un oráculo de espionaje industrial. Asimismo, un archivo compartido jamás debe exponer metadatos de la empresa o persona que lo aportó.
2. **Ciclo de vida y cascada de borrado (`ON DELETE CASCADE` y `TRUNCATE`):** En el modelo de datos, los aportes pertenecen a una empresa (`supplier`). Cuando una empresa es borrada o cuando se resetean las cuentas con `scripts/reset_cuentas.py`, el borrado en cascada no debe hacer desaparecer los documentos ya validados que benefician a la comunidad.
3. **Resistencia a ataques de denegación de servicio (DoS) y cuentas títere:** Un usuario malicioso o una empresa que suba un archivo alterado no debe poder bloquear unilateralmente la disponibilidad de los documentos oficiales ni invalidar una versión ya compartida.
4. **Concurrencia y arquitectura de base de datos:** El entorno de producción utiliza Supavisor en modo transacción. Esto imposibilita el uso de advisory locks a nivel de sesión y exige bloqueos de fila transaccionales (`FOR NO KEY UPDATE`) que no bloqueen los `INSERT` concurrentes de otras empresas.

---

## 2. Decisión Tomada

Se adopta el **modelo de fila canónica independiente y evaluación pura de confianza** (Decisión 6 del plan 233), estructurado en los siguientes principios:

### Resumen de Decisiones de Diseño (D6-1 a D6-14)

* **D6-1 (Fila canónica compartida):** La versión compartida es una fila independiente en `attachment_file` con `workspace_id = NULL`, `uploader_user_id = NULL`, `visibility = 'shared'`, `trust = 'corroborated'`, `status = 'stored'`, y clave de almacenamiento `shared/{tender}/{mp_document_id}/{sha}.{ext}`. Los aportes originales de las empresas permanecen como `visibility = 'private'` y nunca pasan a compartidos; únicamente se actualiza su nivel de confianza (`trust`). Al no tener `workspace_id`, la fila canónica es inmune al `CASCADE` de `supplier`.
* **D6-2 (Invariantes estrictos en base de datos):** Se definen tres restricciones `CHECK` en `attachment_file`:
  * `ck_attachment_file_shared_sin_empresa`: `visibility = 'private' OR workspace_id IS NULL`
  * `ck_attachment_file_shared_corroborado`: `visibility = 'private' OR trust = 'corroborated'`
  * `ck_attachment_file_canonico_sin_autor`: `workspace_id IS NOT NULL OR uploader_user_id IS NULL`
  Junto con dos índices únicos parciales:
  * `uq_attachment_file_canonical_sha`: `(tender_attachment_id, sha256) WHERE workspace_id IS NULL`
  * `uq_attachment_file_shared_attachment`: `(tender_attachment_id) WHERE visibility = 'shared'`
  Estos invariantes se replican a nivel de dominio en un validador Pydantic de la entidad.
* **D6-3 (Independencia de fuentes):** Dos empresas son independientes si tienen distinto `workspace_id` y ningún usuario en común. El conjunto de usuarios de una empresa abarca su dueño histórico (`supplier.user_id`), todas sus membresías (`supplier_members`) en cualquier estado (incluyendo inactivas o revocadas) y el autor del aporte. Un usuario jamás puede corroborarse a sí mismo.
* **D6-4 (Rol de la extensión de navegador):** La extensión oficial es un canal confiable que descarga el documento directamente de Mercado Público. Un aporte vía extensión corrobora un aporte manual aunque compartan personas (salvo si es exactamente el mismo autor). Sin embargo, una captura aislada de la extensión **no** se comparte sola: requiere al menos otra fuente con el mismo hash. Si la extensión respalda una sola versión confirmada o ya compartida, arbitra y desempata.
* **D6-5 (Solo versiones respaldadas y eliminación del oráculo):** Una versión está respaldada si fue corroborada por fuentes independientes, proviene de la extensión o es la versión canónica vigente. Una subida manual aislada permanece en `pending` y no interactúa con subidas ajenas. El estado de conflicto solo surge cuando coexisten dos o más versiones respaldadas sin ganador claro.
* **D6-6 (Persistencia y estabilidad de lo compartido):** Una versión canónica compartida es "pegajosa". Dos empresas con un hash distinto no la degradan (sus aportes quedan `rejected`). Solo la extensión puede suspenderla (pasándola temporalmente a oculta en conflicto) o reemplazarla si confirma otra versión.
* **D6-7 (Decisión pura de confianza):** La función `decidir_confianza(archivos, personas)` es idempotente y recalcula exhaustivamente el estado completo de los aportes y canónicas del anexo a partir de la evidencia actual.
* **D6-8 (Candado de concurrencia y sesión propia):** La evaluación toma un bloqueo `SELECT ... FOR NO KEY UPDATE` sobre `tender_attachment`. Al ser compatible con `FOR KEY SHARE`, no bloquea subidas simultáneas (`INSERT` de aportes privados). El caso de uso de promoción se ejecuta en su propia sesión de base de datos (`PromoteOpener`).
* **D6-9 (Materialización y verificación del destino):** Al crearse la versión canónica, el archivo se copia a `shared/` priorizando la fuente de la extensión o el aporte más antiguo. Se descargan los bytes desde el destino para verificar tamaño y recalcular SHA-256 en un hilo secundario (`asyncio.to_thread`). Si no coincide, se descarta y se prueba la siguiente fuente. Los objetos privados nunca se eliminan ni modifican.
* **D6-10 (Visibilidad efectiva en API):** Los aportes propios corroborados se exponen al cliente como `visibility = 'shared'`, reflejando que su contenido ya es público para todos. Intentar borrar un aporte propio corroborado retorna `HTTP 409 (file_is_shared)`.
* **D6-11 (Recálculo en guardado y borrado):** La reevaluación se dispara al completarse una subida (`on_stored`) y al eliminarse un archivo privado (`on_deleted`).
* **D6-12 (Preservación en reseteo de cuentas):** El script `scripts/reset_cuentas.py` resguarda las canónicas en una tabla temporal `ON COMMIT DROP`, ejecuta `TRUNCATE TABLE ... CASCADE` sobre las raíces de cuentas y reinstala las canónicas dentro de la misma transacción.
* **D6-13 (Evento para extracción de texto):** Se emite `IAttachmentVisibilityListener.on_visibility_changed(file)` tras el commit para que la Decisión 4 indexe o desindexe el contenido compartido sin acoplamiento transaccional.
* **D6-14 (Ocultamiento reversible):** Si una versión canónica es cuestionada, no se borra: pasa a `visibility = 'private'` con `trust = 'conflict'` o `'rejected'`, conservando su objeto en `shared/` para un posible reuso si vuelve a ganar.

---

### Tabla de Verdad de Confianza

| Filas del anexo | Versión Ganadora | ¿Conflicto? | Confianza Aportes | Estado Canónicas |
|---|---|---|---|---|
| W1:S1 | — | No | W1: pending | — |
| W1:S1, W2:S1 | S1 (crear) | No | W1, W2: corroborated | S1: shared/corroborated |
| W1:S1 manual + W1:S1 legacy (misma empresa) | — | No | W1 manual, W1 legacy: pending | — |
| W1:S1, W2:S1 (con persona en común) | — | No | W1, W2: pending | — |
| W1:S1 (autor U7), W2:S1 (autor U7) | — | No | W1, W2: pending | — |
| W1:S1, W5:S1 ext | S1 (crear) | No | W1, W5: corroborated | S1: shared/corroborated |
| W5:S1 ext sola | — | No | W5: pending | — |
| W1:S1, W2:S2 (sueltas) | — | **No** (anti-oráculo) | W1, W2: pending | — |
| W1:S1, W2:S1, W3:S2 | S1 | No | W1, W2: corroborated; W3: rejected | S1: shared/corroborated |
| W1:S1, W2:S1, W3:S2, W4:S2 (sin canónica) | — | **Sí** | Los 4: conflict | — |
| Lo anterior + W5:S1 ext | S1 (crear) | No | W1, W2, W5: corroborated; W3, W4: rejected | S1: shared/corroborated |
| W1:S1, W2:S2, W5:S1 ext | S1 (crear) | No | W1, W5: corroborated; W2: rejected | S1: shared/corroborated |
| W1:S1, W2:S1, W5:S2 ext | — | **Sí** | Los 3: conflict | — |
| Canónica S1 shared (sin aportes) | S1 | No | — | S1: shared/corroborated |
| Canónica S1 shared, W3:S2, W4:S2 | S1 | No | W3, W4: rejected | S1: shared/corroborated |
| Canónica S1 shared, W5:S2 ext | — | **Sí** | W5: conflict | S1: private/conflict |
| Canónica S1 shared, W5:S2 ext, W3:S2 | S2 (crear) | No | W5, W3: corroborated | S1: private/rejected; S2: shared/corroborated |
| Canónica S1 private/conflict, W5:S1 ext | S1 | No | W5: corroborated | S1: shared/corroborated |
| W5:S1 ext (U5), W6:S2 ext (U6), W1:S1 | — | **Sí** | Los 3: conflict | — |

---

## 3. Alternativas Consideradas

* **Actualizar directamente los aportes de empresa a `visibility = 'shared'`:**
  *Descartada.* Si la empresa que aportó el archivo cierra su cuenta o es eliminada, el `ON DELETE CASCADE` de `supplier` eliminaría el archivo compartido para todas las demás empresas que dependían de él.
* **Foreign Key con `ON DELETE SET NULL` en `attachment_file.workspace_id`:**
  *Descartada.* Cuando una empresa se elimina, todos sus archivos privados huérfanos quedarían almacenados en la base de datos sin dueño en lugar de limpiarse, generando violaciones de privacidad y filtraciones de datos.
* **Crear una tabla separada para anexos compartidos (`shared_attachment_file`):**
  *Descartada.* Duplica la estructura de datos y modelos, complica las claves foráneas de los trabajos de extracción de texto (Decisión 4) y fragmenta las consultas de visibilidad.
* **Regla literal de conflicto ("dos sha distintos de empresas distintas generan conflicto"):**
  *Descartada.* Permitiría que cualquier usuario suba un documento arbitrario para comprobar si otra empresa tiene un archivo en esa licitación (oráculo). Además, un formulario rellenado con datos de una empresa bloquearía la posibilidad de compartir el formato en blanco hasta que existiera la extensión.
* **Uso de Advisory Locks de PostgreSQL a nivel de sesión:**
  *Descartada.* Incompatible con el pooler de conexiones en modo transacción (Supavisor) utilizado en producción, ya que los bloqueos de sesión no se liberan de forma predecible al desvincularse la conexión física.

---

## 4. Consecuencias

### Positivas (Beneficios)
- **Privacidad y confidencialidad absoluta:** Los archivos compartidos no tienen autor ni empresa asignada. Las empresas no pueden sondear la presencia de competidores mediante subidas de prueba.
- **Resiliencia ante eliminación de empresas y resets:** Los documentos oficiales sobreviven la eliminación de perfiles de proveedores y la ejecución de `reset_cuentas.py`.
- **Rendimiento y concurrencia sólida:** El uso de `FOR NO KEY UPDATE` serializa adecuadamente la promoción de versiones sin frenar el flujo concurrente de subidas privadas.
- **Idempotencia y verificabilidad:** La decisión de confianza es una función pura fácil de probar con una tabla de verdad exhaustiva. Cada copia a `shared/` valida estrictamente el hash criptográfico del contenido.

### Negativas / Compromisos (Trade-offs)
- **Señal de interés residual:** El hecho de que un anexo figure como compartido revela a cualquier visitante que al menos dos fuentes independientes subieron ese documento para esa licitación. Es una señal inherente al modelo colaborativo y aceptada en el plan 233.
- **Riesgo residual de cuentas títere:** Un usuario malicioso con dos cuentas asociadas a personas y RUTs distintos podría autocoroborar un documento. Este riesgo queda acotado por la presencia arbitradora de la extensión oficial de navegador y la falta de incentivos directos para adulterar documentos públicos de licitación.
- **Costo de almacenamiento dual:** Mantener la versión privada y la versión canónica compartida duplica temporalmente el objeto en el bucket (en `private/{ws}/` y en `shared/`). Este compromiso es necesario para soportar deduplicación y extracciones privadas sin alterar el esquema.
