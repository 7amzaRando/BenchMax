import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

/// <reference types="vitest/config" />
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    // Coverage is opt-in (`npm run test:coverage`) and intentionally NOT a
    // gate: no thresholds here, so `npm run test` / CI never fail on numbers.
    // Revisit thresholds once component coverage is meaningfully higher.
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/test/**', 'src/**/*.test.{ts,tsx}'],
    },
  },
})
