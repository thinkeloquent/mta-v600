/** @type {import('jest').Config} */
export default {
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.mts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.mjs$': '$1.mts',
  },
  transform: {
    '^.+\\.m?tsx?$': [
      'babel-jest',
      {
        presets: [
          ['@babel/preset-env', { targets: { node: 'current' } }],
          '@babel/preset-typescript',
        ],
      },
    ],
  },
  testMatch: ['**/tests/**/*.test.mts'],
  moduleFileExtensions: ['ts', 'mts', 'js', 'mjs', 'json'],
  collectCoverageFrom: ['src/**/*.mts', '!src/**/*.d.mts'],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov'],
  verbose: true,
};
