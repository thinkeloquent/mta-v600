"""
Console printer with optional Rich support.

Provides a unified interface for console output that works with or without Rich.
When Rich is not installed, falls back to standard logging/print.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Optional, Dict, List, Union

# Try to import Rich
try:
    from rich.console import Console as RichConsole
    from rich.table import Table as RichTable
    from rich.panel import Panel as RichPanel
    from rich.text import Text as RichText
    from rich.style import Style as RichStyle
    from rich.logging import RichHandler
    from rich.json import JSON as RichJSON
    from rich.syntax import Syntax as RichSyntax
    from rich.traceback import install as install_rich_traceback

    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    RichConsole = None
    RichTable = None
    RichPanel = None
    RichText = None
    RichStyle = None
    RichHandler = None
    RichJSON = None
    RichSyntax = None
    install_rich_traceback = None


class FallbackConsole:
    """
    Fallback console that mimics Rich's Console API using standard logging/print.
    Used when Rich is not installed.
    """

    def __init__(
        self,
        *,
        stderr: bool = False,
        force_terminal: Optional[bool] = None,
        no_color: bool = False,
        quiet: bool = False,
        **kwargs,
    ):
        self._stderr = stderr
        self._quiet = quiet
        self._no_color = no_color
        self._file = sys.stderr if stderr else sys.stdout

        # Setup basic logger
        self._logger = logging.getLogger("console_print")
        if not self._logger.handlers:
            handler = logging.StreamHandler(self._file)
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
            )
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[str] = None,
        highlight: bool = True,
        **kwargs,
    ) -> None:
        """Print to console (ignores style when Rich not available)."""
        if self._quiet:
            return
        message = sep.join(str(obj) for obj in objects)
        # Strip Rich markup tags
        message = self._strip_markup(message)
        print(message, end=end, file=self._file)

    def log(
        self,
        *objects: Any,
        sep: str = " ",
        log_locals: bool = False,
        **kwargs,
    ) -> None:
        """Log with timestamp."""
        if self._quiet:
            return
        message = sep.join(str(obj) for obj in objects)
        message = self._strip_markup(message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}", file=self._file)

    def rule(self, title: str = "", *, style: str = "rule.line", **kwargs) -> None:
        """Print a horizontal rule."""
        if self._quiet:
            return
        title = self._strip_markup(title)
        width = 80
        if title:
            padding = (width - len(title) - 2) // 2
            line = "-" * padding + f" {title} " + "-" * padding
        else:
            line = "-" * width
        print(line, file=self._file)

    def status(self, status: str, **kwargs):
        """Context manager for status (no-op without Rich)."""
        return FallbackStatus(status, self._file, self._quiet)

    def _strip_markup(self, text: str) -> str:
        """Remove Rich markup tags from text."""
        import re

        # Remove [style]...[/style] and [/style] tags
        return re.sub(r"\[/?[^\]]+\]", "", str(text))


class FallbackStatus:
    """Fallback status context manager."""

    def __init__(self, status: str, file, quiet: bool):
        self._status = status
        self._file = file
        self._quiet = quiet

    def __enter__(self):
        if not self._quiet:
            print(f"... {self._status}", file=self._file)
        return self

    def __exit__(self, *args):
        pass

    def update(self, status: str):
        self._status = status
        if not self._quiet:
            print(f"... {status}", file=self._file)


class Console:
    """
    Unified console interface that uses Rich when available, falls back to standard output.
    """

    def __init__(
        self,
        *,
        stderr: bool = False,
        force_terminal: Optional[bool] = None,
        no_color: bool = False,
        quiet: bool = False,
        **kwargs,
    ):
        self._quiet = quiet

        if HAS_RICH:
            self._console = RichConsole(
                stderr=stderr,
                force_terminal=force_terminal,
                no_color=no_color,
                quiet=quiet,
                **kwargs,
            )
        else:
            self._console = FallbackConsole(
                stderr=stderr,
                force_terminal=force_terminal,
                no_color=no_color,
                quiet=quiet,
                **kwargs,
            )

    @property
    def is_rich(self) -> bool:
        """Check if Rich is being used."""
        return HAS_RICH

    def print(self, *args, **kwargs) -> None:
        """Print to console."""
        self._console.print(*args, **kwargs)

    def log(self, *args, **kwargs) -> None:
        """Log with timestamp."""
        self._console.log(*args, **kwargs)

    def rule(self, title: str = "", **kwargs) -> None:
        """Print horizontal rule."""
        self._console.rule(title, **kwargs)

    def status(self, status: str, **kwargs):
        """Status context manager."""
        return self._console.status(status, **kwargs)

    def print_exception(self, **kwargs) -> None:
        """Print exception traceback."""
        if HAS_RICH:
            self._console.print_exception(**kwargs)
        else:
            import traceback

            traceback.print_exc(file=sys.stderr)


# Global console instance
console = Console()


def get_console(
    *,
    stderr: bool = False,
    force_terminal: Optional[bool] = None,
    no_color: bool = False,
    quiet: bool = False,
    **kwargs,
) -> Console:
    """Create a new Console instance."""
    return Console(
        stderr=stderr,
        force_terminal=force_terminal,
        no_color=no_color,
        quiet=quiet,
        **kwargs,
    )


# =============================================================================
# Convenience functions
# =============================================================================


def print_info(message: str, **kwargs) -> None:
    """Print info message (blue)."""
    if HAS_RICH:
        console.print(f"[blue][INFO][/blue] {message}", **kwargs)
    else:
        console.print(f"[INFO] {message}", **kwargs)


def print_success(message: str, **kwargs) -> None:
    """Print success message (green)."""
    if HAS_RICH:
        console.print(f"[green][OK][/green] {message}", **kwargs)
    else:
        console.print(f"[OK] {message}", **kwargs)


def print_warning(message: str, **kwargs) -> None:
    """Print warning message (yellow)."""
    if HAS_RICH:
        console.print(f"[yellow][WARN][/yellow] {message}", **kwargs)
    else:
        console.print(f"[WARN] {message}", **kwargs)


def print_error(message: str, **kwargs) -> None:
    """Print error message (red)."""
    if HAS_RICH:
        console.print(f"[red][ERROR][/red] {message}", **kwargs)
    else:
        console.print(f"[ERROR] {message}", **kwargs)


def print_debug(message: str, **kwargs) -> None:
    """Print debug message (dim)."""
    if HAS_RICH:
        console.print(f"[dim][DEBUG][/dim] {message}", **kwargs)
    else:
        console.print(f"[DEBUG] {message}", **kwargs)


def print_rule(title: str = "", **kwargs) -> None:
    """Print a horizontal rule with optional title."""
    console.rule(title, **kwargs)


def print_panel(
    content: str,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    border_style: str = "blue",
    **kwargs,
) -> None:
    """Print content in a panel/box."""
    if HAS_RICH:
        panel = RichPanel(content, title=title, subtitle=subtitle, border_style=border_style)
        console.print(panel, **kwargs)
    else:
        width = 80
        border = "+" + "-" * (width - 2) + "+"
        print(border)
        if title:
            print(f"| {title.center(width - 4)} |")
            print("|" + "-" * (width - 2) + "|")
        for line in content.split("\n"):
            print(f"| {line.ljust(width - 4)} |")
        if subtitle:
            print("|" + "-" * (width - 2) + "|")
            print(f"| {subtitle.center(width - 4)} |")
        print(border)


def print_json(data: Union[Dict, List, str], **kwargs) -> None:
    """Print JSON with syntax highlighting."""
    if isinstance(data, str):
        json_str = data
    else:
        json_str = json.dumps(data, indent=2, default=str)

    if HAS_RICH:
        console.print(RichJSON(json_str), **kwargs)
    else:
        print(json_str)


def print_syntax(
    code: str,
    lexer: str = "python",
    *,
    theme: str = "monokai",
    line_numbers: bool = False,
    **kwargs,
) -> None:
    """
    Print code with syntax highlighting.

    Args:
        code: The code/text to display
        lexer: Language for syntax highlighting (e.g., 'python', 'json', 'yaml', 'javascript')
        theme: Color theme (only with Rich)
        line_numbers: Show line numbers (only with Rich)
    """
    if HAS_RICH:
        syntax = RichSyntax(code, lexer, theme=theme, line_numbers=line_numbers)
        console.print(syntax, **kwargs)
    else:
        # Fallback: print plain code
        print(code)


def print_syntax_panel(
    code: str,
    lexer: str = "python",
    *,
    title: Optional[str] = None,
    theme: str = "monokai",
    border_style: str = "blue",
    expand: bool = False,
    **kwargs,
) -> None:
    """
    Print code with syntax highlighting inside a panel.

    Args:
        code: The code/text to display
        lexer: Language for syntax highlighting (e.g., 'python', 'json', 'yaml', 'javascript')
        title: Optional panel title
        theme: Color theme (only with Rich)
        border_style: Panel border style (only with Rich)
        expand: Expand panel to full width
    """
    if HAS_RICH:
        syntax = RichSyntax(code, lexer, theme=theme)
        panel = RichPanel(syntax, title=title, border_style=border_style, expand=expand)
        console.print(panel, **kwargs)
    else:
        # Fallback: simple box
        width = 80
        border = "+" + "-" * (width - 2) + "+"
        print(border)
        if title:
            # Strip Rich markup from title
            clean_title = title
            import re
            clean_title = re.sub(r"\[/?[^\]]+\]", "", str(title))
            print(f"| {clean_title.center(width - 4)} |")
            print("|" + "-" * (width - 2) + "|")
        for line in code.split("\n"):
            # Truncate long lines
            if len(line) > width - 4:
                line = line[: width - 7] + "..."
            print(f"| {line.ljust(width - 4)} |")
        print(border)


def print_table(
    data: List[Dict[str, Any]],
    *,
    title: Optional[str] = None,
    columns: Optional[List[str]] = None,
    **kwargs,
) -> None:
    """
    Print data as a table.

    Args:
        data: List of dictionaries to display
        title: Optional table title
        columns: Optional list of column names (defaults to keys from first row)
    """
    if not data:
        console.print("(empty table)")
        return

    # Determine columns
    if columns is None:
        columns = list(data[0].keys())

    if HAS_RICH:
        table = RichTable(title=title, **kwargs)
        for col in columns:
            table.add_column(col, style="cyan")
        for row in data:
            table.add_row(*[str(row.get(col, "")) for col in columns])
        console.print(table)
    else:
        # Fallback: simple text table
        if title:
            print(f"\n{title}")
            print("=" * len(title))

        # Calculate column widths
        widths = {col: len(col) for col in columns}
        for row in data:
            for col in columns:
                widths[col] = max(widths[col], len(str(row.get(col, ""))))

        # Print header
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        print(header)
        print("-" * len(header))

        # Print rows
        for row in data:
            line = " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
            print(line)
        print()


# =============================================================================
# Logging integration
# =============================================================================


def setup_logging(
    level: int = logging.INFO,
    *,
    rich_tracebacks: bool = True,
    show_time: bool = True,
    show_path: bool = False,
) -> None:
    """
    Setup logging with Rich handler if available.

    Args:
        level: Logging level
        rich_tracebacks: Enable Rich tracebacks (only with Rich)
        show_time: Show timestamps
        show_path: Show file paths in logs
    """
    if HAS_RICH:
        # Install Rich traceback handler
        if rich_tracebacks and install_rich_traceback:
            install_rich_traceback(show_locals=False)

        # Configure Rich logging handler
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[
                RichHandler(
                    rich_tracebacks=rich_tracebacks,
                    show_time=show_time,
                    show_path=show_path,
                )
            ],
        )
    else:
        # Standard logging
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
