Styled native dropdown with custom chevron.

```jsx
<Select label="Región" placeholder="Selecciona…" options={["RM","Valparaíso","Biobío"]} value={r} onChange={setR} />
```

`options` accepts strings or `{value,label}`. `onChange(value, event)` returns the value.
