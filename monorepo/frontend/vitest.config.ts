import { defineConfig, configDefaults } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// Las fechas se muestran en la zona horaria del navegador del usuario. Fijamos
// una zona conocida para que los tests de formato sean deterministas y no
// dependan de la configuración de la máquina que ejecuta la suite.
process.env.TZ = 'America/Santiago';

// El módulo de configuración de Supabase lanza al importarse si faltan estas
// variables, y es a propósito (ver src/features/auth/supabase/env.ts). En los
// tests nada llega a la red: se rellenan con valores reconocibles para que los
// módulos que lo importan se puedan cargar.
process.env.NEXT_PUBLIC_SUPABASE_URL ??= 'http://127.0.0.1:54321';
process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??= 'clave-publicable-de-pruebas';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './vitest.setup.ts',
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
});
