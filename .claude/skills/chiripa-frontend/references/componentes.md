# Catálogo de componentes

Todo está en `monorepo/frontend/src/features/shared/components/`.
Se importan por alias absoluto: `import { Button } from "@/features/shared/components/Button";`

Todos son exports nombrados, no default. Todos aceptan `className` para ajustes de
posición o margen. `className` es para acomodar el componente en su contexto, no para
repintarlo: si necesitas cambiarle el color, lo que falta es una variante nueva.

## Formularios

### `Button`

```tsx
<Button variant="primary" isLoading={enviando}>Guardar</Button>
```

`variant` es `"primary" | "ghost" | "accent"`, default `primary`. Extiende los props
nativos de `<button>`.

`primary` es la acción de la pantalla. `accent` es para el CTA de alta energía y debería
aparecer una vez por vista como mucho. `ghost` es para acciones secundarias.

`isLoading` muestra un spinner y deshabilita el botón solo. No lo combines con `disabled`
manual ni pongas tu propio spinner adentro.

### `Input`

```tsx
<Input label="Correo electrónico" error={errors.email?.message} {...register("email")} />
```

`label` es obligatorio, y de ahí sale el `id` y la asociación del `<label>`. No pongas
un `<label>` por fuera.

`error` y `hint` se excluyen: si hay error, el hint no se muestra. Extiende los props
nativos de `<input>`, así que `type`, `placeholder` y el spread de react-hook-form
funcionan directo.

### `Textarea`

Mismos props que `Input`, más `charCount` y `maxChars` para el contador de caracteres.

### `Switch`

```tsx
<Switch checked={activo} onChange={setActivo} label="Alertas diarias" description="..." />
```

Controlado. `onChange` recibe el booleano, no el evento.

### `TagInput`

```tsx
<TagInput label="Rubros" tags={rubros} onChange={setRubros} optional />
```

Para listas de texto libre que el usuario escribe. `onChange` recibe el arreglo completo.

### `ChipSelect`

```tsx
<ChipSelect label="Regiones" options={REGIONES} selected={seleccion} onChange={setSeleccion} />
```

Para selección múltiple desde un conjunto cerrado. `options` es `readonly string[]`.

Si las opciones son libres usa `TagInput`. Si son fijas usa `ChipSelect`. No mezcles.

## Feedback

### `Badge`

```tsx
<Badge tone="success" dot>Publicada</Badge>
```

`tone` es `"neutral" | "teal" | "coral" | "success" | "warning" | "danger" | "info" | "solid"`,
default `neutral`. `dot` antepone un punto del color actual. `iconLeft` acepta un nodo.

Usa los tonos de estado para estados reales del dominio. `teal` y `coral` son para
categorías, no para decir que algo salió bien o mal.

### `MatchMeter`

```tsx
<MatchMeter value={87} size="lg" label="Compatibilidad" />
```

El anillo de compatibilidad, componente firma de la marca. `value` va de 0 a 100.
`size` es `"sm" | "md" | "lg"`, con diámetros de 44, 64 y 92 píxeles.

Cambia de color solo según umbrales: sobre 80 va en verde, sobre 60 en ámbar, bajo eso
en gris cálido. `thresholds` y `colors` se pueden sobrescribir, pero no lo hagas sin una
razón de producto. La lectura de color es parte de cómo la gente entiende el match.

## Layout y navegación

### `Avatar`

```tsx
<Avatar name="Camila Rojas" size="md" />
```

Sin `src` genera iniciales sobre un color tomado de una paleta fija, derivado del nombre.
Tamaños `xs` 24, `sm` 32, `md` 40, `lg` 56. `shape` es `"circle" | "square"`.

### `Sidebar`

La navegación lateral de la app. Los ítems están definidos dentro del componente en
`NAV_ITEMS`, no se pasan por props. Para agregar una sección de la app, se edita ahí.

### `WizardProgress`

```tsx
<WizardProgress currentStep={2} totalSteps={5} />
```

La barra de pasos del onboarding.

### `Icon`

```tsx
<Icon name="building-2" size={16} />
```

Envuelve Lucide. `name` es el nombre en kebab-case del ícono de Lucide.

Usa este componente en vez de importar íconos sueltos de `lucide-react`. Mantiene el
tamaño y el grosor de línea consistentes, y evita que el bundle crezca por importaciones
directas dispersas.
