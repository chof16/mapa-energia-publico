// Web application configuration within the monorepo.
import { defineConfig } from 'vitest/config';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', 'MAPA_');
  return {
    publicDir: environment.MAPA_MAP_ASSETS_DIR || 'public',
    server: {
      proxy: {
        '/v1': environment.MAPA_API_PROXY_TARGET || 'http://127.0.0.1:8001',
      },
    },
    plugins: [react()],
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      clearMocks: true,
      restoreMocks: true,
    },
    optimizeDeps: {
      exclude: ['maplibre-gl'],
    },
  };
});
