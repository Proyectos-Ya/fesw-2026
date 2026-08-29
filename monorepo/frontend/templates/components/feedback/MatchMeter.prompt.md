The brand's signature metric — a ring gauge for AI company↔tender compatibility (0–100). Use it on every licitación card and detail view.

```jsx
<MatchMeter value={94} size="lg" label="Alta" />
<MatchMeter value={71} size="sm" />
```

Colour is automatic by threshold: ≥80 teal, ≥60 amber, below muted. `size` sm/md/lg. Pass `label` to add the qualitative descriptor beside the ring.
