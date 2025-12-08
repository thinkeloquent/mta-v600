#!/usr/bin/env node
/**
 * Test all provider connections.
 */
import { runAllTests } from './_base.mjs';

// All providers from server.*.yaml (excluding placeholders)
const ALL_PROVIDERS = [
  'figma',
  'github',
  'jira',
  'confluence',
  'gemini',
  'openai',
  'saucelabs',
  'postgres',
  'redis',
  // Placeholders (will report not_implemented)
  'rally',
  'elasticsearch',
];

await runAllTests(ALL_PROVIDERS);
