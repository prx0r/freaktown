import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: [
      'packages/*/tests/**/*.test.ts',
      'apps/live/src/**/*.test.ts',
      'edge/worker/**/*.test.ts',
    ],
    environment: 'node',
  },
});
