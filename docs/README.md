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
* **Convención de nombre**: `<número-issue>-<slug-descriptivo>.md` (ejemplo: `240-integracion-notificaciones.md`).
* **Regla**: El plan debe ser revisado por un humano antes de comenzar a escribir código de producción. Las issues de GitHub definen el **QUÉ** y los planes el **CÓMO** (siempre enlazar con `Refs #NNN`).
* **Planes activos / registrados**:
  * [255-revocacion-acceso-equipo.md](./plans/255-revocacion-acceso-equipo.md): Gestión y revocación de acceso de miembros del equipo (HU-13).

## 2. Decisiones de Arquitectura (`docs/decisions/`)
Registros de decisiones técnicas significativas o difíciles de revertir (ADR - Architecture Decision Record).
* **Convención de nombre**: `<NNNN>-<slug>.md` con cuatro dígitos correlativos (ejemplo: `0001-seleccion-motor-vectorial.md`).
* **Estructura**: Contexto, Decisión tomada, Alternativas descartadas y Consecuencias.

## 3. Guías Operativas (`docs/guides/`)
Manuales prácticos para el equipo de desarrollo:
* [alembic-migraciones.md](./guides/alembic-migraciones.md): Manual operativo de migraciones de base de datos con Alembic, buenas prácticas y troubleshooting completo.
* [scripts-utilitarios.md](./guides/scripts-utilitarios.md): Catálogo de scripts de mantenimiento, vaciado de licitaciones y reseteo de cuentas/empresas.
* [testing-hdu08.md](./guides/testing-hdu08.md): Guía paso a paso para el recorrido y prueba manual de la HdU 08 (alertas de licitaciones).

## 4. Registro de Cambios (`docs/changelogs/`)
Al cierre de cada sprint se consolida el trabajo realizado en un changelog:
* **Convención de nombre**: `sprint-<N>.md` (ejemplo: `sprint-1.md`).
* **Secciones**: *Para usuarios* (funcionalidades visibles) y *Técnico* (con enlaces a PRs y mejoras internas).

---

## Automatización y Agentes de IA

Si colaboras usando un asistente de IA (Claude, Gemini, etc.):
* Las directrices generales y restricciones están en [AGENTS.md](../AGENTS.md) y [SKILL.md](../SKILL.md).
* Los agentes disponen de la [skill `documentacion`](../.claude/skills/documentacion/SKILL.md) que contiene el paso a paso y las plantillas predefinidas para redactar planes, ADRs y changelogs.
