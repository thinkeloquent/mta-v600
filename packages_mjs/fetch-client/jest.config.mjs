export default {
  testEnvironment: 'node',
  testMatch: ['<rootDir>/tests/**/*.test.ts'],
  transform: {
    '^.+\\.(ts|tsx|js|jsx|mjs|mts)$': ['babel-jest', { configFile: './babel.config.mjs' }],
  },
  transformIgnorePatterns: ['<rootDir>/node_modules/(?!uuid|zod)/'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node', 'mjs', 'mts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.mjs$': '$1.mts',
    '^(\\.{1,2}/.*)\\.mts$': '$1.mts',
    '^@internal/fetch-auth-encoding$': '<rootDir>/../fetch-auth-encoding/src/index.ts',
  },
  collectCoverageFrom: ['src/**/*.mts'],
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
