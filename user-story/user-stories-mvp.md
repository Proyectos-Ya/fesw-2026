# Historias de Usuario — MVP ProyectosYA (3 Semanas)

> **Roles identificados:** Representante de empresa (usuario principal), Sistema (motor de matching + LLM)
> **Capacidad estimada MVP:** ~40 story points en 3 semanas (1 desarrollador full-stack)
> **Total story points:** 39 SP

---

## Resumen del Sprint

| HU     | Título                                                      | SP  | Semana |
| ------ | ----------------------------------------------------------- | --- | ------ |
| HU-002 | Completar perfil de empresa                                 | 5   | 1      |
| HU-003 | Visualizar licitaciones recomendadas                        | 5   | 2      |
| HU-004 | Buscar y filtrar licitaciones                               | 5   | 2      |
| HU-005 | Ver detalle de una licitación y análisis de compatibilidad  | 8   | 2      |
| HU-010 | Editar perfil de empresa                                    | 2   | 3      |
| HU-012 | Recibir notificación de nuevas licitaciones relevantes      | 3   | 3      |
| HU-020 | Responder preguntas generadas por IA para mejorar el perfil | 5   | 3      |

---


# HU-002: Completar perfil de empresa

## Story Points

**5 SP** (hasta 3 días)

## Descripción

Yo, como representante de empresa recién registrado, quiero completar el perfil de mi empresa indicando su rubro, experiencia y capacidades, para que el motor de matching pueda identificar licitaciones que se ajusten a lo que realmente podemos ejecutar.

## Conversación

El perfil de empresa es el núcleo del motor de matching semántico. Sin esta información el sistema no puede calcular embeddings ni hacer recomendaciones. Planeta Libre trabaja en construcción, mantenimiento e instalaciones técnicas. El perfil debe capturar tanto texto libre (descripción) como datos estructurados (rubros, regiones, tamaño) para maximizar la calidad del matching. Este es el paso más crítico del MVP.

## Criterios de Aceptación

- Dado un representante recién registrado redirigido al flujo de perfil, cuando el sistema carga la vista, entonces muestra una página "Configura tu perfil" dividida en 3 secciones con un indicador de progreso (Paso 1/3, Paso 2/3, Paso 3/3) en la parte superior.
- Dado un representante en el Paso 1 "Información General", cuando observa el formulario, entonces el sistema muestra los campos: descripción de la empresa (textarea, máx. 500 caracteres con contador), años de experiencia (input numérico, mín. 0), cantidad de empleados (select con rangos: 1–5, 6–20, 21–50, 51–200, 201+) y regiones donde opera (checkboxes múltiples con las 16 regiones de Chile).
- Dado un representante en el Paso 2 "Rubros y Capacidades", cuando observa el formulario, entonces el sistema muestra un selector de rubros con búsqueda autocomplete (basado en la clasificación de Mercado Público) que permite seleccionar múltiples rubros, y una sección de "palabras clave de experiencia" (input tipo tag/chip donde se agregan competencias separadas por Enter).
- Dado un representante en el Paso 3 "Documentación", cuando observa el formulario, entonces el sistema muestra checkboxes para certificaciones disponibles (Inicio de actividades SII, Carpeta tributaria al día, Registro de Proveedores ChileCompra, Certificados ISO, Habilidad en ChileCompra) y un campo opcional para URL del sitio web de la empresa.
- Dado un representante completando cualquier paso del perfil, cuando hace clic en "Siguiente" sin haber completado los campos obligatorios del paso actual, entonces el sistema muestra mensajes de validación inline y no avanza al siguiente paso.
- Dado un representante en el Paso 3 con todos los campos obligatorios completados, cuando hace clic en "Guardar perfil", entonces el sistema persiste el perfil, muestra un toast de éxito "¡Perfil guardado! Generando tus primeras recomendaciones…" y redirige al dashboard de licitaciones recomendadas (HU-003) tras un máximo de 5 segundos.
- Dado un representante que cierra la ventana durante el flujo de perfil sin completarlo, cuando vuelve a iniciar sesión, entonces el sistema lo redirige automáticamente al último paso incompleto del perfil en lugar del dashboard principal.

---

# HU-003: Visualizar licitaciones recomendadas

## Story Points

**5 SP** (hasta 3 días)

## Descripción

Yo, como representante de empresa con perfil completo, quiero ver en mi dashboard una lista de licitaciones recomendadas ordenadas por compatibilidad con mi empresa, para identificar de un vistazo las mejores oportunidades sin tener que buscar manualmente en Mercado Público.

## Conversación

Esta es la propuesta de valor central del MVP: reemplazar las 3 HH/día de búsqueda manual de Planeta Libre por una lista priorizada. El score de compatibilidad (%) debe ser el elemento visual más prominente. Las licitaciones deben mostrar suficiente información para decidir si vale la pena hacer clic, sin tener que entrar al detalle.

## Criterios de Aceptación

- Dado un representante de empresa autenticado con perfil completo, cuando accede a la página principal ("/"), entonces el sistema muestra el dashboard con el título "Licitaciones para ti" y una lista de tarjetas de licitaciones recomendadas ordenadas de mayor a menor score de compatibilidad.
- Dado un representante en el dashboard, cuando observa cada tarjeta de licitación, entonces el sistema muestra: nombre de la licitación (texto truncado a 2 líneas), organismo comprador, región, fecha de cierre (con etiqueta de urgencia si cierra en menos de 3 días), monto estimado del contrato y un indicador circular de compatibilidad con porcentaje en colores (verde ≥70%, amarillo 40–69%, rojo <40%).
- Dado un representante en el dashboard con recomendaciones cargadas, cuando el sistema termina de cargar la lista, entonces muestra un resumen en el header con el texto "X licitaciones encontradas para tu perfil" donde X es el total de resultados.
- Dado un representante en el dashboard, cuando el sistema está calculando las recomendaciones por primera vez (estado de carga inicial), entonces muestra un skeleton loader en lugar de las tarjetas con el mensaje "Analizando tu perfil y buscando oportunidades…".
- Dado un representante en el dashboard cuyo perfil fue creado recientemente y el sistema aún no tiene recomendaciones procesadas, cuando carga el dashboard, entonces muestra un estado vacío con una ilustración de reloj y el mensaje "Tus primeras recomendaciones estarán listas en unos minutos. Te avisaremos por correo." junto al botón "Buscar manualmente" que redirige a la vista de búsqueda (HU-004).
- Dado un representante en el dashboard con licitaciones cargadas, cuando hace scroll hasta el final de la lista, entonces el sistema carga automáticamente las siguientes 10 licitaciones (infinite scroll) sin redirigir a otra página.

---

# HU-004: Buscar y filtrar licitaciones

## Story Points

**5 SP** (hasta 3 días)

## Descripción

Yo, como representante de empresa, quiero buscar licitaciones mediante palabras clave y aplicar filtros por región, rubro y fecha de cierre, para encontrar oportunidades específicas más allá de las recomendaciones automáticas.

## Conversación

El motor de matching cubre el 80% de los casos, pero el representante debe poder buscar proactivamente. La búsqueda semántica es diferenciadora frente a Mercado Público (que solo busca por texto exacto). Los filtros son secundarios pero esenciales para acotar resultados en volúmenes altos.

## Criterios de Aceptación

- Dado un representante de empresa autenticado en cualquier vista del sistema, cuando hace clic en el ícono de búsqueda (lupa) en la barra de navegación superior, entonces el sistema navega a la vista de búsqueda mostrando un campo de búsqueda prominente con el placeholder "Describe qué tipo de licitación estás buscando…" y un panel de filtros lateral (desktop) o colapsable (mobile).
- Dado un representante en la vista de búsqueda, cuando ingresa texto en el campo de búsqueda y presiona Enter o hace clic en el botón "Buscar", entonces el sistema realiza una búsqueda semántica y muestra los resultados en el mismo formato de tarjeta que el dashboard (HU-003) ordenados por relevancia semántica.
- Dado un representante en la vista de búsqueda con resultados cargados, cuando aplica el filtro "Región" seleccionando una o más regiones del selector múltiple (dropdown con checkboxes), entonces el sistema actualiza la lista de resultados mostrando solo las licitaciones que coinciden con la selección.
- Dado un representante en la vista de búsqueda, cuando aplica el filtro "Fecha de cierre" seleccionando un rango desde un date-range picker (opciones rápidas: Próximos 3 días, Esta semana, Este mes, Personalizado), entonces el sistema filtra y actualiza los resultados mostrando solo licitaciones cuya fecha de cierre cae dentro del rango seleccionado.
- Dado un representante en la vista de búsqueda, cuando aplica el filtro "Rubro" seleccionando categorías del selector múltiple basado en la clasificación ChileCompra, entonces el sistema combina el filtro con los ya activos y actualiza los resultados.
- Dado un representante en la vista de búsqueda con filtros activos, cuando hace clic en el botón "Limpiar filtros", entonces el sistema remueve todos los filtros aplicados y actualiza la lista de resultados mostrando la búsqueda sin restricciones de filtro.
- Dado un representante que realiza una búsqueda que no retorna resultados, cuando el sistema termina de procesar la solicitud, entonces muestra un estado vacío con el mensaje "No encontramos licitaciones que coincidan con tu búsqueda. Intenta con otros términos o amplía los filtros." y sugiere 3 búsquedas alternativas relacionadas.

---

# HU-005: Ver detalle de una licitación

## Story Points

**3 SP** (hasta 1 día)

## Descripción

Yo, como representante de empresa, quiero ver la información completa de una licitación en una página de detalle, para evaluar si cumplimos los requisitos antes de invertir tiempo en la postulación.

## Conversación

El detalle es el primer filtro real antes de comprometerse a postular. El representante necesita ver todo lo relevante sin salir de la plataforma: bases, requisitos, montos, plazos. Se extrae la información clave de los documentos de Mercado Público mediante NLP. No debe ser una redirección al portal de ChileCompra; eso genera fricción y derrota el propósito.

## Criterios de Aceptación

- Dado un representante en el dashboard (HU-003) o en los resultados de búsqueda (HU-004), cuando hace clic sobre la tarjeta de una licitación, entonces el sistema navega a la página de detalle de esa licitación con la URL `/licitaciones/{codigo}` (ej. `/licitaciones/1234-56-LP26`).
- Dado un representante en la página de detalle de una licitación, cuando el sistema termina de cargar, entonces muestra las siguientes secciones: (1) Header con nombre, código, organismo comprador, región y badge de compatibilidad; (2) Información clave en cards: monto estimado, fecha publicación, fecha cierre, tipo de licitación; (3) Resumen ejecutivo generado por IA (máx. 3 párrafos con los puntos más relevantes del documento); (4) Requisitos extraídos en formato de lista; (5) Documentos adjuntos originales con botón de descarga.
- Dado un representante en la página de detalle, cuando hace clic en el botón "Ver en Mercado Público" ubicado en el header, entonces el sistema abre el enlace oficial de la licitación en una nueva pestaña del navegador.
- Dado un representante en la página de detalle, cuando el sistema está cargando el resumen IA o los requisitos extraídos, entonces muestra un skeleton loader en esas secciones específicas sin bloquear la visualización del resto del contenido.
- Dado un representante en la página de detalle y la licitación ya cerró su fecha de postulación, cuando el sistema renderiza la página, entonces muestra un banner de advertencia en la parte superior indicando "Esta licitación cerró el [fecha]. Ya no es posible postular." y oculta el botón "Postular".


# HU-010: Editar perfil de empresa

## Story Points

**2 SP** (hasta 4 horas)

## Descripción

Yo, como representante de empresa, quiero poder editar la información de mi perfil de empresa después del registro inicial, para mantener mis datos actualizados y mejorar la precisión del matching.

## Conversación

Los rubros y capacidades de una empresa pueden evolucionar. Si el perfil queda desactualizado, la calidad del matching cae. La edición debe ser accesible sin fricciones desde el panel de configuración. Al guardar cambios, el sistema debe recalcular el matching para reflejar el perfil actualizado.

## Criterios de Aceptación

- Dado un representante de empresa autenticado en cualquier vista del sistema, cuando hace clic en su avatar o nombre en la barra de navegación superior, entonces el sistema despliega un menú con la opción "Mi perfil de empresa".
- Dado un representante que selecciona "Mi perfil de empresa", cuando el sistema carga la vista, entonces muestra la información actual del perfil en modo lectura con un botón "Editar perfil" en el header.
- Dado un representante en la vista de perfil en modo lectura, cuando hace clic en "Editar perfil", entonces el sistema transiciona los campos a modo edición (inputs, selects y textareas editables) mostrando los valores actuales pre-cargados y los botones "Guardar cambios" y "Cancelar" en el header.
- Dado un representante en modo edición del perfil, cuando modifica campos y hace clic en "Guardar cambios", entonces el sistema persiste los nuevos valores, retorna al modo lectura, muestra un toast "Perfil actualizado. Recalculando tus recomendaciones…" y encola el recálculo del matching en segundo plano.
- Dado un representante en modo edición con cambios no guardados, cuando hace clic en "Cancelar", entonces el sistema muestra un modal de confirmación "¿Descartar cambios? Los cambios no guardados se perderán." con los botones "Descartar" y "Seguir editando", sin aplicar ningún cambio si el usuario confirma el descarte.

---

# HU-012: Recibir notificación de nuevas licitaciones relevantes

## Story Points

**3 SP** (hasta 2 días)

## Descripción

Yo, como representante de empresa, quiero recibir notificaciones cuando el sistema detecte nuevas licitaciones con alta compatibilidad para mi empresa, para no tener que entrar a la plataforma todos los días a revisar el dashboard.

## Conversación

El valor de ProyectosYA no es solo la búsqueda activa, sino la detección pasiva: que el sistema trabaje mientras el representante hace otras cosas. Sin notificaciones, el producto requiere que el usuario recuerde visitarlo, lo que reduce el engagement y la retención.

## Criterios de Aceptación

- Dado un representante con perfil de empresa completo, cuando el proceso de ingesta nocturna encuentra una nueva licitación con score de compatibilidad mayor al 80%, entonces el sistema envía un correo electrónico al usuario alertando de la oportunidad.
- Dado un correo de notificación de nueva licitación, cuando el representante lo recibe, entonces el correo incluye el título, monto estimado, organismo comprador y un enlace directo a la página de detalle en la plataforma.
- Dado un representante en la configuración de su cuenta, cuando activa o desactiva la opción "Recibir alertas de licitaciones altamente compatibles", entonces el sistema actualiza su preferencia y comienza o detiene el envío de correos.

---

# HU-020: Responder preguntas generadas por IA para mejorar el perfil

## Story Points

**5 SP** (hasta 3 días)

## Descripción

Yo, como representante de empresa, quiero poder responder a preguntas específicas generadas por la IA sobre mis capacidades, experiencia e historial, para que el sistema pueda refinar mi perfil y mejorar significativamente la precisión de las licitaciones recomendadas.

## Conversación

El perfil estático inicial del MVP puede no ser suficiente para el motor de matching semántico. A medida que el sistema "conoce" a la empresa, el LLM puede identificar vacíos de información que le impiden calcular un score de compatibilidad alto en ciertas licitaciones. Al hacer preguntas interactivas, el perfil se vuelve dinámico y la asertividad del matching mejora con el uso de la plataforma.

## Criterios de Aceptación

- Dado un representante en su dashboard de licitaciones, cuando el motor de matching identifica ambigüedad en el perfil frente a oportunidades relevantes, entonces el sistema muestra una tarjeta destacada tipo widget con la pregunta generada por la IA (ej: "¿Realizan trabajos de obra gruesa en regiones extremas?").
- Dado un representante viendo la pregunta de IA, cuando responde ingresando un texto en el campo provisto y hace clic en "Enviar respuesta", entonces el sistema actualiza el contexto semántico de su perfil y recalcula las licitaciones recomendadas de fondo.
- Dado un representante viendo la pregunta de IA, cuando hace clic en "Omitir por ahora", entonces la tarjeta se descarta y el sistema muestra la siguiente pregunta en cola (si la hay) o esconde el widget.
- Dado el sistema de matching procesando un perfil, cuando determina que necesita más información, entonces encola un máximo de 3 preguntas en el dashboard del usuario para no saturarlo, priorizando aquellas que desbloquean licitaciones de mayor monto o relevancia.

# 🚀 De MVPrototype → MVProduct: Historias de Usuario Pendientes

> Estas historias no forman parte del MVP inicial de 3 semanas. Son los requisitos mínimos para que el producto sea **production-ready**: escalable, seguro, autosuficiente y apto para clientes de pago. No incluyen criterios de aceptación — están listas para priorizarse y refinarse en el siguiente ciclo de planificación.

## Resumen

| HU     | Título                                                      | Área                   |
| ------ | ----------------------------------------------------------- | ---------------------- |
| HU-011 | Onboarding de bienvenida                                    | Experiencia de usuario |
| HU-013 | Recibir alerta de cierre próximo de licitación seguida      | Notificaciones         |
| HU-014 | Agregar notas a una postulación                             | Postulaciones          |
| HU-015 | Archivar postulación                                        | Postulaciones          |
| HU-016 | Invitar miembros del equipo a la empresa                    | Multi-usuario          |
| HU-017 | Gestionar roles del equipo                                  | Multi-usuario          |
| HU-018 | Exportar pipeline de postulaciones                          | Reportes               |
| HU-019 | Ver métricas de rendimiento de postulaciones                | Reportes               |
| HU-020 | Responder preguntas generadas por IA para mejorar el perfil | Perfil de empresa      |

---

## Experiencia de Usuario

---

# HU-011: Onboarding de bienvenida

## Descripción

Yo, como representante de empresa que acaba de completar su perfil, quiero recibir una guía interactiva paso a paso que me explique las funciones principales de la plataforma, para entender rápidamente cómo sacarle el máximo provecho sin necesidad de leer documentación.

## Conversación

En el MVP el early adopter (Planeta Libre) recibe onboarding manual del equipo de ProyectosYA. En producción, cada nuevo cliente llega sin acompañamiento humano. Un onboarding guiado (tooltips o un tour tipo product walkthrough) reduce dramáticamente el time-to-value y la tasa de abandono en los primeros 7 días. Debe ser omitible para usuarios que ya conocen el producto.

---

## Notificaciones

---


# HU-013: Recibir alerta de cierre próximo de licitación seguida

## Descripción

Yo, como representante de empresa con postulaciones activas, quiero recibir una alerta cuando una licitación que estoy siguiendo o postulando esté a menos de 48 horas de cerrar, para no perder el plazo de presentación por descuido.

## Conversación

El 50% de rechazos de Planeta Libre viene de errores administrativos, y perder el plazo de cierre es el error más costoso. Este es un mecanismo de seguridad crítico para el cliente: actúa como un recordatorio de deadline concreto vinculado a una acción que el usuario ya tomó (guardar como favorita o iniciar postulación). La alerta debe enviarse por correo y mostrarse también como notificación in-app.

---

## Postulaciones

---

# HU-014: Agregar notas a una postulación

## Descripción

Yo, como representante de empresa, quiero poder escribir notas libres dentro del seguimiento de una postulación, para registrar decisiones, contactos con el organismo comprador, y detalles del proceso que no caben en el checklist estándar.

## Conversación

El checklist de 5 pasos es un esqueleto útil pero insuficiente para la gestión real. Planeta Libre necesita registrar cosas como "llamamos al organismo el lunes, dijeron que las bases cambian el miércoles" o "la oferta económica queda en $4.200.000". Sin un campo de notas, el representante vuelve a usar WhatsApp o correo para este registro, fragmentando el contexto. Las notas deben tener timestamp automático y ordenarse cronológicamente.

---

# HU-015: Archivar postulación

## Descripción

Yo, como representante de empresa, quiero archivar una postulación que decidí no continuar o que ya fue resuelta, para mantener mi pipeline limpio sin eliminar el historial del proceso.

## Conversación

Con el tiempo el pipeline acumula postulaciones abandonadas, perdidas o adjudicadas que ensucian la vista principal. Eliminar definitivamente es destructivo para el historial; archivar es la solución intermedia correcta. En producción, el representante necesita poder revisar postulaciones pasadas para aprender de patrones (qué organismos contratan con ellos, qué tipos de licitaciones ganan).

---

## Multi-usuario

---

# HU-016: Invitar miembros del equipo a la empresa

## Descripción

Yo, como representante administrador de una empresa, quiero invitar a otros miembros de mi equipo mediante su correo electrónico para que accedan a la plataforma bajo la misma cuenta empresarial, para que podamos colaborar en la gestión de licitaciones y postulaciones sin compartir credenciales.

## Conversación

En el MVPrototype se asume que solo hay un usuario por empresa. En la realidad, Planeta Libre tiene un equipo donde distintas personas se encargan de buscar licitaciones, preparar documentación y gestionar el envío. Compartir credenciales es un problema de seguridad y de trazabilidad. El modelo multi-usuario es un prerequisito para un trabajo colaborativo eficiente.

---

# HU-017: Gestionar roles del equipo

## Descripción

Yo, como representante administrador de una empresa, quiero asignar y modificar los roles de los miembros de mi equipo (Administrador, Editor, Visualizador), para controlar quién puede ver, editar o postular a licitaciones dentro de la cuenta empresarial.

## Conversación

Sin roles, cualquier miembro invitado puede realizar cualquier acción, incluyendo acciones destructivas (archivar postulaciones, cambiar el perfil de empresa, afectar el matching). En clientes con equipos de más de 2 personas, la ausencia de roles genera errores no intencionados, por lo que es una característica clave para la colaboración en equipo.

---

## Reportes

---

# HU-018: Exportar pipeline de postulaciones

## Descripción

Yo, como representante de empresa, quiero exportar mi lista de postulaciones activas e históricas a un archivo Excel o PDF, para compartirla con mi equipo, presentarla en reuniones de gestión, o archivarla en mis registros internos.

## Conversación

Las PYMEs chilenas llevan gestión en Excel por cultura organizacional. Aunque ProyectosYA reemplaza ese Excel interno, el representante necesita poder sacar la información para compartirla con socios, directivos o auditores que no tienen acceso a la plataforma. Un export simple (nombre, organismo, monto, estado, fecha cierre) es suficiente para el primer ciclo.

---

# HU-019: Ver métricas de rendimiento de postulaciones

## Descripción

Yo, como representante de empresa, quiero ver un dashboard con métricas de mis postulaciones (tasa de adjudicación, valor total postulado, tiempo promedio de postulación, organismos más frecuentes), para entender qué tan efectiva es mi estrategia de licitaciones y tomar decisiones basadas en datos.

## Conversación

Sin métricas el representante no puede demostrar el ROI de usar ProyectosYA frente a la búsqueda manual. "En 3 meses postulaste a 18 licitaciones, ganaste 3, por un valor total de $42M". Para ProyectosYA esto también es datos propios del motor de recomendación (qué score de matching correlaciona con adjudicación real).

---


