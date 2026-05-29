# Historias de Usuario — MVP (PMV) ProyectosYA

Este documento contiene las historias de usuario planificadas para el **Prototipo Mínimo Viable (PMV)** de ProyectosYA, según la última planificación detallada en el documento de diseño `E2_ProyectosYa_VF.pdf`.

El alcance del PMV se concentra en el núcleo de procesamiento inteligente, matching semántico y retroalimentación interactiva del perfil de la empresa, sumando un total de **19 Story Points (SP)**.

---

## Resumen del PMV

| ID | Categoría | Historia de Usuario | Story Points (SP) |
| --- | --- | --- | --- |
| **HdU 01** | Importante | Completar perfil de empresa | 3 SP |
| **HdU 02** | Importante | Mejorar el perfil proactivamente | 5 SP |
| **HdU 03** | Importante | Visualizar licitaciones recomendadas | 5 SP *(de 8 SP totales)* |
| **HdU 05** | Importante | Análisis de compatibilidad IA | 5 SP |
| **HdU 10** | Deseable | Consulta de datos objetivos (Detalle de licitación) | 1 SP |

---

# Detalle de Historias de Usuario (PMV)

### HdU 01 - Completar perfil de empresa
- **Categoría**: Importante
- **Puntos**: 3 SP
- **Descripción**: Como representante de empresa recién registrada, necesito completar el perfil de mi empresa indicando su rubro, experiencia y capacidades, para que el motor de matching pueda identificar licitaciones que se ajusten a lo que realmente podemos ejecutar.
- **Criterios de Aceptación**:
  - **Dado** un representante autenticado en el sistema, **cuando** ingresa a la vista de configuración del perfil, **entonces** el sistema muestra un formulario con los campos: descripción de la empresa, años de experiencia, cantidad de empleados, regiones donde opera, selector de rubros y palabras clave de experiencia y el botón “Guardar perfil”.
  - **Dado** un representante con todos los campos obligatorios completados, **cuando** hace clic en “Guardar perfil”, **entonces** el sistema persiste el perfil, muestra una notificación de éxito y redirige al dashboard de licitaciones recomendadas.
  - **Dado** un representante en la vista del formulario para completar perfil, **cuando** el representante envía uno o más datos incorrectos, **entonces** el sistema muestra un mensaje de error en los campos de texto llenados de forma incorrecta.
  - **Dado** un representante en la vista del formulario para completar perfil, **cuando** el representante envía los datos del formulario y el sistema demora 5 minutos en responder, **entonces** el sistema muestra un mensaje de error timeout.

---

### HdU 02 - Mejorar el perfil proactivamente
- **Categoría**: Importante
- **Puntos**: 5 SP
- **Descripción**: Como representante de empresa necesito complementar progresivamente la información de mi empresa, para que las oportunidades de negocio recomendadas por el sistema sean cada vez más acertadas para mi empresa.
- **Criterios de Aceptación**:
  - **Dado** un representante autenticado en el sistema, **cuando** entra a la vista del dashboard, **entonces** el sistema muestra una tarjeta por cada pregunta generada por la IA, para mejorar el perfil. Además dentro de la tarjeta muestra el botón “Enviar” y “Omitir”.
  - **Dado** un representante autenticado en el sistema, **cuando** hace clic en el botón “Enviar” del formulario de una pregunta, **entonces** el sistema actualiza el perfil y las licitaciones recomendadas.
  - **Dado** un representante autenticado en el sistema, **cuando** hace clic en el botón “Omitir” del formulario de una pregunta, **entonces** el sistema descarta la pregunta y muestra la siguiente pregunta en cola (si la hay) o esconde la tarjeta.

---

### HdU 03 - Visualizar licitaciones recomendadas
- **Categoría**: Importante
- **Puntos**: 8 SP *(5 SP asignados para el PMV)*
- **Descripción**: Como representante de empresa con perfil completo, necesito ver una lista de licitaciones recomendadas ordenadas por compatibilidad con mi empresa, para identificar de un vistazo las mejores oportunidades sin tener que buscar manualmente en Mercado Público.
- **Criterios de Aceptación**:
  - **Dado** un representante autenticado en el sistema, **cuando** accede a la página principal, **entonces** el sistema muestra el dashboard con una lista de licitaciones ordenadas por compatibilidad.
  - **Dado** un representante autenticado en el sistema, **cuando** accede al dashboard, **entonces** el sistema muestra para cada licitación el título, organismo comprador, región, fecha de cierre, monto estimado del contrato y porcentaje de compatibilidad en colores (verde ≥70%, amarillo 40–69%, rojo <40%).
  - **Dado** un representante autenticado en el sistema, **cuando** ingresa al dashboard, **entonces** el sistema muestra un filtro por región, provincia y/o comuna.
  - **Dado** un representante autenticado en el sistema, **cuando** llena algún filtro de ubicación, **entonces** el sistema se actualiza y muestra sólo las licitaciones cuya ubicación cumpla con el filtro.
  - **Dado** un representante autenticado en el sistema, **cuando** ingresa al dashboard, **entonces** el sistema muestra un filtro por rango de presupuesto.
  - **Dado** un representante autenticado en el sistema, **cuando** llena el filtro de presupuesto, **entonces** el sistema se actualiza y muestra sólo las licitaciones cuyo presupuesto cumpla con el filtro.

---

### HdU 05 - Análisis de compatibilidad IA
- **Categoría**: Importante
- **Puntos**: 5 SP
- **Descripción**: Como representante de empresa, necesito recibir una medición de compatibilidad de una licitación para tomar la decisión de postular sin necesidad de gastar mucho tiempo.
- **Criterios de Aceptación**:
  - **Dado** un representante autenticado en el sistema, **cuando** ingresa al detalle de una licitación, **entonces** el sistema muestra un botón “Generar análisis de compatibilidad IA”.
  - **Dado** un representante autenticado en el sistema, **cuando** hace clic en el botón “Generar análisis de compatibilidad IA”, **entonces** el sistema redirige a la vista de análisis de compatibilidad.
  - **Dado** un representante autenticado en el sistema, **cuando** el representante accede a la vista de análisis de compatibilidad IA, **entonces** el sistema muestra el porcentaje global de compatibilidad, la fecha en que el análisis fue generado y una recomendación final con uno de estos tres valores: *Postular*, *Evaluar con cautela* o *No recomendado*, y una justificación.
  - **Dado** un representante autenticado en el sistema, **cuando** actualiza su perfil y abre la ficha de una licitación que ya tenía un análisis generado, **entonces** el sistema genera automáticamente el análisis incorporando los nuevos datos del perfil, y muestra la fecha y hora de la última actualización del análisis.
  - **Dado** un representante autenticado en el sistema, **cuando** vuelve a abrir la ficha de una licitación que ya tenía un análisis generado, **entonces** el sistema muestra el análisis previamente generado y un formulario para regenerar el análisis ingresando opcionalmente un prompt con instrucciones para mejorar el análisis y un botón “Regenerar análisis”.
  - **Dado** un representante autenticado en el sistema, **cuando** hace clic en el botón “Regenerar análisis”, **entonces** el sistema muestra el nuevo análisis siguiendo las directivas del prompt de ser indicadas, además de mostrar la fecha en la que se actualizó.

---

### HdU 10 - Consulta de datos objetivos (Ver detalle de licitación)
- **Categoría**: Deseable
- **Puntos**: 1 SP
- **Descripción**: Como representante de empresa, necesito visualizar el detalle completo y análisis de una licitación para poder evaluar si mi empresa cumple los requisitos antes de postular.
- **Criterios de Aceptación**:
  - **Dado** un representante en el dashboard o resultados de búsqueda, **cuando** hace clic en una licitación, **entonces** el sistema navega a la vista con el detalle completo de la licitación.
  - **Dado** un representante autenticado en el sistema, **cuando** accede al detalle de una licitación, **entonces** muestra el nombre de la licitación, organismo comprador, fechas importantes, monto estimado, requisitos, documentos asociados y enlaces relacionados con la licitación.
  - **Dado** un representante en la vista de detalle, **cuando** acceda al detalle de una licitación y se haya generado el análisis de compatibilidad, **entonces** agrega el análisis generado por IA a la información de la licitación.
