import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'worker/auth/*.test.ts', 'worker/ella/*.test.ts'],
    testTimeout: 15000,
  },
});
