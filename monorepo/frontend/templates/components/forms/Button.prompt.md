Primary action button — use for the single most important action on a view; reach for `accent` (coral) only on high-energy "Ya"/postula moments.

```jsx
<Button variant="primary" size="md" onClick={postular}>Postular ahora</Button>
<Button variant="secondary" iconLeft={<Icon name="bookmark" />}>Guardar</Button>
<Button variant="accent" size="lg">Postula ya</Button>
```

Variants: `primary` (teal, default), `accent` (coral CTA), `secondary` (outlined on white), `ghost` (text-only), `soft` (teal tint). Sizes `sm | md | lg`. Press = scale 0.97; hover darkens. Pass `iconLeft` / `iconRight` for icons, `fullWidth` to stretch.
