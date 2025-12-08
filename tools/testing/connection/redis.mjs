#!/usr/bin/env node
/**
 * Test Redis connection.
 */
import { runSingleTest } from './_base.mjs';

await runSingleTest('redis');
