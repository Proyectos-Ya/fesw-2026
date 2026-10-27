# Documentación de Chiripa

Este directorio centraliza la documentación técnica, decisiones arquitectónicas, planes de trabajo y guías operativas del proyecto **Chiripa**.

---

## Estructura de la Documentación

```text
docs/
├── plans/          # Planes técnicos de Historias de Usuario (<issue>-<slug>.md)
├── decisions/      # Architecture Decision Records (<NNNN>-<slug>.md)
├── guides/         # Guías operativas y de mantenimiento
├── changelogs/     # Notas de versión y resúmenes por sprint (sprint-<N>.md)
└── README.md       # Este índice
```

---

## 1. Planes Técnicos (`docs/plans/`)
Antes de implementar cualquier historia de usuario o cambio arquitectónico no trivial, se redacta un plan técnico en esta carpeta.
* **Convención de nombre**: `<número-issue>-<slug-descriptivo>.md` si es un único archivo, o una carpeta `<número-issue>-<slug>/` con `plan.md` y `task.md` cuando incluye desglose de tareas (ejemplo: `312-hu-30/`).
* **Regla**: El plan debe ser revisado por un humano antes de comenzar a escribir código de producción. Las issues de GitHub definen el **QUÉ** y los planes el **CÓMO** (siempre enlazar con `Refs #NNN`).
* **Planes activos / registrados**:
  * [227-mejoras-cotizaciones.md](./plans/227-mejoras-cotizaciones.md): Cantidades automáticas, enteros y PDF.
  * [255-revocacion-acceso-equipo.md](./plans/255-revocacion-acceso-equipo.md): Gestión y revocación de acceso de miembros del equipo (HU-13).
  * [256-matching-qdrant-onboarding-telemetria.md](./plans/256-matching-qdrant-onboarding-telemetria.md): Matching: canal léxico (sparse BM25) sumado a los canales densos, caso sin historial y lectura de la telemetría del ranking.
  * [233-anexos-extension-navegador.md](./plans/233-anexos-extension-navegador.md): Anexos de Mercado Público (subida, extracción con Gemini y extensión de navegador), segundo llamado, NDCG en producción y matching en sombra (Spike 2).
  * [233-disparar-ia-con-anexos.md](./plans/233-disparar-ia-con-anexos.md): Los hitos y el análisis + cotización se disparan al subir un anexo y leen los anexos, en vez de los documentos del chat.
  * [instrucciones-decision-7.md](./plans/instrucciones-decision-7.md): Instrucciones técnicas de implementación para la Extensión de Navegador (Fase 3, Decisión 7).
  * [292-postulacion-preguntas-y-feedback.md](./plans/292-postulacion-preguntas-y-feedback.md): Preguntas basadas en las bases y feedback de carga en la postulación (mejoras a HU-20).
  * [305-ingesta-y-sync-estados.md](./plans/305-ingesta-y-sync-estados.md): Ingesta cada 2 h y sync-estados que etiqueta pendientes, aplica por página y no pierde lo listado.
  * [311-facilitar-creacion-empresa/plan.md](./plans/311-facilitar-creacion-empresa/plan.md): Rubros de Mercado Público, sugerencias de palabras clave y certificaciones con vencimiento (HU-29). Tareas en [311-facilitar-creacion-empresa/tasks.md](./plans/311-facilitar-creacion-empresa/tasks.md).
  * [312-hu-30/plan.md](./plans/312-hu-30/plan.md): Cotizaciones recibidas, llamado y ficha ordenada por secciones (HU-30). Tareas en [312-hu-30/task.md](./plans/312-hu-30/task.md).
  * [294-entrega-y-documentos-detalle/plan.md](./plans/294-entrega-y-documentos-detalle/plan.md): Dirección y plazo de entrega y flags del detalle de Compra Ágil, y recomendación de bases que nombra los documentos (#294). Tareas en [294-entrega-y-documentos-detalle/task.md](./plans/294-entrega-y-documentos-detalle/task.md).

## 2. Decisiones de Arquitectura (`docs/decisions/`)
Registros de decisiones técnicas significativas o difíciles de revertir (ADR - Architecture Decision Record).
* **Convención de nombre**: `<NNNN>-<slug>.md` con cuatro dígitos correlativos (ejemplo: `0001-seleccion-motor-vectorial.md`).
* **Estructura**: Contexto, Decisión tomada, Alternativas descartadas y Consecuencias.
* **Decisiones registradas**:
  * [0001-truncar-textos-del-reranker.md](./decisions/0001-truncar-textos-del-reranker.md): Pinecone recorta los pares que pasan los 1024 tokens en vez de rechazar el rerank. Solución provisoria con investigación pendiente.
  * [0002-confianza-de-anexos-compartidos.md](./decisions/0002-confianza-de-anexos-compartidos.md): Modelo de confianza, privacidad y ciclo de vida de anexos oficiales compartidos entre empresas (Plan 233, Decisión 6).
  * [0003-arquitectura-extension-navegador.md](./decisions/0003-arquitectura-extension-navegador.md): Arquitectura de la extensión de navegador, compatibilidad multi-navegador con WXT, Bridge y adaptador de Mercado Público (Plan 233, Decisión 7).
  * [0005-matching-en-sombra-con-anexos.md](./decisions/0005-matching-en-sombra-con-anexos.md): Matching enriquecido en sombra con anexos oficiales, recorte de tokens a 512, variantes att-text-v1 y att-items-v1, y replay con NDCG (Plan 233, Decisión 9).

## 3. Guías Operativas (`docs/guides/`)
Manuales prácticos para el equipo de desarrollo:
* [alembic-migraciones.md](./guides/alembic-migraciones.md): Manual operativo de migraciones de base de datos con Alembic, buenas prácticas y troubleshooting completo.
* [scripts-utilitarios.md](./guides/scripts-utilitarios.md): Catálogo de scripts de mantenimiento, vaciado de licitaciones y reseteo de cuentas/empresas.
* [testing-hdu08.md](./guides/testing-hdu08.md): Guía paso a paso para el recorrido y prueba manual de la HdU 08 (alertas de licitaciones).
* [copia-produccion-matching.md](./guides/copia-produccion-matching.md): Cómo copiar el catálogo de licitaciones y los vectores de producción a un entorno local para probar el matching.

## 4. Registro de Cambios (`docs/changelogs/`)
Al cierre de cada sprint se consolida el trabajo realizado en un changelog:
* **Convención de nombre**: `sprint-<N>.md` (ejemplo: `sprint-1.md`).
* **Secciones**: *Para usuarios* (funcionalidades visibles) y *Técnico* (con enlaces a PRs y mejoras internas).

---

## Automatización y Agentes de IA

Si colaboras usando un asistente de IA (Claude, Gemini, etc.):
* Las directrices generales y restricciones están en [AGENTS.md](../AGENTS.md) y [SKILL.md](../SKILL.md).
* Los agentes disponen de la [skill `documentacion`](../.claude/skills/documentacion/SKILL.md) que contiene el paso a paso y las plantillas predefinidas para redactar planes, ADRs y changelogs.
