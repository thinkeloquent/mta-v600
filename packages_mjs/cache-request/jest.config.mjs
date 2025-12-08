/** @type {import('jest').Config} */
export default {
  preset: 'ts-jest/presets/default-esm',
  extensionsToTreatAsEsm: ['.mts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.mjs$': '$1',
  },
  transform: {
    '^.+\\.m?ts$': [
      'ts-jest',
      {
        useESM: true,
        tsconfig: {
          module: 'ESNext',
          moduleResolution: 'NodeNext',
          target: 'ESNext',
          esModuleInterop: true,
          allowSyntheticDefaultImports: true,
        },
      },
    ],
  },
  testMatch: ['**/tests/**/*.test.mts'],
  testEnvironment: 'node',
  collectCoverageFrom: [
    'src/**/*.mts',
    '!src/**/*.d.mts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
};
