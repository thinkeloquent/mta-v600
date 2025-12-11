export default {
  testEnvironment: 'node',
  moduleFileExtensions: ['js', 'mjs'],
  testMatch: ['**/tests/**/*.test.mjs'],
  transform: {
    '^.+\\.m?js$': 'babel-jest',
  },
  transformIgnorePatterns: [],
  collectCoverageFrom: ['src/**/*.mjs'],
  coverageDirectory: 'coverage',
  verbose: true,
};
