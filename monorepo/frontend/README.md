This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

> [!IMPORTANT]
> **Es obligatorio utilizar `pnpm` para la gestión de dependencias en este proyecto.** Por razones de seguridad, optimización de espacio y consistencia en el árbol de dependencias, bajo ninguna circunstancia se debe ejecutar `npm` o `yarn`.


## Getting Started

First, run the development server:

```bash
pnpm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

Esta aplicación utiliza el sistema de ruteo **Next.js App Router** en combinación con los principios de **Screaming Architecture** (Arquitectura que grita su dominio) para mantener un diseño limpio, desacoplado y orientado al negocio.

---

## Estructura de Carpetas (Screaming Architecture)

La estructura principal del código se encuentra bajo el directorio `src/`:

```text
src/
├── app/                         # Enrutamiento de Next.js (Wrapper delgado)
│   ├── page.tsx                 # Renderiza <DashboardTenders /> (página de inicio)
│   ├── perfil/
│   │   └── page.tsx             # Renderiza <ProfileFlow /> (página de perfil)
│   └── layout.tsx
├── features/                    # Características de negocio (Módulos autocontenidos)
│   ├── company-profile/         # Módulo Perfil de la Empresa (HU-002, HU-010)
│   │   ├── components/          # Componentes visuales específicos de la característica
│   │   ├── hooks/               # Custom hooks de React específicos
│   │   ├── services/            # Servicios y clientes de API del módulo
│   │   └── __tests__/           # Tests Unitarios y de Integración CO-LOCALIZADOS
│   │       ├── ProfileFlow.test.tsx
│   │       └── useProfile.test.ts
│   ├── tenders/                 # Módulo de Licitaciones (HU-003, HU-004, HU-005)
│   │   ├── components/
│   │   ├── hooks/
│   │   └── __tests__/
│   └── shared/                  # Módulos y elementos transversales reutilizables
│       ├── components/          # Componentes atómicos comunes (Button, Input, Card)
│       │   ├── Button.tsx
│       │   └── __tests__/
│       │       └── Button.test.tsx
│       └── utils/
└── domain/                      # Modelos, contratos y tipos de datos globales
```

### Reglas de la Arquitectura Frontend

1. **Páginas Delgadas (`src/app`)**: Las páginas en `src/app/` deben actuar únicamente como contenedores mínimos de ruteo. No deben contener lógica de negocio, manejo de estado complejo, ni llamadas directas de red. Toda esa lógica debe delegarse a los componentes y hooks de `src/features/`.
2. **Co-localización de Tests**: Las pruebas unitarias y de integración de componentes/hooks deben estar ubicadas en una carpeta `__tests__/` inmediatamente al lado del código que prueban. Esto facilita el mantenimiento, la refactorización y deja en claro la cobertura del módulo.
3. **Módulos Autocontenidos (`src/features/...`)**: Las características deben evitar importar elementos internos de otras características (excepto si provienen de `shared/`). Si la característica `tenders` necesita interactuar con el perfil de empresa, debe hacerse mediante interfaces claras o a través de hooks compartidos en la capa superior.

---

## Pruebas y TDD

El proyecto está configurado para desarrollo guiado por pruebas (TDD) utilizando **Vitest** para pruebas unitarias de componentes/hooks y **Playwright** para pruebas de integración End-to-End (E2E).

### Ejecutar Pruebas Unitarias y de Componentes

Para ejecutar la suite de pruebas unitarias locales (Vitest):

```bash
# Ejecutar todas las pruebas una sola vez
pnpm test

# Ejecutar pruebas en modo de observación continua (watch)
pnpm test:watch
```

### Ejecutar Pruebas End-to-End (E2E)

Las pruebas de extremo a extremo simulan el comportamiento del usuario en el navegador utilizando **Playwright**:

```bash
# Ejecutar pruebas E2E
pnpm test:e2e
```
Las pruebas de Playwright se definen en el directorio raíz `e2e/` del frontend.

