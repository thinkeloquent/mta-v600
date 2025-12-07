// packages_mjs/static-config-property-management/jest.config.mjs

export default {
  testEnvironment: "node",
  testMatch: ["<rootDir>/tests/**/*.test.mjs"],
  moduleFileExtensions: ["js", "mjs", "json"],
  // Use native ESM instead of transforming
  transform: {},
};
