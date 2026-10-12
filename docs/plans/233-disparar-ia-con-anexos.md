# Plan Técnico: Disparar hitos y análisis con la subida de un anexo

**Issue asociada**: Refs #233  
**Estado**: Completado  
**Fecha**: 2026-10-12  

---

## 1. Contexto y Objetivo

Chiripa pasa a tener una sola fuente de documentos por licitación: los anexos
oficiales (plan 233, decisiones 1, 2 y 6), que las empresas suben a R2 desde la
ficha o con la extensión. Hoy la extracción de hitos (HU-16) y el análisis +
cotización con Gemini se disparan al subir un documento al chat del asistente,
que se guarda en el disco del contenedor y se pierde en cada despliegue.

Este cambio hace que los dos se disparen al subir un anexo y que lean los anexos.
Lo que se decidió:

- **Hitos:** se extraen en el momento para quien sube el anexo. Los demás
  miembros de la empresa los reciben al abrir la ficha, si hay anexos que todavía
  no se leyeron para ellos.
- **Análisis + cotización:** con todos los anexos que la empresa ve de esa
  licitación, en una sola llamada y en segundo plano.
- **Cotización de la IA:** solo se guarda si la empresa no tiene una. No pisa la
  que el usuario armó en la postulación.

Fuera de alcance (va en la integración siguiente): que el asistente, la
factibilidad y la postulación lean solo anexos, quitar la subida al chat y que el
botón "volver a analizar" de la ficha use los anexos.

---

## 2. Decisiones Técnicas y Arquitectura

- **Punto de enganche:** `IAttachmentStoredListener.on_stored(file)`
  (`app/application/services/attachment_stored_listener.py`). Corre después de
  confirmar la subida y recibe el `AttachmentFile` con `uploader_user_id`,
  `workspace_id`, `tender_id` y `storage_key`. Ya lo usan la promoción a
  compartido y `EnqueueExtractionOnStored`. Se agregan dos listeners que solo
  agendan trabajo y no esperan a Gemini.
- **Hitos:** `ExtractTenderMilestonesUseCase` cambia de fuente. Deja los
  documentos del chat y pasa a los anexos visibles para la empresa
  (`IAttachmentFileRepository.list_visible_for_tender`), leídos con
  `IAttachmentStorage.get_bytes`. Conserva el flujo incremental de develop: un
  documento por llamada, cada uno leído una sola vez y con contadores de perdidos
  y fallidos.
  - Los hitos nuevos llevan `source_file_id`.
  - Para no duplicar, se fusionan con `merge_ai_milestones` contra todos los hitos
    de IA del usuario en la licitación, incluidos los que vinieron del chat. Un
    hito equivalente se reutiliza con su recordatorio y su evento de Google u
    Outlook.
  - Los hitos viejos del chat no se borran.
- **Registro de anexos leídos:** tabla nueva `tender_milestone_attachment`, por
  usuario y archivo. La tabla de develop (`tender_milestone_document`) apunta por
  FK a los documentos del chat y no sirve. La migración solo crea la tabla
  (compatible hacia atrás) y se encadena tras `b4c9e1d8a735`.
- **Empresa del usuario:** se toma del archivo cuando dispara la subida, y del
  contexto de empresa activa en la ficha y en la extracción manual.
- **Análisis + cotización:** caso de uso nuevo
  `AnalyzeTenderAttachmentsUseCase`, con la lógica que hoy vive en
  `UploadTenderChatDocumentUseCase`.
  - `IDocumentAnalysisAndQuotationService.analyze_and_quote` pasa a recibir varios
    documentos (`list[DocumentContextDTO]`).
  - El servicio de Gemini manda PDF y PNG dentro de la petición, XLSX como texto,
    y omite los demás tipos. Tope de unos 15 MB en total antes de codificar.
- **Segundo plano:** los hitos reutilizan `AsyncioMilestoneExtractionBackground`.
  El análisis usa uno nuevo con el mismo patrón y clave `(workspace_id,
  tender_id)`: varias subidas seguidas hacen como mucho dos llamadas. Asume una
  sola instancia de la API, como el resto de los segundos planos.
- **El chat deja de disparar:** `UploadTenderChatDocumentUseCase` vuelve a solo
  guardar el documento.
- **Seguridad:** solo crean archivos las rutas de subida de anexos, que exigen
  sesión y el permiso `upload_attachments`. Los endpoints de la extensión sin
  autenticación no crean archivos, así que no pueden disparar llamadas a Gemini.
- **Costo:** las llamadas de hitos y de análisis no cuentan en
  `ATTACHMENT_GEMINI_DAILY_BUDGET`.
- Sin dependencias ni variables de entorno nuevas.

---

## 3. Desglose de Tareas (Checklist)

### Backend
- [x] Red/Green: `ScheduleMilestonesOnStored` y `ScheduleTenderAnalysisOnStored`
      agendan con el usuario y la empresa correctos, e ignoran archivos no
      `STORED` y la versión canónica compartida. Se cuelgan en
      `app/bootstrap/attachments.py`.
- [x] Red/Green: tabla, modelo, repositorio y migración de
      `tender_milestone_attachment`. `alembic heads` debe dar una sola línea.
- [x] Red/Green: la extracción de hitos lee los anexos visibles, guarda
      `source_file_id`, no relee lo ya procesado, reutiliza los hitos
      equivalentes (incluidos los del chat), limpia los huérfanos de anexos
      borrados y no toca los sincronizados.
- [x] Red/Green: `GetTenderMilestonesUseCase` cuenta los anexos pendientes del
      usuario y agenda la extracción si no hay una en curso.
- [x] Red/Green: `analyze_and_quote` con varios documentos y tope de tamaño;
      `AnalyzeTenderAttachmentsUseCase` y su segundo plano; la cotización solo se
      guarda si no existe.
- [x] Red/Green: `GET /tenders/{id}/attachments` informa si el análisis está en
      curso.
- [x] `UploadTenderChatDocumentUseCase` vuelve a solo guardar. Sus tests del
      análisis pasan al caso de uso nuevo.
- [x] Cableado: completar la subida de un anexo agenda hitos y análisis
      (`tests/unit/test_bootstrap_attachment_uploads.py`). El e2e de subida
      necesita Postgres local y su `conftest` reemplaza los listeners.

### Frontend
- [x] Red/Green: al subir un anexo, la ficha recarga la sección de hitos
      (`milestonesRefreshKey`), como hoy lo hace el chat.
- [x] Red/Green: el panel de anexos muestra "Analizando anexos…" y la ficha
      recarga el análisis y el cotizador cuando termina.
- [x] La subida al chat vuelve al tiempo límite por defecto.

---

## 4. Plan de Verificación y Pruebas

```bash
# Backend (desde monorepo/backend, con .venv activo)
pytest
ruff check .
python -m scripts.migraciones

# Frontend (desde monorepo/frontend)
pnpm run test
pnpm exec tsc --noEmit
```

Prueba manual local, con `IS_DEV=true` y disco local en vez de R2: subir un PDF
de bases como anexo desde la ficha y ver aparecer hitos, análisis y cotización.
Usa llamadas pagadas a Gemini.

---

## 5. Parte 2: la postulación lee los anexos

Aprobada el 2026-10-12. La factibilidad y el borrador de la postulación (HU-20)
dejan de leer los documentos del chat y leen los mismos anexos que los hitos y
el análisis.

**Cambio de comportamiento:** los documentos del chat eran por usuario (plan
230, §5 punto 7). Los anexos son por empresa (los propios y los compartidos):
dos miembros de la misma empresa ven los mismos documentos en su postulación.

### Decisiones

- `adjuntos_del_usuario` (`proposals/_documentos.py`) se reemplaza por
  `anexos_de_la_empresa`, que usa `anexos_visibles` y devuelve los mismos
  `DocumentContextDTO`. Un anexo que no se puede leer va con
  `is_corrupted=True`.
- La huella del análisis y `analysis_documents` no cambian: los nombres guardados
  pasan a ser los nombres oficiales de los anexos.
- La pantalla de postulación muestra el panel de anexos de la ficha en vez de su
  propia subida al chat, así que subir desde ahí también dispara hitos y
  análisis.

Fuera de alcance: el asistente (sigue leyendo anexos y chat) y quitar la subida
al chat.

### Tareas

- [x] Red/Green: `anexos_de_la_empresa` devuelve los anexos de la empresa y los
      compartidos, y marca como dañado lo que no se puede leer.
- [x] Red/Green: la factibilidad y el borrador mandan esos anexos a la IA y
      `analysis_documents` guarda sus nombres.
- [x] Cableado en `app/bootstrap/proposals.py`.
- [x] Red/Green: `ProposalView` muestra el panel de anexos y el aviso de bases usa
      los anexos.
