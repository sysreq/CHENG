import { defineConfig } from 'vitest/config';
import path from 'path';
import { createRequire } from 'module';

const frontendDir = path.resolve(__dirname, '../../frontend');
const unitTestDir = path.resolve(__dirname, 'unit');

// Resolve @vitejs/plugin-react from the frontend's own node_modules
// (the tests/ directory doesn't have its own node_modules)
const require = createRequire(path.join(frontendDir, 'package.json'));
// eslint-disable-next-line @typescript-eslint/no-require-imports
const react = require(path.join(frontendDir, 'node_modules/@vitejs/plugin-react')).default;

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    root: frontendDir,
    include: [unitTestDir.replace(/\\/g, '/') + '/**/*.test.{ts,tsx}'],
    globals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(frontendDir, 'src'),
      '@testing-library/react': path.resolve(frontendDir, 'node_modules/@testing-library/react'),
      // fake-indexeddb is installed in frontend node_modules; resolve it from there
      // so tests in the tests/ directory can import it (#150)
      'fake-indexeddb/auto': path.resolve(frontendDir, 'node_modules/fake-indexeddb/auto'),
      'fake-indexeddb': path.resolve(frontendDir, 'node_modules/fake-indexeddb'),
    },
  },
});
