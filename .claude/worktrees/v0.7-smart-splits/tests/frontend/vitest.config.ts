import { defineConfig } from 'vitest/config';
import path from 'path';

const frontendDir = path.resolve(__dirname, '../../frontend');
const unitTestDir = path.resolve(__dirname, 'unit');

export default defineConfig({
  test: {
    environment: 'jsdom',
    root: frontendDir,
    include: [unitTestDir.replace(/\\/g, '/') + '/**/*.test.ts'],
    globals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(frontendDir, 'src'),
      '@testing-library/react': path.resolve(frontendDir, 'node_modules/@testing-library/react'),
    },
  },
});
