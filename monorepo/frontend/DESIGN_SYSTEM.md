# Design System — Chiripa / ProyectosYA

## Fonts

| Role      | Font                  |
|-----------|-----------------------|
| Body / UI | **Hanken Grotesk**    |
| Headings  | **Bricolage Grotesque** (h1–h5) |
| Mono      | **Spline Sans Mono**  |

---

## Color Palette

### Brand scales

Used as Tailwind utilities: `bg-teal-500`, `text-warm-800`, etc.

| Scale   | Description                        | Key values |
|---------|------------------------------------|------------|
| `warm`  | Off-white → warm near-black (neutrals) | `50` = page bg · `800` = body text · `900` = strong text |
| `teal`  | Sage green — primary/brand color   | `500` = primary · `600` = hover · `700` = active |
| `coral` | Mustard yellow — accent color      | `500` = accent · `400` = bright yellow |

### Semantic status colors

| Color        | Use     |
|--------------|---------|
| `green-500` / `green-100` | success |
| `amber-500` / `amber-100` | warning |
| `red-500` / `red-100`     | danger  |
| `blue-500` / `blue-100`   | info    |

### Semantic tokens (CSS vars)

| Token             | Points to  |
|-------------------|------------|
| `--bg-page`       | warm-50    |
| `--surface-card`  | white      |
| `--surface-inset` | warm-100   |
| `--text-strong`   | warm-900   |
| `--text-body`     | warm-800   |
| `--text-muted`    | warm-600   |
| `--text-subtle`   | warm-500   |
| `--text-link`     | teal-600   |
| `--border-default`| warm-300   |
| `--primary`       | teal-500   |
| `--accent`        | coral-500  |

---

## Spacing

4px base grid. Tokens `--space-1` (4px) through `--space-16` (64px).

---

## Border Radii

| Token  | Value |
|--------|-------|
| `xs`   | 4px   |
| `sm`   | 8px   |
| `md`   | 12px  |
| `lg`   | 16px  |
| `xl`   | 22px  |

---

## Shadows

Elevation ladder: `xs` → `sm` → `md` → `lg` → `premium`.  
Colored glows: `shadow-teal`, `shadow-coral` for brand-colored elements.

---

## Components

| Component  | Variants / sizes |
|------------|-----------------|
| **Button** | `primary` (teal, shadow-teal) · `accent` (mustard, shadow-coral) · `ghost` (transparent) |
| **Badge**  | `neutral` · `teal` · `coral` · `success` · `warning` · `danger` · `info` · `solid`. Pill shape, optional `dot` or `iconLeft` |
| **Input**  | Label + input + hint/error. Error state: red border + soft-red background |
| **Avatar** | Sizes `xs/sm/md/lg`. Circle or square. Falls back to initials colored from a 6-color palette (teal, coral, amber…) |
| **Switch** | On = `--primary` (teal) · Off = warm-300 |
| **Icon**   | Wrapper over lucide-react. Accepts kebab-case names, converts to PascalCase internally |

---

## Interaction Patterns

- **Focus rings:** `ring-primary/30` (teal) or `ring-accent` (coral)
- **Hover/active:** next shade in the scale — `500` → `600` → `700`
- **Transitions:** `duration-200` everywhere
- **Active press:** `scale-[0.98]` on buttons
- **Active nav item:** `bg-primary-soft text-primary font-bold`

---

## Naming Conventions

- **Tailwind utilities** use scale names directly: `bg-teal-500`, `text-warm-800`
- **CSS var tokens** are semantic aliases used in inline styles or non-utility contexts: `var(--primary)`, `var(--text-muted)`
