# ProyectosYa — Design System

> Branding y kit de interfaz para **ProyectosYa**, la startup chilena que ayuda a las MiPymes a ganar más licitaciones en ChileCompra / Compra Ágil.

ProyectosYa construye un **perfil inteligente** de cada empresa, hace **matching semántico** entre ese perfil y miles de licitaciones de Compra Ágil, y entrega un **análisis de compatibilidad con IA** que explica, en lenguaje simple, por qué una licitación calza (o no) con la empresa. El producto existe para quitarle el papeleo y la búsqueda manual a los dueños de pequeñas empresas, y mostrarles solo las oportunidades que valen la pena.

El sistema visual es **cálido, fresco y confiable** — lo opuesto al típico SaaS B2B frío y saturado. Fondo off-white, tinta negra cálida, primario **teal** (azul-verde) para confianza e inteligencia, y un acento **coral / naranja-rojo** para la energía y la acción ("Ya"). Claridad y facilidad de uso por sobre todo.

---

## Fuentes / materiales de origen

Este sistema se creó **desde cero a partir del brief de marca** (descripción de la empresa + dirección de color y tono). No se adjuntó código, Figma ni assets previos, por lo que:

- El **logo/wordmark** (`assets/logo-*.svg`) es una identidad nueva creada para este sistema (checkmark "Ya" + punto coral, wordmark con "Ya" en coral).
- Las **fuentes** se cargan vía **Google Fonts CDN** (ver Caveats). Si existen binarios de marca, reemplazarlos en `tokens/fonts.css`.
- Los **iconos** usan **Lucide** (ver sección Iconografía).
- Los datos de licitaciones en los UI kits son **ficticios pero realistas** (formato Compra Ágil chileno).

Si tienes un codebase, Figma o brand book reales, compártelos y ajusto el sistema para que sea fiel a ellos.

---

## Índice del proyecto

| Ruta | Qué es |
|---|---|
| `styles.css` | **Punto de entrada global.** Solo `@import`s. Los consumidores enlazan este archivo. |
| `tokens/` | Custom properties CSS: `colors.css`, `typography.css`, `spacing.css` (radii/sombras/motion), `fonts.css`, `base.css`. |
| `assets/` | Logos (wordmark, on-teal, mark). |
| `guidelines/` | Tarjetas de especímenes (color, tipografía, spacing, marca) que pueblan la pestaña Design System. |
| `components/` | Primitivas React reutilizables (ver abajo). |
| `ui_kits/app/` | Recreación interactiva de la **app ProyectosYa** (feed de matches, detalle con análisis IA, perfil). |
| `ui_kits/site/` | **Landing page** de marketing. |
| `SKILL.md` | Hace este sistema usable como Agent Skill. |

### Componentes
`core/`: **Icon** · `forms/`: **Button, IconButton, Input, Select, Checkbox, Switch** · `feedback/`: **Badge, Tag, MatchMeter** · `layout/`: **Card, Avatar** · `navigation/`: **Tabs**

`MatchMeter` es el componente **firma** de la marca: el medidor circular de compatibilidad (0–100) que aparece en toda la experiencia.

---

## CONTENT FUNDAMENTALS — cómo se escribe

**Idioma:** español de Chile. Cercano pero profesional; nunca acartonado ni "lenguaje de sistema".

- **Tuteo siempre.** Le hablamos al dueño de la MiPyme de "tú", no de "usted". *"Encontramos 8 licitaciones que calzan con tu perfil."*
- **Nosotros + tú.** La marca es un socio que trabaja para ti: *"Cruzamos miles de licitaciones y te mostramos solo las que valen la pena."* Evitamos la voz pasiva impersonal ("El sistema ha procesado…").
- **Claro sobre clever.** Frases cortas, verbos concretos (*calza, postula, gana, revisa, cubre tus brechas*). Cero jerga corporativa, cero "soluciones de valor agregado".
- **Vocabulario del dominio, bien usado:** *licitación, Compra Ágil, ChileCompra, organismo, rubro, adjudicado, postular, monto estimado, cierre*. Estos términos dan credibilidad; se usan con naturalidad, no se sobre-explican.
- **Energía con mesura.** El nombre es "ProyectosYa" — el "Ya" aporta urgencia positiva. Se usa en CTAs y titulares ("Postula ya", "Postula a la licitación correcta, hoy") pero sin gritar. Sin signos de exclamación apilados.
- **Casing:** títulos en *sentence case* ("De tu perfil a la postulación, en tres pasos"), no Title Case. Eyebrows/overlines en MAYÚSCULAS con tracking amplio. Botones en sentence case ("Crear mi perfil", "Ver análisis").
- **Números y montos:** formato chileno con puntos de miles y signo peso: `$12.480.000`. IDs y porcentajes en fuente mono.
- **Emoji:** **no.** La calidez viene del color, la tipografía y el tono — no de emoji. (Excepción tolerada: nunca en producto; jamás en UI.)
- **Tagline de marca:** *"Menos papeleo. Más proyectos ganados."*
- **Microcopy de ejemplo:** título → "Hola, Camila"; subtítulo → "Tienes 8 licitaciones nuevas que calzan con tu perfil esta semana"; estado vacío sugerido → "Aún no hay matches nuevos. Completa tu perfil para mejorar tus resultados."

**Así sí:** "Encontramos 8 licitaciones que calzan con tu giro esta semana."
**Así no:** "El sistema ha procesado satisfactoriamente las oportunidades disponibles."

---

## VISUAL FOUNDATIONS

**Vibe general:** cálido, fresco, inteligente, ordenado. Mucho aire. Una superficie blanca limpia sobre un fondo off-white cálido, acentos de color usados con intención (no decoración). Nada de gradientes morados, ni cards con borde-izquierdo de color, ni saturación dura.

### Color
- **Fondo página:** off-white cálido `--bg-page #FBF8F3`. **Tinta:** negro cálido `--warm-900 #1B1814` (nunca `#000`).
- **Primario teal** `--teal-500 #0E8580` → confianza, inteligencia, el "match". Es el color de las acciones primarias, estados activos y del MatchMeter alto.
- **Acento coral** `--coral-500 #E0552F` → energía, el "Ya", CTAs de alta intención (botón `accent`). Se usa con moderación, como chispa.
- **Neutrales cálidos** (`--warm-*`): toda la escala de grises tiene un sesgo cálido, no azulado.
- **Estados semánticos suaves:** verde `#2F8F5B` (adjudicado/éxito), ámbar `#D6960F` (cierra pronto/advertencia), rojo `#CC3B2E` (vencida/error), azul `#2E78A6` (info). Siempre en versiones suaves para fondos (`*-soft`).
- **Regla:** máximo 1–2 colores de fondo por pantalla. El teal a gran escala (banda CTA) se usa para momentos de cierre, no en todo.

### Tipografía
- **Display — Bricolage Grotesque** (600/700): titulares, números grandes. Carácter fresco y un poco humano; tracking apretado (`-0.02em`).
- **Texto/UI — Hanken Grotesk** (400–700): cuerpo, labels, botones. Cálida, amistosa, muy legible.
- **Mono — Spline Sans Mono** (400–600): IDs de licitación, montos, porcentajes de compatibilidad. Redondeada y amigable, no técnica-fría.
- Escala de `--text-xs 12` a `--text-7xl 76`. Cuerpo 16px, line-height 1.5–1.6. Eyebrows 12px MAYÚS con tracking `0.08em` en color primario.

### Espaciado y layout
- Grilla base **4px** (`--space-*`). Contenido principal centrado con `max-width` (~920 app, ~1120 landing). Generoso padding interno en cards (20–24px).
- Layouts de dos columnas con rail pegajoso (`position: sticky`) para acciones (detalle de licitación, perfil).

### Bordes, radios y elevación
- **Radios suaves y amigables:** cards `--radius-lg 16px`, botones/inputs `--radius-md 12px`, pills `--radius-pill`, bandas grandes `--radius-2xl 32px`. Nada de esquinas vivas.
- **Bordes** finos `1px` en neutrales cálidos (`--border-subtle/-default`). Las cards combinan borde sutil + sombra suave.
- **Sombras cálidas:** tintadas con la tinta a baja opacidad (`rgba(27,24,20,…)`), nunca negro puro ni duras. Escala `--shadow-xs → -xl`. Sombras de color (`--shadow-teal/-coral`) para elementos flotantes destacados.

### Movimiento, hover y press
- **Movimiento gentil, sin rebote** por defecto. Easing estándar `cubic-bezier(0.4,0,0.2,1)`; salidas suaves con `--ease-out`. Duraciones 120/200/320ms.
- **Hover:** los botones primario/acento **oscurecen** el fondo (no aclaran); secundarios toman un tinte cálido y borde más marcado; cards interactivas **se elevan** 2px y profundizan la sombra.
- **Press:** los botones **encogen** (`scale 0.97`, icon-buttons `0.94`). Foco con anillo teal de 3px (`--ring`).
- Animaciones de progreso del MatchMeter: el arco se dibuja con transición de `stroke-dashoffset`.

### Imágenes, transparencia y fondos
- Sin fotografía pesada ni ilustraciones recargadas. Los "héroes" son **componentes reales del producto** (la card de match flotante) — el producto es el visual.
- Bandas a color sólido (teal) con **círculos concéntricos sutiles** de la misma familia como textura, nunca gradientes ruidosos.
- **Blur/transparencia:** solo en chrome pegajoso (topbar, nav landing) con `backdrop-filter: blur` + fondo semitransparente del color de página. Uso funcional, no decorativo.

---

## ICONOGRAPHY

- **Set:** **[Lucide](https://lucide.dev)** (UMD vía CDN: `https://unpkg.com/lucide@latest`). Línea limpia, **stroke 2px**, esquinas redondeadas — calza con la calidez de la marca sin ser infantil.
- **Sustitución declarada:** como no había un set de iconos de origen, se eligió Lucide como el más cercano al carácter buscado (trazo medio, geométrico-amistoso). Si se define un set propio, reemplazar en el componente `Icon` y documentarlo aquí.
- **Componente:** usar siempre `<Icon name="…" />` (wrapper de Lucide); hereda `currentColor`, tamaño por prop. No pegar SVGs sueltos.
- **Tamaños:** 16px inline en texto/labels, 18–20px en botones/nav, 22–24px en encabezados de sección/tiles.
- **Vocabulario de iconos frecuente:** `sparkles` (IA / match), `search`, `target`, `file-text`, `building-2` (empresa/organismo), `map-pin` (región), `bell` (alertas), `bookmark` (guardar), `send` (postular), `check` / `check-circle-2`, `shield-check`, `trending-up`, `clock`, `arrow-right`.
- **Emoji como icono:** no se usa. **Unicode como icono:** no. Todo icono pasa por Lucide.
- **Logo/marca:** el "mark" (`assets/logo-mark.svg`) es un checkmark cálido con punto coral — se usa como favicon/app icon; el wordmark para headers. No redibujar el logo a mano; usar los SVG provistos.

---

## Cómo consumir este sistema

1. Enlaza **`styles.css`** (trae tokens + fuentes + defaults base).
2. Carga el runtime de componentes: `<script src="…/_ds_bundle.js"></script>` (generado por el compilador) y lee `const { Button, MatchMeter, … } = window.ProyectosYaDesignSystem_1dd038`.
3. En artefactos visuales (slides, mocks, prototipos), enlaza Lucide y React/Babel como en `ui_kits/app/index.html`.
4. Usa los tokens semánticos (`--primary`, `--surface-card`, `--text-strong`) en vez de valores crudos.
