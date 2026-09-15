---
name: chiripa-frontend
description: Manual de diseño y convenciones de frontend de Chiripa. Úsala siempre que trabajes en el frontend del monorepo: crear o modificar pantallas, componentes React, formularios, estilos con Tailwind, rutas de Next.js, o cuando haya que decidir un color, un tamaño de texto, un espaciado o un estado de interacción. También cuando alguien pregunte por la marca, la paleta, las tipografías o cómo se ve algo en la app.
---

# Frontend de Chiripa

Chiripa ayuda a MiPymes chilenas a ganar licitaciones de ChileCompra y Compra Ágil.
Bajada de marca: **Licitaciones inteligentes**.

Esta skill es la fuente de verdad para cualquier cosa que se vea en pantalla. Si lo que
vas a escribir contradice algo de acá, lo que está acá manda.

## Antes de escribir una sola línea de UI

1. **Busca el componente antes de crearlo.** Revisa `src/features/shared/components/`.
   Hay doce primitivas ya construidas. Crear un botón nuevo porque no encontraste el
   que existe es el error más caro de este repo.
2. **Nunca escribas un color en hexadecimal.** Todo color sale de un token semántico.
   Ver [tokens.md](references/tokens.md).
3. **Si el componente es de una feature, vive en esa feature.** Solo sube a `shared/`
   cuando lo usen dos features distintas.

## Reglas que no se negocian

### Color

Los únicos cinco colores de marca son estos, y ya están en tokens:

| Manual | Token de marca | Token semántico | Uso |
|---|---|---|---|
| `#2D4F2C` | `--teal-800` | `--shadow-teal`, fondos oscuros | Verde profundo, isotipo y superficies fuertes |
| `#6D8657` | `--teal-500` | `--primary` | Acciones, enlaces, estados activos |
| `#DB9E23` | `--coral-500` | `--accent` | Acento de energía, uso escaso |
| `#FFC246` | `--coral-400` | destacados suaves | Amarillo brillante, highlights |
| `#FBF8F3` | `--warm-50` | `--bg-page` | Fondo de toda la app |

En el código escribes la clase semántica, no la de marca. `bg-primary`, no `bg-teal-500`.
`text-text-muted`, no `text-warm-600`. Las escalas crudas existen para casos donde
necesitas un tono intermedio que no tiene nombre semántico.

Nunca uses negro puro ni blanco puro como fondo de página o color de texto. La marca es
cálida: tinta `--warm-900`, fondo `--warm-50`.

El acento mostaza es para energía, no para volumen. Si en una pantalla hay más de uno o
dos elementos en `--accent`, está mal balanceada.

### Tipografía

- **Bricolage Grotesque** para títulos. Ya está aplicada a `h1`–`h5` en la capa base,
  así que no repitas `font-display` salvo que estés titulando algo que no es un heading.
- **Hanken Grotesk** para texto y UI. Es el default del `body`.
- **Spline Sans Mono** para IDs de licitación, montos y cualquier dato tabular.

> El manual de marca nombra **Sinar Grotesque** para texto. No es una fuente de Google
> Fonts y no está licenciada en el proyecto, así que la implementación usa Hanken
> Grotesk como sustituto. No cambies esto por tu cuenta: si se compra la licencia, se
> reemplaza en un solo lugar, el `@import` de `globals.css`.

### TypeScript

`any` está prohibido en todo el repo. Usa `unknown`, genéricos o define la interfaz.
Las variantes de un componente se tipan con una unión y se resuelven con
`Record<Variante, string>`, como en `Button.tsx`.

### Interacción

Todo lo clickeable necesita estado de foco visible. El patrón del repo es
`focus-visible:ring-2 focus-visible:ring-primary/30`. Los botones además bajan de tono
en hover y encogen en press con `active:scale-[0.98]`.

### Idioma

Todo el texto de cara al usuario va en español de Chile, con tuteo y en sentence case.
Sin emoji. Los mensajes de error dicen qué hacer, no qué falló: mira `mensajeDeError`
en `LoginForm.tsx` como referencia.

## Qué ya existe

Doce primitivas en `src/features/shared/components/`:

**Formularios**: `Input`, `Textarea`, `Switch`, `TagInput`, `ChipSelect`, `Button`
**Feedback**: `Badge`, `MatchMeter`
**Layout y navegación**: `Avatar`, `Sidebar`, `WizardProgress`, `Icon`

`MatchMeter` es el componente firma de la marca: el anillo de compatibilidad 0 a 100.
No lo reimplementes ni lo recolorees.

La API de cada uno está en [componentes.md](references/componentes.md).

## Referencias

- [tokens.md](references/tokens.md) — paleta completa, espaciado, radios, sombras y qué token usar cuándo.
- [componentes.md](references/componentes.md) — catálogo con props y ejemplos.
- [patrones.md](references/patrones.md) — estructura por feature, formularios, estados de carga, accesibilidad y tests.
- [marca.md](references/marca.md) — logo, bajada, tono de voz y referencias visuales.

## Una advertencia

`monorepo/frontend/templates/` contiene un kit de diseño anterior, de cuando el producto
se llamaba ProyectosYa. Su paleta es teal `#0E8580` y coral `#E0552F`, que ya no son la
marca. No copies nada de ahí sin traducir los colores a los tokens actuales.
