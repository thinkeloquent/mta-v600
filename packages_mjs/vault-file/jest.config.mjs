// packages_mjs/vault-file/jest.config.mjs

const jestConfig = {
  testEnvironment: "node",
  testMatch: ["<rootDir>/tests/**/*.test.ts"],
  transform: {
    "^.+.(ts|tsx|js|jsx|mjs)$": [
      "babel-jest",
      { configFile: "./babel.config.mjs" },
    ],
  },
  transformIgnorePatterns: [
    "<rootDir>/node_modules/(?!uuid|zod)/", // Transform uuid and zod
  ],
  // No moduleNameMapper here for now, we will add it separately.
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node", "mjs"],
};

export default jestConfig;
