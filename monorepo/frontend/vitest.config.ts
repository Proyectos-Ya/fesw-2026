import { defineConfig, configDefaults } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// Las fechas se muestran en la zona horaria del navegador del usuario. Fijamos
// una zona conocida para que los tests de formato sean deterministas y no
// dependan de la configuración de la máquina que ejecuta la suite.
process.env.TZ = 'America/Santiago';

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
