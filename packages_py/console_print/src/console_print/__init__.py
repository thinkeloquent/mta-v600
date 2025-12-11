"""
console_print - Console printing utilities with optional Rich support.

A unified console output library that provides colored output when Rich is
available, with automatic fallback to plain text. Mirrors the JavaScript
@internal/console-print package API for cross-language consistency.

============================================================================
INSTALLATION
============================================================================

    pip install console-print

Or add to pyproject.toml:

    [tool.poetry.dependencies]
    console-print = { path = "../packages_py/console_print", develop = true }

============================================================================
QUICK START
============================================================================

    from console_print import (
        print_section, print_json, print_info, print_success, print_error,
        print_warning, print_debug, mask_sensitive, mask_url, has_colors
    )

    # Section headers for step-by-step debugging
    print_section('1. LOADING CONFIGURATION')

    # JSON output with optional title
    print_json({'host': 'localhost', 'port': 6379}, 'Redis Config')

    # Status messages with provider/component title
    print_info('Connecting...', 'Redis')
    print_success('Connected', 'Redis')
    print_warning('High latency detected', 'Redis')
    print_error('Connection failed', 'Redis')

    # Mask sensitive data before logging
    print(f"Token: {mask_sensitive('ghp_abc123xyz789')}")  # "ghp_***"

============================================================================
API REFERENCE
============================================================================

SECTION & RULE PRINTING
-----------------------

    print_section(title, options_or_title=None)
        Print a prominent section header with === lines.
        Options: {'width': 60, 'char': '='}

        print_section('1. YAML CONFIG LOADING')
        # Output:
        # ============================================================
        # Step: 1. YAML CONFIG LOADING
        # ============================================================

    print_rule(title='', options_or_title=None)
        Print a horizontal rule, optionally with centered title.
        Options: {'width': 60, 'char': '-'}

        print_rule()           # ------------------------------------------------------------
        print_rule('Details')  # ------------------------- Details --------------------------

JSON PRINTING
-------------

    print_json(data, options_or_title=None)
        Print JSON with syntax highlighting (when Rich available).
        Second arg: string (title shorthand) OR {'title': ..., 'indent': ...}

        # Title as string shorthand
        print_json({'host': 'localhost'}, 'Connection Config')
        # Output:
        # [Connection Config]
        # { "host": "localhost" }

        # Title in options dict
        print_json(data, {'title': 'Provider Config', 'indent': 4})

        # No title
        print_json({'status': 'ok'})

STATUS MESSAGES
---------------

All status functions accept: (message, options_or_title=None)
Second arg: string (title shorthand) OR {'title': string}

    print_info(message, title=None)     - Blue [INFO] or [INFO:title]
    print_success(message, title=None)  - Green [OK] or [OK:title]
    print_warning(message, title=None)  - Yellow [WARN] or [WARN:title]
    print_error(message, title=None)    - Red [ERROR] or [ERROR:title]
    print_debug(message, title=None)    - Dim [DEBUG] or [DEBUG:title]

    # Without title
    print_info('Starting server...')
    # Output: [INFO] Starting server...

    # With title as string
    print_success('Health check passed', 'GitHub')
    # Output: [OK:GitHub] Health check passed

    # With title in options dict
    print_error('Connection timeout', {'title': 'Database'})
    # Output: [ERROR:Database] Connection timeout

SENSITIVE DATA MASKING
----------------------

    mask_sensitive(value, options_or_show_chars=None)
        Mask sensitive values for safe logging.
        Second arg: int (show_chars shorthand) OR dict options
        Options: {'show_chars': 4, 'mask_char': '*', 'placeholder': '<none>'}

        mask_sensitive('secretpassword123')      # "secr***"
        mask_sensitive('abc')                    # "***" (short values fully masked)
        mask_sensitive(None)                     # "<none>"
        mask_sensitive('token', 2)               # "to***" (int shorthand)
        mask_sensitive('token', {'show_chars': 2})  # "to***"

    mask_url(url)
        Mask passwords and sensitive query params in URLs.

        mask_url('redis://user:secret@localhost:6379')
        # "redis://user:****@localhost:6379"

        mask_url('https://api.example.com?key=abc123&other=value')
        # "https://api.example.com?key=****&other=value"

DATA DISPLAY
------------

    print_table(data, options_or_title=None)
        Print list of dicts as formatted table.
        Options: {'title': ..., 'columns': [...]}

        print_table([
            {'name': 'Redis', 'status': 'connected'},
            {'name': 'Postgres', 'status': 'connected'}
        ], 'Service Status')

    print_panel(content, options_or_title=None)
        Print content in a bordered box.
        Options: {'title': ..., 'width': 60}

        print_panel('Important message here', 'Notice')

    print_syntax_panel(code, lexer='python', title=None, theme='monokai', ...)
        Print syntax-highlighted code in a bordered panel.
        Args: code, lexer, title, theme, line_numbers, expand, width

        print_syntax_panel('{"key": "value"}', lexer='json', title='Response')
        print_syntax_panel(yaml_content, lexer='yaml', title='Config')

    print_key_value(label, value, options_or_indent=None)
        Print a single key: value pair with indentation.
        Second arg: int (indent shorthand) OR {'indent': int}

        print_key_value('Host', 'localhost')      # "  Host: localhost"
        print_key_value('Port', 6379, 4)          # "    Port: 6379"

    print_key_values(obj, options_or_indent=None)
        Print multiple key-value pairs from a dict.

        print_key_values({'host': 'localhost', 'port': 6379, 'db': 0})
        # "  host: localhost"
        # "  port: 6379"
        # "  db: 0"

UTILITIES
---------

    has_colors()
        Returns True if Rich is available for colored output.

        if has_colors():
            print('Terminal supports colors')

    HAS_RICH
        Boolean constant indicating if Rich is installed.

CONSOLE CLASS (Advanced)
------------------------

    console
        Global Console instance for direct use.

        console.print('Hello [bold]world[/bold]')  # Rich markup when available

    get_console(stderr=False, quiet=False, **kwargs)
        Create a new Console instance.

        err_console = get_console(stderr=True)
        quiet_console = get_console(quiet=True)

============================================================================
HEALTH CHECK PATTERN (Recommended Usage)
============================================================================

This library is designed for the explicit 7-step health check pattern:

    from console_print import (
        print_section, print_json, mask_sensitive,
        print_info, print_success, print_error
    )

    async def check_github_health(config: dict = None):
        # Step 1: YAML CONFIG
        print_section('1. YAML CONFIG LOADING')
        print_info(f"Loaded from: {config.get('_source')}", 'Config')

        # Step 2: PROVIDER CONFIG
        print_section('2. PROVIDER CONFIG')
        print_json({
            'provider_name': 'github',
            'base_url': 'https://api.github.com',
            'health_endpoint': '/user'
        }, 'Provider Config')

        # Step 3: PROXY CONFIG
        print_section('3. PROXY CONFIG')
        print_json({'proxy_url': None, 'cert_verify': True}, 'Network Config')

        # Step 4: AUTH CONFIG
        print_section('4. AUTH CONFIG')
        print_info(f"Auth type: bearer", 'Auth')
        print_info(f"Token: {mask_sensitive(token)}", 'Auth')

        # Step 5: REQUEST CONFIG
        print_section('5. REQUEST CONFIG')
        print_json({'method': 'GET', 'url': 'https://api.github.com/user'}, 'Request')

        # Step 6: FETCH
        print_section('6. FETCH')
        response = await client.get('/user')

        # Step 7: RESPONSE
        print_section('7. RESPONSE')
        if response['ok']:
            print_success(f"Connected as @{response['data']['login']}", 'GitHub')
        else:
            print_error(f"HTTP {response['status']}", 'GitHub')

============================================================================
LLM INTEGRATION INSTRUCTIONS
============================================================================

When generating code that uses this library:

1. IMPORT: Always import from console_print
    ```python
    from console_print import (
        print_section, print_json, print_info, print_success,
        print_error, mask_sensitive
    )
    ```

2. SECTIONS: Use print_section() to mark major steps in a process
    ```python
    print_section('1. LOADING CONFIG')
    print_section('2. CONNECTING')
    print_section('3. EXECUTING QUERY')
    ```

3. STATUS WITH CONTEXT: Always include the component/provider name as title
    ```python
    print_info('Connecting...', 'Redis')       # NOT: print_info('Redis: Connecting...')
    print_success('Connected', 'PostgreSQL')   # NOT: print_success('PostgreSQL connected')
    print_error('Timeout', 'Elasticsearch')    # NOT: print_error('Elasticsearch timeout')
    ```

4. JSON WITH TITLES: Label JSON blocks for clarity
    ```python
    print_json(config, 'Provider Config')      # NOT: print_json(config)
    print_json(response, 'API Response')       # NOT: print(json.dumps(response))
    ```

5. MASK SENSITIVE DATA: Never log raw credentials
    ```python
    print_info(f"Token: {mask_sensitive(token)}", 'Auth')   # NOT: print_info(f"Token: {token}")
    print_info(f"URL: {mask_url(conn_string)}", 'DB')       # NOT: print_info(conn_string)
    ```

6. JAVASCRIPT EQUIVALENT: The MJS package has camelCase equivalents
    ```
    Python                JavaScript
    ------                ----------
    print_section()   ->  printSection()
    print_json()      ->  printJson()
    print_info()      ->  printInfo()
    print_success()   ->  printSuccess()
    print_error()     ->  printError()
    mask_sensitive()  ->  maskSensitive()
    mask_url()        ->  maskUrl()
    has_colors()      ->  hasColors()
    ```

============================================================================
PACKAGE STRUCTURE
============================================================================

    packages_py/console_print/
    ├── pyproject.toml                    # Package configuration
    ├── src/
    │   └── console_print/
    │       ├── __init__.py               # Main exports (this file)
    │       └── printer.py                # Core implementation
    └── tests_console_print/
        └── test_printer.py               # pytest tests

============================================================================
CROSS-LANGUAGE COMPATIBILITY
============================================================================

This package mirrors packages_mjs/console-print for consistent APIs across
Python and JavaScript codebases. Both packages:

- Support the same function signatures
- Accept string shorthand OR options dict for second argument
- Use the same output formats ([INFO:title], [OK:title], etc.)
- Gracefully degrade when color libraries are unavailable
"""

from console_print.printer import (
    # Core utilities
    HAS_RICH,
    has_colors,
    print_section,
    print_rule,
    print_json,

    # Sensitive data masking
    mask_sensitive,
    mask_url,

    # Status messages
    print_info,
    print_success,
    print_warning,
    print_error,
    print_debug,

    # Data display
    print_table,
    print_panel,
    print_syntax_panel,
    print_key_value,
    print_key_values,

    # Console class (for advanced usage)
    Console,
    console,
    get_console,
)

__all__ = [
    # Core utilities
    "HAS_RICH",
    "has_colors",
    "print_section",
    "print_rule",
    "print_json",

    # Sensitive data masking
    "mask_sensitive",
    "mask_url",

    # Status messages
    "print_info",
    "print_success",
    "print_warning",
    "print_error",
    "print_debug",

    # Data display
    "print_table",
    "print_panel",
    "print_syntax_panel",
    "print_key_value",
    "print_key_values",

    # Console class
    "Console",
    "console",
    "get_console",
]

__version__ = "1.0.0"
