/** @type {import('jest').Config} */
export default {
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.mjs'],
  moduleFileExtensions: ['mjs', 'js'],
  transform: {},
  verbose: true,
  collectCoverageFrom: ['src/**/*.mjs'],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
};
