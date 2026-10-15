# Plan técnico: el asistente virtual lee solo los anexos

**Issue asociada**: Refs #NNN (por crear)  
**Estado**: En curso (fase 1 implementada)  
**Fecha**: 2026-10-13

---

## 1. Contexto y objetivo

El asistente virtual responde preguntas sobre las bases de una licitación. Hoy tiene dos
fuentes de archivos:

- **Anexos** (plan 233). Se guardan en R2 con `IAttachmentStorage`, se comparten entre
  empresas según el ADR 0002 y el asistente ya los lee por la tabla `attachment_file`.
- **Documentos del chat** (`tender_chat_documents`). Se guardan en el volumen de Railway
  `chat-uploads` (50 GB, montado en `/app/storage` del servicio `fesw-2026`). El asistente
  los lee como `legacy_chat` y los fusiona con los anexos (`deduplicar_documentos_chat`).

En la práctica, los documentos del chat son los mismos anexos, subidos dos veces. Este
plan quita la carga propia del chat. El asistente lee solo los anexos de la licitación,
y el volumen de Railway desaparece.

Lo que ya está hecho en `develop`:

- `TenderAssistantDrawer` ya no ofrece subir archivos. `DocumentAttachmentManager` solo
  lista los documentos antiguos y lleva al panel de anexos (`onNavigateToPanel`).
- La extracción de hitos ya lee anexos (`tender_milestone_attachment`, migración
  `1ddfcce953b7`). La tabla vieja `tender_milestone_document` sigue apuntando a
  `tender_chat_documents`, pero nadie escribe en ella.
- `scripts/migrar_documentos_chat_a_anexos.py` copia cada documento del chat a R2 como
  `attachment_file` (`source=legacy_chat`, `visibility=private`) si su nombre coincide
  con un anexo oficial. Tiene test en `tests/unit/scripts/test_migrar_documentos_chat.py`.

Lo que falta:

- El backend todavía acepta `POST /tenders/{id}/assistant/documents` y el frontend
  conserva `uploadDocument` en el hook y el servicio.
- `AskTenderAssistantUseCase` sigue leyendo bytes del disco por
  `chat_repo.get_document_bytes` en los pases 1 y 2.
- La telemetría de prioridad de anexos (`ComputeAttachmentPriorityShadowUseCase`) cuenta
  como "subida manual" los documentos de `tender_chat_documents`.
- Producción no tiene ninguna variable `R2_*`. Sin ellas, `build_attachment_storage`
  devuelve `None` y la subida de anexos responde 503.

---

## 2. Decisiones técnicas

**D1. El asistente solo lee anexos.** Un documento que no corresponde a un anexo oficial
de la licitación no entra al contexto. Esto reemplaza la fusión con `legacy_chat` de la
decisión 5 del plan 233 (D5-6). Se registra en un ADR corto.

**D2. Los documentos antiguos se migran, no se descartan sin más.** Antes de retirar la
lectura del disco, se corre el script de migración en producción. Los documentos que no
coinciden con ningún anexo (`no_emparejados`) se pierden para el asistente. Antes de
borrar el volumen se baja una copia comprimida, que se guarda fuera de Railway por 30 días.

**D3. El retiro va en tres despliegues**, por la regla de migraciones compatibles hacia
atrás de `AGENTS.md`:

| Despliegue | Qué cambia | Por qué en este orden |
|---|---|---|
| PR 1 | Se quita la subida. El asistente sigue leyendo los documentos antiguos. | Deja de crecer el volumen sin romper lo existente. |
| Operación | Configurar R2 en producción, correr el script, respaldar y desmontar el volumen. | El script lee del volumen y escribe en R2: necesita los dos montados a la vez. |
| PR 2 | Se quita la lectura de documentos del chat, los endpoints GET y DELETE, el repositorio y el `mkdir` del `Dockerfile`. | El código deja de usar las tablas; las tablas siguen. |
| PR 3 | Migración que borra `tender_milestone_document` y `tender_chat_documents`. | Va en un despliegue posterior al que deja de usarlas. |

**D4. Sin dependencias nuevas.** Se reutilizan `IAttachmentStorage`,
`R2AttachmentStorage`, `FakeAttachmentStorage` y el script de migración. No se crean
endpoints.

**D5. Variables de entorno en producción.** `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY` y `R2_BUCKET` en el servicio `fesw-2026`. `_exigir_r2_completo`
falla al arrancar si falta alguna de las cuatro. Las carga un humano desde el panel de
Railway: escribir variables necesita confirmación explícita.

**Seguridad.** El volumen contiene archivos de empresas. La copia de respaldo se guarda
en un lugar con acceso restringido al equipo y se borra pasados los 30 días.

**El entorno `dev test` de Railway usa la misma base de datos que producción.** Correr
ahí el script con `--aplicar`, o desplegar la migración de la fase 4, escribe sobre datos
reales. Esas pruebas se hacen contra la base local de Supabase (`supabase start`).

**Cruce con la rama 305.** Las fases 1 a 3 no tocan archivos de la 305. La 305 agrega la
migración `2510718f486e` sobre `1ddfcce953b7`. Si la fase 4 se crea antes de que la 305
llegue a `develop`, habrá dos cabezas: el PR que se mergee segundo repunta su
`down_revision` con `python -m scripts.migraciones --arreglar`.

---

## 3. Desglose de tareas

### Fase 0: R2 en producción (operación, antes de llevar `develop` a `main`)

- [ ] Crear el bucket de R2 de producción y un token con permisos solo sobre ese bucket.
- [ ] Cargar las cuatro variables `R2_*` en `fesw-2026` (producción) desde el panel.
- [ ] Verificar en los logs del arranque la línea `Anexos en Cloudflare R2 (bucket ...)`.

### Fase 1: PR 1, quitar la subida del chat

Backend:
- [x] Red: en `tests/unit/infrastructure/test_tender_chat_router.py`, un test que espera
  405 en `POST /tenders/{id}/assistant/documents`. Se borraron los tests que solo
  probaban la subida: `test_upload_tender_chat_document_use_case.py`,
  `tests/integration/test_tender_chat_real_document.py` y el del límite de 10 documentos.
- [x] Green: quitar la ruta POST de `app/infrastructure/routers/tender_chat.py`, el
  proveedor de `app/bootstrap/tender_chat.py`, su registro en `app/bootstrap/routes.py`
  y `upload_tender_chat_document_use_case.py`. Se quitaron de `tender_chat_errors.py`
  los cuatro errores que quedaron sin uso.
- [x] `tests/integration/test_tender_chat_multidoc_integration.py` siembra los
  documentos en el repositorio en vez de subirlos por HTTP. Su mock de Gemini esperaba
  la clave en la query y ya fallaba en `develop`; ahora la espera en el header
  `x-goog-api-key`.
- [x] Red: test de integración del repositorio de telemetría. Cuenta como subida manual
  una fila de `attachment_file` de una empresa (`workspace_id` no nulo) con `source` en
  `manual` o `extension` de los últimos 7 días. No cuentan la copia compartida (es una
  promoción) ni lo migrado desde el chat (`legacy_chat`, con la fecha de la migración).
- [x] Green: la consulta de `ranking_telemetry_repository.py` lee `attachment_file` y el
  docstring de `ComputeAttachmentPriorityShadowUseCase` describe la regla nueva.

Frontend:
- [x] Red: `useTenderDocuments.test.ts` exige que el hook no exponga `uploadDocument` ni
  `isUploading`; se quitó el test de subida de `tenderAssistantService.test.ts`.
- [x] Green: se quitaron `uploadDocument`, `isUploading`, `canUpload` y `maxDocuments`
  del hook, `uploadTenderDocument` del servicio, la constante `MAX_ATTACHED_DOCUMENTS`
  y las props `onUpload` e `isUploading` de `DocumentAttachmentManager`.
- [x] Se quitó `onDocumentsChanged` del drawer y de `TenderDetailView`: solo avisaba
  tras subir al chat, y los hitos ya se recargan al subir un anexo.

### Fase 2: migrar y retirar el volumen (operación, después de desplegar la versión con anexos)

Todo esto pide confirmación explícita antes de ejecutarse.

- [ ] Correr el script dentro del contenedor, que es donde está montado el volumen:
  primero en simulación y después con `--aplicar --confirmar-produccion`. Guardar el
  reporte (migrados, no emparejados, sin empresa, errores) en la issue.
- [ ] Comprimir `/app/storage/chat_uploads` y bajar la copia.
- [ ] Desmontar el volumen `chat-uploads` del servicio y, tras una semana sin
  incidentes, borrarlo.

### Fase 3: PR 2, el asistente deja de leer el chat

Backend:
- [ ] Red: en `test_ask_tender_assistant_use_case.py` y
  `test_ask_tender_assistant_two_pass.py`, el contexto de los pases 1 y 2 no tiene
  ningún `DocumentContextDTO` con `source="legacy_chat"` y el caso de uso no recibe
  `chat_repo` para documentos.
- [ ] Green: quitar el paso 10 de `ask_tender_assistant_use_case.py` (lectura de
  `chat_docs`, `chat_bytes_by_id`, `legacy_con_texto`) y su uso en los pases 1 y 2.
  Quitar el parámetro `legacy_docs` de `construir_contexto_anexos` y borrar
  `deduplicar_documentos_chat` de `assistant_context_builder.py`.
- [ ] Quitar las rutas GET y DELETE de `/assistant/documents`, sus casos de uso, los
  métodos de documentos de `ITenderChatRepository` y `SQLTenderChatRepository` (incluido
  `storage_dir`), la entidad `TenderChatDocument` y `InMemoryTenderChatRepository.documents`.
- [ ] Quitar `_extraer_texto_legacy` si queda sin uso fuera del chat. Hoy también lo usan
  los anexos sin extracción (`xlsx`, `txt`): en ese caso se mueve a un nombre que no
  diga "legacy".
- [ ] Quitar el `mkdir /app/storage/chat_uploads` y su comentario del `Dockerfile`.
- [ ] Borrar `scripts/migrar_documentos_chat_a_anexos.py` y su test: ya cumplió.

Frontend:
- [ ] Red: test de `TenderAssistantDrawer` que no llama a `listTenderDocuments` y muestra
  un aviso con enlace al panel de anexos.
- [ ] Green: borrar `useTenderDocuments`, `DocumentAttachmentManager` y el tipo
  `TenderChatDocument`. En el drawer, dejar solo el aviso que lleva al panel.

Documentación:
- [ ] ADR `0006-asistente-solo-lee-anexos.md`: D1 y D2.
- [ ] Nota en `docs/plans/233-disparar-ia-con-anexos.md` junto a D5-6 que apunte al ADR.

### Fase 4: PR 3, borrar las tablas (despliegue posterior al PR 2)

- [ ] Migración de Alembic que borra `tender_milestone_document` y luego
  `tender_chat_documents`. Quitar `TenderChatDocumentModel`,
  `TenderMilestoneDocumentModel`, `IMilestoneDocumentRepository` y su implementación.
- [ ] `python -m scripts.migraciones` devuelve una sola cabeza.

---

## 4. Plan de verificación

```bash
# Backend (monorepo/backend, con .venv activo)
pytest
python -m scripts.migraciones

# Frontend (monorepo/frontend)
pnpm run test
pnpm run test:e2e
```

En producción, después de cada fase:

- Fase 0: el log de arranque dice `Anexos en Cloudflare R2`.
- Fase 1: `POST /tenders/{id}/assistant/documents` responde 405.
- Fase 2: el reporte del script tiene `errores = 0`. En una licitación con documentos
  migrados, el panel muestra el anexo y el asistente lo cita al responder.
- Fase 3: una pregunta al asistente sobre una licitación con anexos responde sin errores
  en los logs, y el servicio no tiene volúmenes montados.
- Fase 4: `alembic upgrade head` corre en el `preDeployCommand` sin errores.

Las pruebas del script y de la migración de la fase 4 corren contra la base local de
Supabase, nunca en `dev test`. Ninguna fase se mergea a `main` entre las 06:00 y las
12:00 UTC.
