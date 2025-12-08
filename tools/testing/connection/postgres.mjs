#!/usr/bin/env node
/**
 * Test PostgreSQL connection.
 */
import { runSingleTest } from './_base.mjs';

await runSingleTest('postgres');
