# Patrones

## Dónde va cada archivo

El frontend se organiza por feature, no por tipo de archivo.

```
src/
  app/                      Rutas de Next.js. Solo composición.
    (app)/                  Pantallas autenticadas: matches, buscar, guardados, empresa, alertas, configuracion
    (auth)/                 login, register, verificar
    (onboarding)/perfil     Wizard de perfil
    (public)/               Páginas abiertas
    globals.css             Todos los tokens
  features/
    <feature>/
      components/           Componentes de esta feature
      hooks/                Hooks de esta feature
      services/             Llamadas al backend
      utils/
      <feature>Types.ts     Tipos del dominio
      <feature>Schema.ts    Esquemas de zod
      __tests__/
    shared/
      components/           Las doce primitivas
      api/
```

Los archivos de `app/` deben ser delgados. Toda la lógica vive en la feature. Una página
que pasa de unas pocas decenas de líneas casi siempre tiene un componente escondido
adentro.

Las rutas van en español, igual que la interfaz: `/matches`, `/buscar`, `/empresa`.

## Componentes cliente

Next.js con App Router. Todo es Server Component salvo que declares `"use client"`.

Declara el cliente lo más abajo posible del árbol. Si una página solo necesita
interactividad en un formulario, es el formulario el que lleva la directiva, no la
página.

## Formularios

El patrón del repo es react-hook-form con zod. El esquema vive en el archivo
`<feature>Schema.ts` de la feature y exporta también el tipo inferido.

```tsx
export const loginSchema = z.object({
  email: z.string().email("Correo electrónico inválido"),
  password: z.string().min(8, "La contraseña debe tener al menos 8 caracteres"),
});

export type LoginData = z.infer<typeof loginSchema>;
```

Los mensajes de validación se escriben en el esquema, en español, y llegan solos al
prop `error` del `Input`. No los dupliques en el componente.

```tsx
const { register, handleSubmit, formState: { errors } } = useForm<LoginData>({
  resolver: zodResolver(loginSchema),
});
```

Nunca derives el tipo del formulario a mano. Sale de `z.infer`.

## Errores

Hay dos clases de error y se muestran distinto.

Los de validación van en el campo, vía el prop `error`.

Los del servidor van en un banner sobre el formulario, con
`bg-danger-soft/30 border border-danger/20 text-danger`.

Antes de mostrar un error de una API, tradúcelo. `LoginForm.tsx` tiene la función
`mensajeDeError` como referencia: toma lo que devuelve Supabase y lo convierte en algo
que le sirve a la persona. Un mensaje en inglés que se filtra a la pantalla es un bug.

## Estados de carga

Los botones traen su spinner en `isLoading`. Para contenido, usa esqueletos con
`bg-warm-100` y `animate-pulse`, respetando la altura final del contenido para que la
página no salte.

## Accesibilidad

- Cada control necesita su etiqueta. Las primitivas ya la manejan, por eso `label` es
  obligatorio en `Input`, `Textarea` y `TagInput`.
- Los elementos decorativos llevan `aria-hidden="true"`, como el punto del `Badge`.
- El foco se ve siempre. Nunca elimines el outline sin poner un `focus-visible:ring`.
- Los íconos que van solos en un botón necesitan `aria-label`.
- El contraste se verifica contra `--bg-page`, no contra blanco. El mostaza `#DB9E23`
  sobre off-white no alcanza para texto pequeño: úsalo como fondo con `text-on-accent`,
  o sube a `--coral-700` para texto.

## Tests

Vitest con Testing Library para unitarios, Playwright para end to end.

```bash
pnpm run test
pnpm run test:e2e
```

Los tests van en `__tests__/` dentro de la feature. Se consulta por rol y por texto
visible, no por clase CSS ni por test id. Si un test necesita un `data-testid` para
encontrar algo, normalmente el problema es que a ese algo le falta una etiqueta
accesible.

Los flujos de interfaz que se tocaron necesitan correr también los e2e antes del commit.

## TypeScript

`any` está prohibido. Cuando el tipo no se conoce, usa `unknown` y estrecha, o define la
interfaz.

Las variantes se tipan con unión y se resuelven con un `Record`:

```tsx
type ButtonVariant = "primary" | "ghost" | "accent";
const variants: Record<ButtonVariant, string> = { ... };
```

Así, agregar una variante y olvidar su clase deja de compilar.

## Commits

Conventional Commits, en minúsculas, con alcance. El frontend usa `feat(front): ...`,
`fix(ui): ...` y similares. Los commits hechos por un agente lo declaran en el cuerpo,
según las reglas de `SKILL.md` en la raíz del repo.
