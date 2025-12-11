/**
 * Console printer with optional picocolors support.
 *
 * Provides a unified interface for console output that works with or without colors.
 * When picocolors is not installed, falls back to standard console output.
 */

// Try to import picocolors for colored output
let pc;
let HAS_COLORS = false;

try {
  pc = (await import('picocolors')).default;
  HAS_COLORS = true;
} catch {
  HAS_COLORS = false;
  pc = null;
}

/**
 * Check if colors are available.
 * @returns {boolean} True if picocolors is available
 */
export function hasColors() {
  return HAS_COLORS;
}

// =============================================================================
// Section and Rule Printing
// =============================================================================

/**
 * Print a section header with a title.
 * @param {string} title - Section title
 * @param {Object} [options] - Options
 * @param {number} [options.width=60] - Width of the section line
 * @param {string} [options.char='='] - Character to use for the line
 */
export function printSection(title, options = {}) {
  const { width = 60, char = '=' } = options;
  const line = char.repeat(width);

  console.log(`\n${line}`);
  if (HAS_COLORS) {
    console.log(pc.bold(pc.cyan(`Step: ${title}`)));
  } else {
    console.log(`Step: ${title}`);
  }
  console.log(line);
}

/**
 * Print a horizontal rule.
 * @param {string} [title] - Optional title in the rule
 * @param {Object} [options] - Options
 * @param {number} [options.width=60] - Width of the rule
 * @param {string} [options.char='-'] - Character to use for the rule
 */
export function printRule(title = '', options = {}) {
  const { width = 60, char = '-' } = options;

  if (title) {
    const padding = Math.max(0, (width - title.length - 2) / 2);
    const leftPad = char.repeat(Math.floor(padding));
    const rightPad = char.repeat(Math.ceil(padding));
    console.log(`${leftPad} ${title} ${rightPad}`);
  } else {
    console.log(char.repeat(width));
  }
}

// =============================================================================
// Helper to normalize options
// =============================================================================

/**
 * Normalize options argument - supports string shorthand for title.
 * @param {string|Object} optionsOrTitle - Options object or title string
 * @param {string} [titleKey='title'] - Key name for title in options
 * @returns {Object} Normalized options object
 */
function normalizeOptions(optionsOrTitle, titleKey = 'title') {
  if (typeof optionsOrTitle === 'string') {
    return { [titleKey]: optionsOrTitle };
  }
  return optionsOrTitle || {};
}

// =============================================================================
// JSON Printing
// =============================================================================

/**
 * Print JSON data with indentation.
 * @param {Object|Array|string} data - Data to print as JSON
 * @param {string|Object} [optionsOrTitle] - Title string or options object
 * @param {string} [optionsOrTitle.title] - Title to print before JSON
 * @param {number} [optionsOrTitle.indent=2] - Indentation spaces
 */
export function printJson(data, optionsOrTitle) {
  const options = normalizeOptions(optionsOrTitle);
  const { title, indent = 2 } = options;

  // Print title if provided
  if (title) {
    if (HAS_COLORS) {
      console.log(pc.dim(`[${title}]`));
    } else {
      console.log(`[${title}]`);
    }
  }

  let jsonStr;
  if (typeof data === 'string') {
    jsonStr = data;
  } else {
    jsonStr = JSON.stringify(data, null, indent);
  }

  if (HAS_COLORS) {
    // Simple syntax highlighting for JSON
    const highlighted = jsonStr
      .replace(/"([^"]+)":/g, (_, key) => `${pc.cyan(`"${key}"`)}:`)
      .replace(/: "([^"]*)"/g, (_, val) => `: ${pc.green(`"${val}"`)}`)
      .replace(/: (\d+)/g, (_, num) => `: ${pc.yellow(num)}`)
      .replace(/: (true|false)/g, (_, bool) => `: ${pc.magenta(bool)}`)
      .replace(/: (null)/g, (_, n) => `: ${pc.dim(n)}`);
    console.log(highlighted);
  } else {
    console.log(jsonStr);
  }
}

// =============================================================================
// Sensitive Data Masking
// =============================================================================

/**
 * Mask sensitive values for logging.
 * @param {string} value - Value to mask
 * @param {Object} [options] - Options
 * @param {number} [options.showChars=4] - Number of characters to show before masking
 * @param {string} [options.maskChar='*'] - Character to use for masking
 * @param {string} [options.placeholder='<none>'] - Placeholder for null/empty values
 * @returns {string} Masked value
 */
export function maskSensitive(value, options = {}) {
  const { showChars = 4, maskChar = '*', placeholder = '<none>' } = options;

  if (!value) return placeholder;
  if (value.length <= showChars) return maskChar.repeat(value.length);
  return value.substring(0, showChars) + '***';
}

/**
 * Mask a URL by hiding password and sensitive query parameters.
 * @param {string} url - URL to mask
 * @returns {string} Masked URL
 */
export function maskUrl(url) {
  if (!url) return '<none>';

  try {
    const parsed = new URL(url);

    // Mask password in auth
    if (parsed.password) {
      parsed.password = '****';
    }

    // Mask sensitive query parameters
    const sensitiveParams = ['key', 'token', 'secret', 'password', 'apikey', 'api_key', 'auth'];
    for (const param of sensitiveParams) {
      if (parsed.searchParams.has(param)) {
        parsed.searchParams.set(param, '****');
      }
    }

    return parsed.toString();
  } catch {
    // If URL parsing fails, use regex fallback
    return url
      .replace(/(\/\/[^:]+:)[^@]+(@)/, '$1****$2')
      .replace(/([?&](key|token|secret|password|apikey|api_key|auth)=)[^&]+/gi, '$1****');
  }
}

// =============================================================================
// Status Messages
// =============================================================================

/**
 * Print an info message.
 * @param {string} message - Message to print
 * @param {string|Object} [optionsOrTitle] - Title string or options object
 * @param {string} [optionsOrTitle.title] - Title/label to show after [INFO]
 */
export function printInfo(message, optionsOrTitle) {
  const options = normalizeOptions(optionsOrTitle);
  const { title } = options;
  const label = title ? `[INFO:${title}]` : '[INFO]';

  if (HAS_COLORS) {
    console.log(`${pc.blue(label)} ${message}`);
  } else {
    console.log(`${label} ${message}`);
  }
}

/**
 * Print a success message.
 * @param {string} message - Message to print
 * @param {string|Object} [optionsOrTitle] - Title string or options object
 * @param {string} [optionsOrTitle.title] - Title/label to show after [OK]
 */
export function printSuccess(message, optionsOrTitle) {
  const options = normalizeOptions(optionsOrTitle);
  const { title } = options;
  const label = title ? `[OK:${title}]` : '[OK]';

  if (HAS_COLORS) {
    console.log(`${pc.green(label)} ${message}`);
  } else {
    console.log(`${label} ${message}`);
  }
}

/**
 * Print a warning message.
 * @param {string} message - Message to print
 * @param {string|Object} [optionsOrTitle] - Title string or options object
 * @param {string} [optionsOrTitle.title] - Title/label to show after [WARN]
 */
export function printWarning(message, optionsOrTitle) {
  const options = normalizeOptions(optionsOrTitle);
  const { title } = options;
  const label = title ? `[WARN:${title}]` : '[WARN]';

  if (HAS_COLORS) {
    console.log(`${pc.yellow(label)} ${message}`);
  } else {
    console.log(`${label} ${message}`);
  }
}

/**
 * Print an error message.
 * @param {string} message - Message to print
 * @param {string|Object} [optionsOrTitle] - Title string or options object
 * @param {string} [optionsOrTitle.title] - Title/label to show after [ERROR]
 */
export function printError(message, optionsOrTitle) {
  const options = normalizeOptions(optionsOrTitle);
  const { title } = options;
  const label = title ? `[ERROR:${title}]` : '[ERROR]';

  if (HAS_COLORS) {
    console.log(`${pc.red(label)} ${message}`);
  } else {
    console.log(`${label} ${message}`);
  }
}

/**
 * Print a debug message.
 * @param {string} message - Message to print
 * @param {string|Object} [optionsOrTitle] - Title string or options object
 * @param {string} [optionsOrTitle.title] - Title/label to show after [DEBUG]
 */
export function printDebug(message, optionsOrTitle) {
  const options = normalizeOptions(optionsOrTitle);
  const { title } = options;
  const label = title ? `[DEBUG:${title}]` : '[DEBUG]';

  if (HAS_COLORS) {
    console.log(`${pc.dim(label)} ${pc.dim(message)}`);
  } else {
    console.log(`${label} ${message}`);
  }
}

// =============================================================================
// Table Printing
// =============================================================================

/**
 * Print data as a simple table.
 * @param {Array<Object>} data - Array of objects to print
 * @param {Object} [options] - Options
 * @param {string} [options.title] - Table title
 * @param {Array<string>} [options.columns] - Column names (defaults to keys from first row)
 */
export function printTable(data, options = {}) {
  const { title, columns } = options;

  if (!data || data.length === 0) {
    console.log('(empty table)');
    return;
  }

  // Determine columns
  const cols = columns || Object.keys(data[0]);

  // Calculate column widths
  const widths = {};
  for (const col of cols) {
    widths[col] = col.length;
    for (const row of data) {
      const val = String(row[col] ?? '');
      widths[col] = Math.max(widths[col], val.length);
    }
  }

  // Print title
  if (title) {
    console.log(`\n${title}`);
    console.log('='.repeat(title.length));
  }

  // Print header
  const header = cols.map((col) => col.padEnd(widths[col])).join(' | ');
  console.log(header);
  console.log('-'.repeat(header.length));

  // Print rows
  for (const row of data) {
    const line = cols.map((col) => String(row[col] ?? '').padEnd(widths[col])).join(' | ');
    console.log(line);
  }

  console.log('');
}

// =============================================================================
// Panel Printing
// =============================================================================

/**
 * Print content in a simple box/panel.
 * @param {string} content - Content to print
 * @param {Object} [options] - Options
 * @param {string} [options.title] - Panel title
 * @param {number} [options.width=60] - Panel width
 */
export function printPanel(content, options = {}) {
  const { title, width = 60 } = options;

  const border = '+' + '-'.repeat(width - 2) + '+';

  console.log(border);
  if (title) {
    const centered = title.length < width - 4 ? title.padStart((width - 2 + title.length) / 2).padEnd(width - 4) : title.substring(0, width - 4);
    console.log(`| ${centered} |`);
    console.log('|' + '-'.repeat(width - 2) + '|');
  }

  for (const line of content.split('\n')) {
    const truncated = line.length <= width - 4 ? line : line.substring(0, width - 7) + '...';
    console.log(`| ${truncated.padEnd(width - 4)} |`);
  }

  console.log(border);
}

// =============================================================================
// Key-Value Printing
// =============================================================================

/**
 * Print a labeled value (key: value format).
 * @param {string} label - Label/key
 * @param {*} value - Value to print
 * @param {Object} [options] - Options
 * @param {number} [options.indent=2] - Indentation spaces
 */
export function printKeyValue(label, value, options = {}) {
  const { indent = 2 } = options;
  const spaces = ' '.repeat(indent);

  if (HAS_COLORS) {
    console.log(`${spaces}${pc.cyan(label)}: ${value}`);
  } else {
    console.log(`${spaces}${label}: ${value}`);
  }
}

/**
 * Print multiple key-value pairs.
 * @param {Object} obj - Object with key-value pairs
 * @param {Object} [options] - Options
 * @param {number} [options.indent=2] - Indentation spaces
 */
export function printKeyValues(obj, options = {}) {
  for (const [key, value] of Object.entries(obj)) {
    printKeyValue(key, value, options);
  }
}
