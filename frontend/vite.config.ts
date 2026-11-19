import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: `npm run dev` on :5173 proxies /api to the FastAPI backend on :8005.
// Build: output goes to ../static, which FastAPI serves at http://127.0.0.1:8005.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8005', changeOrigin: true },
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
    sourcemap: false,
  },
});
