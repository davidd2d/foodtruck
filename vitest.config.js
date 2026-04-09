import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: 'frontend/tests/js/setup.js',
    include: ['frontend/tests/js/**/*.test.js'],
  },
  resolve: {
    alias: {
      '@schedules': path.resolve('./static/js/schedules'),
    },
  },
});
