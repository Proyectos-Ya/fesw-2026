Labelled text field; teal focus ring, coral error state.

```jsx
<Input label="RUT empresa" placeholder="76.123.456-7" hint="Sin puntos ni guión opcional" />
<Input label="Correo" type="email" error="Ingresa un correo válido" iconLeft={<Icon name="mail" size={18} />} />
```

Pass `iconLeft` for a leading icon, `error` to flip into the danger state.
