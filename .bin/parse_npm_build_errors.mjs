#!/usr/bin/env node

/**
 * Parse TypeScript/Build errors from pnpm build log files
 *
 * Usage:
 *   ./.bin/parse-build-errors.mjs [options] [logfile]
 *
 * Options:
 *   --summary, -s         Show summary only (error counts per package)
 *   --package, -p NAME    Filter by package name (partial match)
 *   --type, -t CODE       Filter by error code (e.g., TS2305, TS6133)
 *   --json, -j            Output as JSON
 *   --jsonl, -l           Generate JSONL file (saves to <logfile>.jsonl)
 *   --output, -o FILE     Specify output file for JSONL (default: <logfile>.jsonl)
 *   --dedupe, -d          Remove duplicate errors (same file, line, code, message)
 *   --group, -g MODE      Group output: package, file, code, message (default: package)
 *   --sort, -S FIELD      Sort by: count, package, file, code, line (default: count)
 *   --exclude, -x CODES   Exclude error codes (comma-separated, e.g., TS6133,TS2305)
 *   --consolidate, -c     Consolidate similar messages (group by message pattern)
 *   --help, -h            Show help
 *
 * Examples:
 *   ./.bin/parse-build-errors.mjs logs/pnpm-build-error.log
 *   ./.bin/parse-build-errors.mjs -s logs/pnpm-build-error.log
 *   ./.bin/parse-build-errors.mjs -d -g code logs/pnpm-build-error.log
 *   ./.bin/parse-build-errors.mjs -x TS6133 logs/pnpm-build-error.log
 *   ./.bin/parse-build-errors.mjs -c -S count logs/pnpm-build-error.log
 *   ./.bin/parse-build-errors.mjs -l -d logs/pnpm-build-error.log
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, basename, dirname } from 'path';

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
};

function parseArgs(args) {
  const options = {
    summary: false,
    package: null,
    type: null,
    json: false,
    jsonl: false,
    output: null,
    dedupe: false,
    group: 'package',
    sort: 'count',
    exclude: [],
    consolidate: false,
    help: false,
    logFile: null,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case '--summary':
      case '-s':
        options.summary = true;
        break;
      case '--package':
      case '-p':
        options.package = args[++i];
        break;
      case '--type':
      case '-t':
        options.type = args[++i];
        break;
      case '--json':
      case '-j':
        options.json = true;
        break;
      case '--jsonl':
      case '-l':
        options.jsonl = true;
        break;
      case '--output':
      case '-o':
        options.output = args[++i];
        break;
      case '--dedupe':
      case '-d':
        options.dedupe = true;
        break;
      case '--group':
      case '-g':
        options.group = args[++i];
        break;
      case '--sort':
      case '-S':
        options.sort = args[++i];
        break;
      case '--exclude':
      case '-x':
        options.exclude = args[++i].split(',').map(c => c.trim().toUpperCase());
        break;
      case '--consolidate':
      case '-c':
        options.consolidate = true;
        break;
      case '--help':
      case '-h':
        options.help = true;
        break;
      default:
        if (!arg.startsWith('-')) {
          options.logFile = arg;
        }
        break;
    }
  }

  return options;
}

function showHelp() {
  console.log(`
${colors.bold}Parse Build Errors${colors.reset}
Parse TypeScript/Build errors from pnpm build log files

${colors.bold}Usage:${colors.reset}
  ./.bin/parse-build-errors.mjs [options] [logfile]

${colors.bold}Options:${colors.reset}
  ${colors.cyan}--summary, -s${colors.reset}         Show summary only (error counts per package)
  ${colors.cyan}--package, -p NAME${colors.reset}    Filter by package name (partial match)
  ${colors.cyan}--type, -t CODE${colors.reset}       Filter by error code (e.g., TS2305, TS6133)
  ${colors.cyan}--json, -j${colors.reset}            Output as JSON array
  ${colors.cyan}--jsonl, -l${colors.reset}           Generate JSONL file (one JSON object per line)
  ${colors.cyan}--output, -o FILE${colors.reset}     Specify output file for JSONL (default: <logfile>.jsonl)
  ${colors.cyan}--dedupe, -d${colors.reset}          Remove duplicate errors (same file, line, code, message)
  ${colors.cyan}--group, -g MODE${colors.reset}      Group output: package, file, code, message (default: package)
  ${colors.cyan}--sort, -S FIELD${colors.reset}      Sort by: count, package, file, code, line (default: count)
  ${colors.cyan}--exclude, -x CODES${colors.reset}   Exclude error codes (comma-separated, e.g., TS6133,TS2305)
  ${colors.cyan}--consolidate, -c${colors.reset}     Consolidate similar messages (group by message pattern)
  ${colors.cyan}--help, -h${colors.reset}            Show help

${colors.bold}Examples:${colors.reset}
  ${colors.dim}# Basic usage${colors.reset}
  ./.bin/parse-build-errors.mjs logs/pnpm-build-error.log

  ${colors.dim}# Summary view${colors.reset}
  ./.bin/parse-build-errors.mjs -s logs/pnpm-build-error.log

  ${colors.dim}# Deduplicate and group by error code${colors.reset}
  ./.bin/parse-build-errors.mjs -d -g code logs/pnpm-build-error.log

  ${colors.dim}# Exclude unused variable warnings${colors.reset}
  ./.bin/parse-build-errors.mjs -x TS6133 logs/pnpm-build-error.log

  ${colors.dim}# Consolidate similar messages, sort by count${colors.reset}
  ./.bin/parse-build-errors.mjs -c -S count logs/pnpm-build-error.log

  ${colors.dim}# Generate deduplicated JSONL${colors.reset}
  ./.bin/parse-build-errors.mjs -l -d logs/pnpm-build-error.log

  ${colors.dim}# Exclude multiple error types${colors.reset}
  ./.bin/parse-build-errors.mjs -x TS6133,TS2305,TS7006 logs/pnpm-build-error.log

${colors.bold}Group Modes:${colors.reset}
  ${colors.yellow}package${colors.reset}  - Group errors by package name (default)
  ${colors.yellow}file${colors.reset}     - Group errors by source file
  ${colors.yellow}code${colors.reset}     - Group errors by error code (TS2305, etc.)
  ${colors.yellow}message${colors.reset}  - Group errors by message pattern

${colors.bold}Sort Fields:${colors.reset}
  ${colors.yellow}count${colors.reset}    - Sort by error count descending (default)
  ${colors.yellow}package${colors.reset}  - Sort alphabetically by package
  ${colors.yellow}file${colors.reset}     - Sort alphabetically by file path
  ${colors.yellow}code${colors.reset}     - Sort by error code
  ${colors.yellow}line${colors.reset}     - Sort by line number

${colors.bold}JSONL Output Format:${colors.reset}
  Each line contains a JSON object with:
  - package: Package name (e.g., "@internal/fastify-task-graph")
  - file: Source file path
  - line: Line number
  - column: Column number
  - code: Error code (e.g., "TS2305")
  - message: Error message
  - type: Error type ("typescript" or "lifecycle")
  - severity: "error"
  - timestamp: ISO timestamp when parsed
  - occurrences: Number of occurrences (when using --dedupe)
`);
}

function parseLogFile(content) {
  const errors = [];
  const lines = content.split('\n');
  const timestamp = new Date().toISOString();

  // Pattern to match TypeScript errors: @internal/package-name: file(line,col): error TSXXXX: message
  const tsErrorPattern = /^(@internal\/[^:]+):\s*([^(]+)\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.+)$/;

  // Pattern for ELIFECYCLE errors
  const lifecyclePattern = /^(@internal\/[^:]+):\s*ELIFECYCLE\s+(.+)$/;

  for (const line of lines) {
    const tsMatch = line.match(tsErrorPattern);
    if (tsMatch) {
      errors.push({
        package: tsMatch[1],
        file: tsMatch[2].trim(),
        line: parseInt(tsMatch[3], 10),
        column: parseInt(tsMatch[4], 10),
        code: tsMatch[5],
        message: tsMatch[6].trim(),
        type: 'typescript',
        severity: 'error',
        timestamp,
      });
      continue;
    }

    const lifecycleMatch = line.match(lifecyclePattern);
    if (lifecycleMatch) {
      errors.push({
        package: lifecycleMatch[1],
        file: null,
        line: null,
        column: null,
        code: 'ELIFECYCLE',
        message: lifecycleMatch[2].trim(),
        type: 'lifecycle',
        severity: 'error',
        timestamp,
      });
    }
  }

  return errors;
}

/**
 * Remove duplicate errors based on file, line, code, and message
 */
function deduplicateErrors(errors) {
  const seen = new Map();

  for (const error of errors) {
    const key = `${error.package}|${error.file}|${error.line}|${error.column}|${error.code}|${error.message}`;

    if (seen.has(key)) {
      const existing = seen.get(key);
      existing.occurrences = (existing.occurrences || 1) + 1;
    } else {
      seen.set(key, { ...error, occurrences: 1 });
    }
  }

  return Array.from(seen.values());
}

/**
 * Consolidate errors by normalizing message patterns
 * (e.g., different variable names but same error type)
 */
function consolidateErrors(errors) {
  const consolidated = new Map();

  for (const error of errors) {
    // Normalize message by replacing specific identifiers with placeholders
    let normalizedMessage = error.message
      // Replace quoted strings
      .replace(/'[^']+'/g, "'<identifier>'")
      // Replace type names in "Type 'X' is not assignable to type 'Y'"
      .replace(/Type '[^']+'/g, "Type '<type>'")
      // Replace module paths
      .replace(/"[^"]+"/g, '"<module>"')
      // Replace numbers
      .replace(/\b\d+\b/g, '<n>');

    const key = `${error.code}|${normalizedMessage}`;

    if (consolidated.has(key)) {
      const existing = consolidated.get(key);
      existing.occurrences = (existing.occurrences || 1) + 1;
      existing.examples = existing.examples || [];
      if (existing.examples.length < 3) {
        existing.examples.push({
          package: error.package,
          file: error.file,
          line: error.line,
          message: error.message,
        });
      }
    } else {
      consolidated.set(key, {
        ...error,
        normalizedMessage,
        occurrences: 1,
        examples: [{
          package: error.package,
          file: error.file,
          line: error.line,
          message: error.message,
        }],
      });
    }
  }

  return Array.from(consolidated.values());
}

/**
 * Sort errors by the specified field
 */
function sortErrors(errors, sortField) {
  const sorted = [...errors];

  switch (sortField) {
    case 'count':
      sorted.sort((a, b) => (b.occurrences || 1) - (a.occurrences || 1));
      break;
    case 'package':
      sorted.sort((a, b) => (a.package || '').localeCompare(b.package || ''));
      break;
    case 'file':
      sorted.sort((a, b) => (a.file || '').localeCompare(b.file || ''));
      break;
    case 'code':
      sorted.sort((a, b) => (a.code || '').localeCompare(b.code || ''));
      break;
    case 'line':
      sorted.sort((a, b) => (a.line || 0) - (b.line || 0));
      break;
    default:
      // Default to count
      sorted.sort((a, b) => (b.occurrences || 1) - (a.occurrences || 1));
  }

  return sorted;
}

/**
 * Group errors by the specified field
 */
function groupErrors(errors, groupBy) {
  const grouped = {};

  for (const error of errors) {
    let key;
    switch (groupBy) {
      case 'package':
        key = error.package || 'unknown';
        break;
      case 'file':
        key = error.file || 'unknown';
        break;
      case 'code':
        key = error.code || 'unknown';
        break;
      case 'message':
        key = error.normalizedMessage || error.message || 'unknown';
        break;
      default:
        key = error.package || 'unknown';
    }

    if (!grouped[key]) {
      grouped[key] = [];
    }
    grouped[key].push(error);
  }

  return grouped;
}

function groupByPackage(errors) {
  return groupErrors(errors, 'package');
}

function groupByErrorCode(errors) {
  return groupErrors(errors, 'code');
}

function filterErrors(errors, options) {
  let filtered = errors;

  // Filter by package
  if (options.package) {
    filtered = filtered.filter(e =>
      e.package.toLowerCase().includes(options.package.toLowerCase())
    );
  }

  // Filter by type (include)
  if (options.type) {
    filtered = filtered.filter(e =>
      e.code && e.code.toUpperCase() === options.type.toUpperCase()
    );
  }

  // Filter by exclude codes
  if (options.exclude && options.exclude.length > 0) {
    filtered = filtered.filter(e =>
      !e.code || !options.exclude.includes(e.code.toUpperCase())
    );
  }

  return filtered;
}

function generateJsonlOutput(errors, logFile, outputFile) {
  // Generate output filename if not specified
  let jsonlPath;
  if (outputFile) {
    jsonlPath = resolve(process.cwd(), outputFile);
  } else {
    const logBasename = basename(logFile, '.log');
    const logDir = dirname(logFile);
    jsonlPath = resolve(process.cwd(), logDir, `${logBasename}.jsonl`);
  }

  // Generate JSONL content (one JSON object per line)
  const jsonlContent = errors.map(err => JSON.stringify(err)).join('\n');

  writeFileSync(jsonlPath, jsonlContent + '\n', 'utf-8');

  return jsonlPath;
}

function printSummary(errors, options) {
  const byPackage = groupByPackage(errors);
  const byCode = groupByErrorCode(errors);

  // Calculate total considering occurrences
  const totalErrors = errors.reduce((sum, e) => sum + (e.occurrences || 1), 0);
  const uniqueErrors = errors.length;

  if (options.json) {
    const summary = {
      totalErrors,
      uniqueErrors: options.dedupe || options.consolidate ? uniqueErrors : undefined,
      byPackage: Object.fromEntries(
        Object.entries(byPackage).map(([pkg, errs]) => [
          pkg,
          errs.reduce((sum, e) => sum + (e.occurrences || 1), 0)
        ])
      ),
      byErrorCode: Object.fromEntries(
        Object.entries(byCode).map(([code, errs]) => [
          code,
          errs.reduce((sum, e) => sum + (e.occurrences || 1), 0)
        ])
      ),
    };
    console.log(JSON.stringify(summary, null, 2));
    return;
  }

  console.log(`\n${colors.bold}${colors.red}Build Error Summary${colors.reset}\n`);
  console.log(`${colors.bold}Total Errors:${colors.reset} ${colors.red}${totalErrors}${colors.reset}`);
  if (options.dedupe || options.consolidate) {
    console.log(`${colors.bold}Unique Errors:${colors.reset} ${colors.yellow}${uniqueErrors}${colors.reset}`);
  }
  if (options.exclude.length > 0) {
    console.log(`${colors.dim}Excluded: ${options.exclude.join(', ')}${colors.reset}`);
  }
  console.log();

  // By package
  console.log(`${colors.bold}${colors.cyan}Errors by Package:${colors.reset}`);
  const sortedPackages = Object.entries(byPackage)
    .map(([pkg, errs]) => [pkg, errs.reduce((sum, e) => sum + (e.occurrences || 1), 0)])
    .sort((a, b) => b[1] - a[1]);

  for (const [pkg, count] of sortedPackages) {
    const bar = '█'.repeat(Math.min(50, Math.ceil(count / 5)));
    console.log(`  ${colors.yellow}${pkg}${colors.reset}`);
    console.log(`    ${colors.red}${bar}${colors.reset} ${count}`);
  }

  // By error code
  console.log(`\n${colors.bold}${colors.cyan}Errors by Type:${colors.reset}`);
  const sortedCodes = Object.entries(byCode)
    .map(([code, errs]) => [code, errs.reduce((sum, e) => sum + (e.occurrences || 1), 0)])
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15);

  for (const [code, count] of sortedCodes) {
    const bar = '█'.repeat(Math.min(30, Math.ceil(count / 3)));
    console.log(`  ${colors.magenta}${code}${colors.reset}: ${colors.red}${bar}${colors.reset} ${count}`);
  }

  if (Object.keys(byCode).length > 15) {
    console.log(`  ${colors.dim}... and ${Object.keys(byCode).length - 15} more error types${colors.reset}`);
  }
}

function printErrors(errors, options) {
  if (options.json) {
    console.log(JSON.stringify(errors, null, 2));
    return;
  }

  const grouped = groupErrors(errors, options.group);

  // Sort group entries
  let sortedGroups;
  if (options.sort === 'count') {
    sortedGroups = Object.entries(grouped)
      .sort((a, b) => {
        const countA = a[1].reduce((sum, e) => sum + (e.occurrences || 1), 0);
        const countB = b[1].reduce((sum, e) => sum + (e.occurrences || 1), 0);
        return countB - countA;
      });
  } else {
    sortedGroups = Object.entries(grouped)
      .sort((a, b) => a[0].localeCompare(b[0]));
  }

  for (const [groupKey, groupErrors] of sortedGroups) {
    const totalCount = groupErrors.reduce((sum, e) => sum + (e.occurrences || 1), 0);
    const uniqueCount = groupErrors.length;

    const countDisplay = options.dedupe || options.consolidate
      ? `${totalCount} total, ${uniqueCount} unique`
      : `${totalCount} errors`;

    console.log(`\n${colors.bold}${colors.cyan}${groupKey}${colors.reset} (${countDisplay})`);
    console.log('─'.repeat(60));

    // Sort errors within group
    const sortedErrors = sortErrors(groupErrors, options.sort);

    if (options.consolidate) {
      // Show consolidated view with examples
      for (const err of sortedErrors) {
        const occStr = err.occurrences > 1 ? ` ${colors.yellow}(×${err.occurrences})${colors.reset}` : '';
        console.log(`\n  ${colors.red}${err.code}${colors.reset}${occStr}: ${err.normalizedMessage || err.message}`);

        if (err.examples && err.examples.length > 0) {
          console.log(`  ${colors.dim}Examples:${colors.reset}`);
          for (const ex of err.examples) {
            console.log(`    ${colors.dim}${ex.file}:${ex.line}${colors.reset}`);
            console.log(`      ${ex.message}`);
          }
        }
      }
    } else if (options.group === 'code' || options.group === 'message') {
      // For code/message grouping, show file locations
      for (const err of sortedErrors) {
        const occStr = err.occurrences > 1 ? ` ${colors.yellow}(×${err.occurrences})${colors.reset}` : '';
        if (err.type === 'typescript') {
          console.log(`  ${colors.dim}${err.package}${colors.reset} ${err.file}:${err.line}:${err.column}${occStr}`);
          console.log(`    ${err.message}`);
        } else {
          console.log(`  ${colors.dim}${err.package}${colors.reset}${occStr}: ${err.message}`);
        }
      }
    } else {
      // Default package/file grouping
      const byFile = {};
      for (const err of sortedErrors) {
        const key = err.file || 'unknown';
        if (!byFile[key]) {
          byFile[key] = [];
        }
        byFile[key].push(err);
      }

      for (const [file, fileErrors] of Object.entries(byFile)) {
        console.log(`\n  ${colors.yellow}${file}${colors.reset}`);

        for (const err of fileErrors) {
          const occStr = err.occurrences > 1 ? ` ${colors.yellow}(×${err.occurrences})${colors.reset}` : '';
          if (err.type === 'typescript') {
            console.log(`    ${colors.dim}${err.line}:${err.column}${colors.reset} ${colors.red}${err.code}${colors.reset}${occStr}: ${err.message}`);
          } else {
            console.log(`    ${colors.red}${err.message}${colors.reset}${occStr}`);
          }
        }
      }
    }
  }
}

function main() {
  try {
    const args = process.argv.slice(2);
    const options = parseArgs(args);

    if (options.help) {
      showHelp();
      process.exit(0);
    }

    // Default log file
    const logFile = options.logFile || 'logs/pnpm-build-error.log';
    const resolvedPath = resolve(process.cwd(), logFile);

    if (!existsSync(resolvedPath)) {
      console.error(`${colors.red}Error: Log file not found: ${resolvedPath}${colors.reset}`);
      console.error(`\nRun ${colors.cyan}pnpm run build:logerror${colors.reset} first to generate the log file.`);
      process.exit(1);
    }

    let content;
    try {
      content = readFileSync(resolvedPath, 'utf-8');
    } catch (readErr) {
      console.error(`${colors.red}Error reading file: ${readErr.message}${colors.reset}`);
      process.exit(1);
    }

    let errors = parseLogFile(content);

    if (errors.length === 0) {
      console.log(`${colors.green}No build errors found!${colors.reset}`);
      process.exit(0);
    }

    // Apply filters (including exclusions)
    errors = filterErrors(errors, options);

    if (errors.length === 0) {
      console.log(`${colors.yellow}No errors matching the filter criteria.${colors.reset}`);
      process.exit(0);
    }

    // Apply deduplication
    if (options.dedupe) {
      const beforeCount = errors.length;
      errors = deduplicateErrors(errors);
      const afterCount = errors.length;
      if (!options.json && !options.jsonl) {
        console.log(`${colors.dim}Deduplicated: ${beforeCount} → ${afterCount} unique errors${colors.reset}`);
      }
    }

    // Apply consolidation
    if (options.consolidate) {
      const beforeCount = errors.length;
      errors = consolidateErrors(errors);
      const afterCount = errors.length;
      if (!options.json && !options.jsonl) {
        console.log(`${colors.dim}Consolidated: ${beforeCount} → ${afterCount} patterns${colors.reset}`);
      }
    }

    // Apply sorting
    errors = sortErrors(errors, options.sort);

    // Generate JSONL file if requested
    if (options.jsonl) {
      try {
        const jsonlPath = generateJsonlOutput(errors, logFile, options.output);
        const totalCount = errors.reduce((sum, e) => sum + (e.occurrences || 1), 0);
        console.log(`${colors.green}Generated JSONL file:${colors.reset} ${jsonlPath}`);
        console.log(`${colors.dim}Total errors: ${totalCount}${options.dedupe || options.consolidate ? ` (${errors.length} unique)` : ''}${colors.reset}`);
      } catch (writeErr) {
        console.error(`${colors.red}Error writing JSONL file: ${writeErr.message}${colors.reset}`);
        process.exit(1);
      }
      process.exit(0);
    }

    if (options.summary) {
      printSummary(errors, options);
    } else {
      printErrors(errors, options);
    }
  } catch (err) {
    console.error(`${colors.red}Unexpected error: ${err.message}${colors.reset}`);
    if (process.env.DEBUG) {
      console.error(err.stack);
    }
    process.exit(1);
  }
}

main();
