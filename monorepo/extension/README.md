# Chiripa — Extensión de Navegador

Extensión oficial de Chiripa para asistir a MiPymes en la postulación a licitaciones de Mercado Público y sincronizar bases oficiales.

## Instrucciones de Compilación Reproducible (Store Reviewers)

Este paquete ha sido construido utilizando **Node.js v22.x** y **pnpm v10.3.0**.

### 1. Requisitos
- Node.js >= 20.10.0 (recomendado: 22.x)
- pnpm 10.3.0 (`corepack enable` o `npm install -g pnpm@10.3.0`)

### 2. Instalación de dependencias
Desde el directorio `monorepo/extension`:
```bash
pnpm install --frozen-lockfile
```

### 3. Compilación para Chrome Web Store (Chromium)
```bash
pnpm run build:chrome
```
El paquete compilado se genera en `.output/chrome-mv3`.

Para empaquetar en zip:
```bash
pnpm run zip
```

### 4. Compilación para Firefox Add-ons (AMO)
```bash
pnpm run build:firefox
```
El paquete compilado se genera en `.output/firefox-mv2`.

Para validar con linter oficial de Mozilla:
```bash
pnpm run web-ext:lint
```

Para empaquetar en zip (incluye zip de fuentes para revisión):
```bash
pnpm run zip:firefox
```

### 5. Ejecución de pruebas
```bash
pnpm run test
pnpm run compile
```

## Descarga directa mientras no esté en las tiendas (HU-32, CA2)

Si la extensión no está instalada, el aviso de Chiripa ofrece descargar un `.zip` que sirve el
frontend desde `monorepo/frontend/public/extension/` (`chiripa-chrome.zip`,
`chiripa-firefox.zip` y `version.json`). Para regenerarlos con el build de producción:

```bash
pnpm run release:zips
```

Hay que hacerlo cada vez que cambie la extensión, y commitear los archivos generados.
`wxt zip` deja en `.output/` el build de producción; para volver a probar con el frontend en
localhost, recompilar con `pnpm run build:firefox:dev` o `pnpm exec wxt build -m development -b chrome`.
Cuando la extensión se publique, cambiar `EXTENSION_DISTRIBUTION` a `"store"` en
`monorepo/frontend/src/features/shared/extension/extensionLinks.ts`.
