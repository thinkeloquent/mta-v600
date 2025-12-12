"""
Console printer with optional Rich support.

Provides a unified interface for console output that works with or without Rich.
When Rich is not installed, falls back to standard print.

This module mirrors the API of @internal/console-print (MJS version).
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List, Optional, Union

# Try to import Rich
try:
    from rich.console import Console as RichConsole
    from rich.table import Table as RichTable
    from rich.panel import Panel as RichPanel
    from rich.json import JSON as RichJSON
    from rich.syntax import Syntax as RichSyntax

    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    RichConsole = None
    RichTable = None
    RichPanel = None
    RichJSON = None
    RichSyntax = None


# =============================================================================
# Helper Functions
# =============================================================================


def has_colors() -> bool:
    """
    Check if colors are available (Rich is installed).

    Returns:
        bool: True if Rich is available for colored output
    """
    return HAS_RICH


def _normalize_options(
    options_or_title: Union[str, Dict[str, Any], None],
    title_key: str = "title",
) -> Dict[str, Any]:
    """
    Normalize options argument - supports string shorthand for title.

    Args:
        options_or_title: Options dict or title string
        title_key: Key name for title in options

    Returns:
        dict: Normalized options object
    """
    if options_or_title is None:
        return {}
    if isinstance(options_or_title, str):
        return {title_key: options_or_title}
    return options_or_title


# =============================================================================
# Section and Rule Printing
# =============================================================================


def print_section(
    title: str,
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print a section header with a title.

    Args:
        title: Section title
        options_or_title: Options dict or ignored (for API consistency)
            - width: Width of the section line (default: 60)
            - char: Character to use for the line (default: '=')
    """
    options = _normalize_options(options_or_title)
    width = options.get("width", 60)
    char = options.get("char", "=")
    line = char * width

    print(f"\n{line}")
    if HAS_RICH:
        console = RichConsole()
        console.print(f"[bold cyan]Step: {title}[/bold cyan]")
    else:
        print(f"Step: {title}")
    print(line)


def print_rule(
    title: str = "",
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print a horizontal rule.

    Args:
        title: Optional title in the rule
        options_or_title: Options dict
            - width: Width of the rule (default: 60)
            - char: Character to use for the rule (default: '-')
    """
    options = _normalize_options(options_or_title)
    width = options.get("width", 60)
    char = options.get("char", "-")

    if title:
        padding = max(0, (width - len(title) - 2) // 2)
        left_pad = char * padding
        right_pad = char * (width - padding - len(title) - 2)
        print(f"{left_pad} {title} {right_pad}")
    else:
        print(char * width)


# =============================================================================
# JSON Printing
# =============================================================================


def print_json(
    data: Union[Dict, List, str, Any],
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print JSON data with indentation and optional syntax highlighting.

    Args:
        data: Data to print as JSON
        options_or_title: Title string or options dict
            - title: Title to print before JSON
            - indent: Indentation spaces (default: 2)
    """
    options = _normalize_options(options_or_title)
    title = options.get("title")
    indent = options.get("indent", 2)

    # Print title if provided
    if title:
        if HAS_RICH:
            console = RichConsole()
            console.print(f"[dim][{title}][/dim]")
        else:
            print(f"[{title}]")

    # Convert to JSON string
    if isinstance(data, str):
        json_str = data
    else:
        json_str = json.dumps(data, indent=indent, default=str)

    # Print with or without Rich
    if HAS_RICH:
        console = RichConsole()
        console.print(RichJSON(json_str))
    else:
        print(json_str)


# =============================================================================
# Sensitive Data Masking
# =============================================================================


def mask_sensitive(
    value: Optional[str],
    options_or_show_chars: Union[int, Dict[str, Any], None] = None,
) -> str:
    """
    Mask sensitive values for logging.

    Args:
        value: Value to mask
        options_or_show_chars: Number of chars to show, or options dict
            - show_chars: Number of characters to show before masking (default: 4)
            - mask_char: Character to use for masking (default: '*')
            - placeholder: Placeholder for null/empty values (default: '<none>')

    Returns:
        str: Masked value
    """
    # Handle int shorthand for show_chars
    if isinstance(options_or_show_chars, int):
        options = {"show_chars": options_or_show_chars}
    else:
        options = _normalize_options(options_or_show_chars)

    show_chars = options.get("show_chars", 4)
    mask_char = options.get("mask_char", "*")
    placeholder = options.get("placeholder", "<none>")

    if not value:
        return placeholder
    if len(value) <= show_chars:
        return mask_char * len(value)
    return value[:show_chars] + "***"


def mask_url(url: Optional[str]) -> str:
    """
    Mask a URL by hiding password and sensitive query parameters.

    Args:
        url: URL to mask

    Returns:
        str: Masked URL
    """
    if not url:
        return "<none>"

    try:
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

        parsed = urlparse(url)

        # Mask password in netloc
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
        else:
            netloc = parsed.netloc

        # Mask sensitive query parameters
        sensitive_params = {"key", "token", "secret", "password", "apikey", "api_key", "auth"}
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            for param in sensitive_params:
                if param in params:
                    params[param] = ["****"]
            query = urlencode(params, doseq=True)
        else:
            query = parsed.query

        return urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            query,
            parsed.fragment,
        ))
    except Exception:
        # Regex fallback if URL parsing fails
        result = re.sub(r"(://[^:]+:)[^@]+(@)", r"\1****\2", url)
        result = re.sub(
            r"([?&](key|token|secret|password|apikey|api_key|auth)=)[^&]+",
            r"\1****",
            result,
            flags=re.IGNORECASE,
        )
        return result


# =============================================================================
# Status Messages
# =============================================================================


def print_info(
    message: str,
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print an info message.

    Args:
        message: Message to print
        options_or_title: Title string or options dict
            - title: Title/label to show after [INFO]
    """
    options = _normalize_options(options_or_title)
    title = options.get("title")
    label = f"[INFO:{title}]" if title else "[INFO]"

    if HAS_RICH:
        console = RichConsole()
        console.print(f"[blue]{label}[/blue] {message}")
    else:
        print(f"{label} {message}")


def print_success(
    message: str,
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print a success message.

    Args:
        message: Message to print
        options_or_title: Title string or options dict
            - title: Title/label to show after [OK]
    """
    options = _normalize_options(options_or_title)
    title = options.get("title")
    label = f"[OK:{title}]" if title else "[OK]"

    if HAS_RICH:
        console = RichConsole()
        console.print(f"[green]{label}[/green] {message}")
    else:
        print(f"{label} {message}")


def print_warning(
    message: str,
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print a warning message.

    Args:
        message: Message to print
        options_or_title: Title string or options dict
            - title: Title/label to show after [WARN]
    """
    options = _normalize_options(options_or_title)
    title = options.get("title")
    label = f"[WARN:{title}]" if title else "[WARN]"

    if HAS_RICH:
        console = RichConsole()
        console.print(f"[yellow]{label}[/yellow] {message}")
    else:
        print(f"{label} {message}")


def print_error(
    message: str,
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print an error message.

    Args:
        message: Message to print
        options_or_title: Title string or options dict
            - title: Title/label to show after [ERROR]
    """
    options = _normalize_options(options_or_title)
    title = options.get("title")
    label = f"[ERROR:{title}]" if title else "[ERROR]"

    if HAS_RICH:
        console = RichConsole()
        console.print(f"[red]{label}[/red] {message}")
    else:
        print(f"{label} {message}")


def print_debug(
    message: str,
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print a debug message.

    Args:
        message: Message to print
        options_or_title: Title string or options dict
            - title: Title/label to show after [DEBUG]
    """
    options = _normalize_options(options_or_title)
    title = options.get("title")
    label = f"[DEBUG:{title}]" if title else "[DEBUG]"

    if HAS_RICH:
        console = RichConsole()
        console.print(f"[dim]{label} {message}[/dim]")
    else:
        print(f"{label} {message}")



def print_auth_trace(
    message: str,
    file_info: str,
    key: Optional[str] = None,
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print an authentication trace message.

    Format: [TRACE raw_api_key] {file_info} {message} {key_preview}...

    Args:
        message: Trace message
        file_info: File context (e.g., "file.py:123")
        key: The raw api key to preview (optional)
        options_or_title: Title string or options dict (for compatibility)
    """
    key_preview = ""
    if key:
        visible_len = 30
        preview = key[:visible_len] if len(key) > visible_len else key
        key_preview = f" {preview}..." if preview else " <empty>..."
    elif key is None:
        key_preview = " None..."

    full_message = f"{file_info} {message}{key_preview}"
    
    if HAS_RICH:
        console = RichConsole()
        # Use a distinct style for these traces to make them stand out or fade as needed
        # User requested specific format: [TRACE raw_api_key] ...
        console.print(f"[bold magenta][TRACE raw_api_key][/bold magenta] {full_message}")
    else:
        print(f"[TRACE raw_api_key] {full_message}")


# =============================================================================
# Table Printing
# =============================================================================


def print_table(
    data: List[Dict[str, Any]],
    options_or_title: Union[str, Dict[str, Any], None] = None,
) -> None:
    """
    Print data as a simple table.

    Args:
        data: Array of objects to print
        options_or_title: Title string or options dict
            - title: Table title
            - columns: Column names (defaults to keys from first row)
    """
    options = _normalize_options(options_or_title)
    title = options.get("title")
    columns = options.get("columns")

    if not data:
        print("(empty table)")
        return

    # Determine columns
    cols = columns or list(data[0].keys())

    # Calculate column widths
    widths = {col: len(col) for col in cols}
    for row in data:
        for col in cols:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val))

    if HAS_RICH:
        console = RichConsole()
        table = RichTable(title=title)
        for col in cols:
            table.add_column(col, style="cyan")
        for row in data:
            table.add_row(*[str(row.get(col, "")) for col in cols])
        console.print(table)
    else:
        # Print title
        if title:
            print(f"\n{title}")
            print("=" * len(title))

        # Print header
        header = " | ".join(col.ljust(widths[col]) for col in cols)
        print(header)
        print("-" * len(header))

        # Print rows
        for row in data:
            line = " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in cols)
            print(line)
        print()


# =============================================================================
# Panel Printing
# =============================================================================


def print_panel(
    content: str,
    options_or_title: Union[str, Dict[str, Any], None] = None,
    *,
    title: Optional[str] = None,
    width: int = 60,
) -> None:
    """
    Print content in a simple box/panel.

    Args:
        content: Content to print
        options_or_title: Title string or options dict
            - title: Panel title
            - width: Panel width (default: 60)
        title: Panel title (keyword arg, overrides options_or_title)
        width: Panel width (keyword arg, overrides options_or_title)
    """
    options = _normalize_options(options_or_title)
    # Keyword args override options dict
    title = title if title is not None else options.get("title")
    width = width if width != 60 else options.get("width", 60)

    if HAS_RICH:
        console = RichConsole()
        panel = RichPanel(content, title=title)
        console.print(panel)
    else:
        border = "+" + "-" * (width - 2) + "+"

        print(border)
        if title:
            centered = title.center(width - 4) if len(title) < width - 4 else title[: width - 4]
            print(f"| {centered} |")
            print("|" + "-" * (width - 2) + "|")

        for line in content.split("\n"):
            truncated = line if len(line) <= width - 4 else line[: width - 7] + "..."
            print(f"| {truncated.ljust(width - 4)} |")

        print(border)


def print_syntax_panel(
    code: str,
    lexer: str = "python",
    title: Optional[str] = None,
    theme: str = "monokai",
    line_numbers: bool = False,
    expand: bool = True,
    width: int = 60,
) -> None:
    """
    Print syntax-highlighted code in a panel.

    Args:
        code: Code/text to syntax highlight
        lexer: Syntax lexer (e.g., 'python', 'json', 'yaml', 'javascript')
        title: Panel title (supports Rich markup when Rich is available)
        theme: Syntax theme (default: 'monokai')
        line_numbers: Show line numbers
        expand: Expand panel to full width
        width: Panel width when expand=False (fallback mode only)
    """
    if HAS_RICH and RichSyntax is not None:
        console = RichConsole()
        syntax = RichSyntax(code, lexer, theme=theme, line_numbers=line_numbers)
        panel = RichPanel(syntax, title=title, expand=expand)
        console.print(panel)
    else:
        # Fallback: simple bordered output
        border = "+" + "-" * (width - 2) + "+"

        print(border)
        if title:
            # Strip Rich markup from title
            clean_title = re.sub(r"\[/?[^\]]+\]", "", title)
            centered = clean_title.center(width - 4) if len(clean_title) < width - 4 else clean_title[: width - 4]
            print(f"| {centered} |")
            print("|" + "-" * (width - 2) + "|")

        for line in code.split("\n"):
            truncated = line if len(line) <= width - 4 else line[: width - 7] + "..."
            print(f"| {truncated.ljust(width - 4)} |")

        print(border)


# =============================================================================
# Key-Value Printing
# =============================================================================


def print_key_value(
    label: str,
    value: Any,
    options_or_indent: Union[int, Dict[str, Any], None] = None,
) -> None:
    """
    Print a labeled value (key: value format).

    Args:
        label: Label/key
        value: Value to print
        options_or_indent: Indent level (int) or options dict
            - indent: Indentation spaces (default: 2)
    """
    if isinstance(options_or_indent, int):
        options = {"indent": options_or_indent}
    else:
        options = _normalize_options(options_or_indent)

    indent = options.get("indent", 2)
    spaces = " " * indent

    if HAS_RICH:
        console = RichConsole()
        console.print(f"{spaces}[cyan]{label}[/cyan]: {value}")
    else:
        print(f"{spaces}{label}: {value}")


def print_key_values(
    obj: Dict[str, Any],
    options_or_indent: Union[int, Dict[str, Any], None] = None,
) -> None:
    """
    Print multiple key-value pairs.

    Args:
        obj: Object with key-value pairs
        options_or_indent: Indent level (int) or options dict
            - indent: Indentation spaces (default: 2)
    """
    for key, value in obj.items():
        print_key_value(key, value, options_or_indent)


# =============================================================================
# Console Class (for advanced usage)
# =============================================================================


class Console:
    """
    Unified console interface that uses Rich when available.

    For most use cases, prefer the module-level functions instead.
    """

    def __init__(
        self,
        *,
        stderr: bool = False,
        quiet: bool = False,
        **kwargs,
    ):
        self._quiet = quiet
        self._file = sys.stderr if stderr else sys.stdout

        if HAS_RICH:
            self._console = RichConsole(stderr=stderr, quiet=quiet, **kwargs)
        else:
            self._console = None

    @property
    def is_rich(self) -> bool:
        """Check if Rich is being used."""
        return HAS_RICH

    def print(self, *args, **kwargs) -> None:
        """Print to console."""
        if self._quiet:
            return
        if HAS_RICH and self._console:
            self._console.print(*args, **kwargs)
        else:
            message = " ".join(str(arg) for arg in args)
            # Strip Rich markup
            message = re.sub(r"\[/?[^\]]+\]", "", message)
            print(message, file=self._file)

    def rule(self, title: str = "", **kwargs) -> None:
        """Print horizontal rule."""
        print_rule(title)


# Global console instance
console = Console()


def get_console(
    *,
    stderr: bool = False,
    quiet: bool = False,
    **kwargs,
) -> Console:
    """Create a new Console instance."""
    return Console(stderr=stderr, quiet=quiet, **kwargs)
