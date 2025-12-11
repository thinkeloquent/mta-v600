/**
 * @internal/console-print - Console printing utilities with optional color support.
 *
 * A unified console output library that provides colored output when picocolors is
 * available, with automatic fallback to plain text. Mirrors the Python console_print
 * package API for cross-language consistency.
 *
 * ============================================================================
 * INSTALLATION
 * ============================================================================
 *
 * This is an internal package. Add to your package.json:
 *
 *   "peerDependencies": {
 *     "@internal/console-print": "workspace:*"
 *   }
 *
 * ============================================================================
 * QUICK START
 * ============================================================================
 *
 *   import {
 *     printSection, printJson, printInfo, printSuccess, printError,
 *     printWarning, printDebug, maskSensitive, maskUrl, hasColors
 *   } from '@internal/console-print';
 *
 *   // Section headers for step-by-step debugging
 *   printSection('1. LOADING CONFIGURATION');
 *
 *   // JSON output with optional title
 *   printJson({ host: 'localhost', port: 6379 }, 'Redis Config');
 *
 *   // Status messages with provider/component title
 *   printInfo('Connecting...', 'Redis');
 *   printSuccess('Connected', 'Redis');
 *   printWarning('High latency detected', 'Redis');
 *   printError('Connection failed', 'Redis');
 *
 *   // Mask sensitive data before logging
 *   console.log(`Token: ${maskSensitive('ghp_abc123xyz789')}`);  // "ghp_***"
 *
 * ============================================================================
 * API REFERENCE
 * ============================================================================
 *
 * SECTION & RULE PRINTING
 * -----------------------
 *
 *   printSection(title, options?)
 *     Print a prominent section header with === lines.
 *     Options: { width: 60, char: '=' }
 *
 *     printSection('1. YAML CONFIG LOADING');
 *     // Output:
 *     // ============================================================
 *     // Step: 1. YAML CONFIG LOADING
 *     // ============================================================
 *
 *   printRule(title?, options?)
 *     Print a horizontal rule, optionally with centered title.
 *     Options: { width: 60, char: '-' }
 *
 *     printRule();           // ------------------------------------------------------------
 *     printRule('Details');  // ------------------------- Details --------------------------
 *
 * JSON PRINTING
 * -------------
 *
 *   printJson(data, optionsOrTitle?)
 *     Print JSON with syntax highlighting (when colors available).
 *     Second arg: string (title shorthand) OR { title?, indent? }
 *
 *     // Title as string shorthand
 *     printJson({ host: 'localhost' }, 'Connection Config');
 *     // Output:
 *     // [Connection Config]
 *     // { "host": "localhost" }
 *
 *     // Title in options object
 *     printJson(data, { title: 'Provider Config', indent: 4 });
 *
 *     // No title
 *     printJson({ status: 'ok' });
 *
 * STATUS MESSAGES
 * ---------------
 *
 * All status functions accept: (message, optionsOrTitle?)
 * Second arg: string (title shorthand) OR { title: string }
 *
 *   printInfo(message, title?)     - Blue [INFO] or [INFO:title]
 *   printSuccess(message, title?)  - Green [OK] or [OK:title]
 *   printWarning(message, title?)  - Yellow [WARN] or [WARN:title]
 *   printError(message, title?)    - Red [ERROR] or [ERROR:title]
 *   printDebug(message, title?)    - Dim [DEBUG] or [DEBUG:title]
 *
 *   // Without title
 *   printInfo('Starting server...');
 *   // Output: [INFO] Starting server...
 *
 *   // With title as string
 *   printSuccess('Health check passed', 'GitHub');
 *   // Output: [OK:GitHub] Health check passed
 *
 *   // With title in options
 *   printError('Connection timeout', { title: 'Database' });
 *   // Output: [ERROR:Database] Connection timeout
 *
 * SENSITIVE DATA MASKING
 * ----------------------
 *
 *   maskSensitive(value, options?)
 *     Mask sensitive values for safe logging.
 *     Options: { showChars: 4, maskChar: '*', placeholder: '<none>' }
 *
 *     maskSensitive('secretpassword123');     // "secr***"
 *     maskSensitive('abc');                   // "***" (short values fully masked)
 *     maskSensitive(null);                    // "<none>"
 *     maskSensitive('token', { showChars: 2 }); // "to***"
 *
 *   maskUrl(url)
 *     Mask passwords and sensitive query params in URLs.
 *
 *     maskUrl('redis://user:secret@localhost:6379');
 *     // "redis://user:****@localhost:6379"
 *
 *     maskUrl('https://api.example.com?key=abc123&other=value');
 *     // "https://api.example.com?key=****&other=value"
 *
 * DATA DISPLAY
 * ------------
 *
 *   printTable(data, optionsOrTitle?)
 *     Print array of objects as formatted table.
 *     Options: { title?, columns? }
 *
 *     printTable([
 *       { name: 'Redis', status: 'connected' },
 *       { name: 'Postgres', status: 'connected' }
 *     ], 'Service Status');
 *
 *   printPanel(content, optionsOrTitle?)
 *     Print content in a bordered box.
 *     Options: { title?, width? }
 *
 *     printPanel('Important message here', 'Notice');
 *
 *   printKeyValue(label, value, options?)
 *     Print a single key: value pair with indentation.
 *     Options: { indent: 2 }
 *
 *     printKeyValue('Host', 'localhost');     // "  Host: localhost"
 *     printKeyValue('Port', 6379, { indent: 4 }); // "    Port: 6379"
 *
 *   printKeyValues(obj, options?)
 *     Print multiple key-value pairs from an object.
 *
 *     printKeyValues({ host: 'localhost', port: 6379, db: 0 });
 *     // "  host: localhost"
 *     // "  port: 6379"
 *     // "  db: 0"
 *
 * UTILITIES
 * ---------
 *
 *   hasColors()
 *     Returns true if picocolors is available for colored output.
 *
 *     if (hasColors()) {
 *       console.log('Terminal supports colors');
 *     }
 *
 * ============================================================================
 * HEALTH CHECK PATTERN (Recommended Usage)
 * ============================================================================
 *
 * This library is designed for the explicit 7-step health check pattern:
 *
 *   import { printSection, printJson, maskSensitive, printInfo, printSuccess, printError } from '@internal/console-print';
 *
 *   async function checkGithubHealth(config) {
 *     // Step 1: YAML CONFIG
 *     printSection('1. YAML CONFIG LOADING');
 *     printInfo(`Loaded from: ${config._source}`, 'Config');
 *
 *     // Step 2: PROVIDER CONFIG
 *     printSection('2. PROVIDER CONFIG');
 *     printJson({
 *       providerName: 'github',
 *       baseUrl: 'https://api.github.com',
 *       healthEndpoint: '/user'
 *     }, 'Provider Config');
 *
 *     // Step 3: PROXY CONFIG
 *     printSection('3. PROXY CONFIG');
 *     printJson({ proxyUrl: null, certVerify: true }, 'Network Config');
 *
 *     // Step 4: AUTH CONFIG
 *     printSection('4. AUTH CONFIG');
 *     printInfo(`Auth type: bearer`, 'Auth');
 *     printInfo(`Token: ${maskSensitive(token)}`, 'Auth');
 *
 *     // Step 5: REQUEST CONFIG
 *     printSection('5. REQUEST CONFIG');
 *     printJson({ method: 'GET', url: 'https://api.github.com/user' }, 'Request');
 *
 *     // Step 6: FETCH
 *     printSection('6. FETCH');
 *     const response = await fetch(url, options);
 *
 *     // Step 7: RESPONSE
 *     printSection('7. RESPONSE');
 *     if (response.ok) {
 *       printSuccess(`Connected as @${data.login}`, 'GitHub');
 *     } else {
 *       printError(`HTTP ${response.status}`, 'GitHub');
 *     }
 *   }
 *
 * ============================================================================
 * LLM INTEGRATION INSTRUCTIONS
 * ============================================================================
 *
 * When generating code that uses this library:
 *
 * 1. IMPORT: Always import from '@internal/console-print'
 *    ```javascript
 *    import { printSection, printJson, printInfo, printSuccess, printError, maskSensitive } from '@internal/console-print';
 *    ```
 *
 * 2. SECTIONS: Use printSection() to mark major steps in a process
 *    ```javascript
 *    printSection('1. LOADING CONFIG');
 *    printSection('2. CONNECTING');
 *    printSection('3. EXECUTING QUERY');
 *    ```
 *
 * 3. STATUS WITH CONTEXT: Always include the component/provider name as title
 *    ```javascript
 *    printInfo('Connecting...', 'Redis');      // NOT: printInfo('Redis: Connecting...')
 *    printSuccess('Connected', 'PostgreSQL');  // NOT: printSuccess('PostgreSQL connected')
 *    printError('Timeout', 'Elasticsearch');   // NOT: printError('Elasticsearch timeout')
 *    ```
 *
 * 4. JSON WITH TITLES: Label JSON blocks for clarity
 *    ```javascript
 *    printJson(config, 'Provider Config');     // NOT: printJson(config)
 *    printJson(response, 'API Response');      // NOT: console.log(JSON.stringify(response))
 *    ```
 *
 * 5. MASK SENSITIVE DATA: Never log raw credentials
 *    ```javascript
 *    printInfo(`Token: ${maskSensitive(token)}`, 'Auth');  // NOT: printInfo(`Token: ${token}`)
 *    printInfo(`URL: ${maskUrl(connectionString)}`, 'DB'); // NOT: printInfo(connectionString)
 *    ```
 *
 * 6. PYTHON EQUIVALENT: The Python package has snake_case equivalents
 *    ```
 *    JavaScript              Python
 *    -----------             ------
 *    printSection()    ->    print_section()
 *    printJson()       ->    print_json()
 *    printInfo()       ->    print_info()
 *    printSuccess()    ->    print_success()
 *    printError()      ->    print_error()
 *    maskSensitive()   ->    mask_sensitive()
 *    maskUrl()         ->    mask_url()
 *    hasColors()       ->    has_colors()
 *    ```
 *
 * ============================================================================
 * PACKAGE STRUCTURE
 * ============================================================================
 *
 *   packages_mjs/console-print/
 *   ├── package.json          # Package configuration
 *   ├── src/
 *   │   ├── index.mjs         # Main exports (this file)
 *   │   └── printer.mjs       # Core implementation
 *   └── tests/
 *       └── printer.test.mjs  # Jest tests
 *
 * ============================================================================
 * CROSS-LANGUAGE COMPATIBILITY
 * ============================================================================
 *
 * This package mirrors packages_py/console_print for consistent APIs across
 * JavaScript and Python codebases. Both packages:
 *
 * - Support the same function signatures
 * - Accept string shorthand OR options object for second argument
 * - Use the same output formats ([INFO:title], [OK:title], etc.)
 * - Gracefully degrade when color libraries are unavailable
 *
 */

export {
  // Core utilities
  hasColors,
  printSection,
  printRule,
  printJson,

  // Sensitive data masking
  maskSensitive,
  maskUrl,

  // Status messages
  printInfo,
  printSuccess,
  printWarning,
  printError,
  printDebug,

  // Data display
  printTable,
  printPanel,
  printKeyValue,
  printKeyValues,
} from "./printer.mjs";

export const VERSION = "1.0.0";
