// ============================================================================
// CHENG — Vitest smoke-only configuration
//
// Runs only the Tier 1 smoke tests (tests/frontend/smoke/**/*.smoke.test.ts).
// Used by scripts/test-precommit.sh for fast pre-commit validation.
//
// Usage:
//   cd frontend && pnpm exec vitest run --config ../tests/frontend/vitest.smoke.config.ts
//
// Target: < 15 seconds total.
// ============================================================================

import { defineConfig } from 'vitest/config';
import path from 'path';
import { createRequire } from 'module';

const frontendDir = path.resolve(__dirname, '../../frontend');
const smokeTestDir = path.resolve(__dirname, 'smoke');

// Resolve @vitejs/plugin-react from the frontend's own node_modules
const require = createRequire(path.join(frontendDir, 'package.json'));
// eslint-disable-next-line @typescript-eslint/no-require-imports
const react = require(path.join(frontendDir, 'node_modules/@vitejs/plugin-react')).default;

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    root: frontendDir,
    include: [smokeTestDir.replace(/\\/g, '/') + '/**/*.smoke.test.{ts,tsx}'],
    globals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(frontendDir, 'src'),
      '@testing-library/react': path.resolve(frontendDir, 'node_modules/@testing-library/react'),
      'fake-indexeddb/auto': path.resolve(frontendDir, 'node_modules/fake-indexeddb/auto'),
      'fake-indexeddb': path.resolve(frontendDir, 'node_modules/fake-indexeddb'),
    },
  },
});
