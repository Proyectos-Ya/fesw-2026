# Tokens

Todos viven en `monorepo/frontend/src/app/globals.css`. Ese archivo es la única fuente
de verdad. Si necesitas un valor que no está acá, agrégalo ahí como token antes de
usarlo, nunca inline en un componente.

Cada token está expuesto dos veces: como custom property CSS (`var(--primary)`) y como
utilidad de Tailwind vía `@theme` (`bg-primary`). En componentes React usa la utilidad.
La custom property es para SVG, gradientes y cálculos en línea, como hace `MatchMeter`.

## Cuál usar

La regla corta: **elige por significado, no por color**. Si estás eligiendo entre
`bg-teal-500` y `bg-primary` para un botón de acción, la respuesta es `bg-primary`.
Si mañana cambia la marca, los semánticos se mueven solos.

### Superficies

| Token | Valor | Cuándo |
|---|---|---|
| `bg-page` | `--warm-50` | Fondo de la página. Ya está en `body`. |
| `bg-sunken` | `--warm-100` | Zonas hundidas, fondos de listas |
| `surface-card` | blanco | Tarjetas sobre el fondo cálido |
| `surface-inset` | `--warm-100` | Cajas embutidas dentro de una tarjeta |
| `surface-teal` | `--teal-50` | Realces verdes muy suaves |
| `surface-coral` | `--coral-50` | Realces amarillos muy suaves |

### Texto

| Token | Cuándo |
|---|---|
| `text-text-strong` | Títulos y etiquetas de formulario |
| `text-text-body` | Párrafos. Default del `body`. |
| `text-text-muted` | Texto secundario, ayudas, metadatos |
| `text-text-subtle` | Placeholders y texto casi decorativo |
| `text-on-primary` | Sobre fondo verde |
| `text-on-coral` | Sobre fondo mostaza |
| `text-text-link` | Enlaces desnudos, ya aplicado a `a:not([class])` |

### Acción

`primary`, `primary-hover`, `primary-active`, `primary-soft`, `primary-border`,
`on-primary`. La misma familia existe para `accent`.

El patrón de un botón sólido es: fondo `primary`, hover `primary-hover`, press
`primary-active`, texto `on-primary`.
El de un botón suave es: fondo `primary-soft`, borde `primary-border`, texto `primary`.

### Estado

`success`, `warning`, `danger`, `info`, cada uno con su variante `-soft` para fondos.

Los fondos de estado se usan a baja opacidad sobre superficies claras. El patrón del
repo es `bg-danger-soft/30` con `border-danger/20`, como en el banner de error del login.

### Bordes

`border-subtle` para divisiones dentro de una tarjeta, `border-default` para el borde de
un control, `border-strong` para el hover de ese control. `divider` para separadores.

## Escalas crudas

Existen `warm-50` a `warm-900`, `teal-50` a `teal-900` y `coral-50` a `coral-900`.

Ojo con los nombres. Los prefijos `--teal-` y `--coral-` quedaron del branding anterior
y ya no describen el color: `teal` es verde salvia y `coral` es mostaza. Se mantuvieron
para no renombrar cada utilidad del código. No te confíes del nombre, confía del token
semántico.

Anclas útiles: `teal-500` `#6D8657` es el primario, `teal-800` `#2D4F2C` es el verde
profundo del isotipo, `coral-500` `#DB9E23` es el acento, `coral-400` `#FFC246` es el
amarillo brillante, `warm-50` `#FBF8F3` es el fondo.

## Espaciado

Base de 4px, de `--space-1` (`0.25rem`) a `--space-16` (`4rem`). En la práctica usas las
utilidades normales de Tailwind, que comparten la misma escala. Los tokens están para
CSS a mano.

## Radios

`--radius-xs` 4px, `sm` 8px, `md` 12px, `lg` 16px, `xl` 22px.

Controles y botones usan `rounded-md`. Tarjetas usan `rounded-lg`. Badges y chips usan
`rounded-full`. Nada en la marca es de esquina viva.

## Sombras

`shadow-xs` a `shadow-lg` son sombras cálidas neutras, todas tintadas con `rgba(27, 24, 20, ...)`.
`shadow-premium` es para tarjetas destacadas.
`shadow-teal` y `shadow-coral` son sombras de color para botones sólidos, y solo se usan ahí.

Nunca uses una sombra negra pura. Rompe la calidez de la paleta.

## Utilidad propia

`eyebrow` es la única utilidad custom: texto pequeño, en mayúsculas, con tracking abierto
y en color primario. Es el antetítulo de las secciones.
