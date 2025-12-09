"""
console_print - Console printing with optional Rich support.

Falls back to standard logging if Rich is not installed.

Usage:
    from console_print import console, print_info, print_error, print_success, print_warning

    # Simple printing
    print_info("Starting process...")
    print_success("Done!")
    print_error("Something went wrong")
    print_warning("Be careful")

    # Using console directly
    console.print("Hello", style="bold blue")
    console.log("Debug message")

    # Check if Rich is available
    from console_print import HAS_RICH
    if HAS_RICH:
        console.print("[bold green]Rich is available![/bold green]")
"""

from console_print.printer import (
    HAS_RICH,
    Console,
    console,
    get_console,
    print_debug,
    print_error,
    print_info,
    print_success,
    print_warning,
    print_table,
    print_json,
    print_rule,
    print_panel,
)

__all__ = [
    "HAS_RICH",
    "Console",
    "console",
    "get_console",
    "print_debug",
    "print_error",
    "print_info",
    "print_success",
    "print_warning",
    "print_table",
    "print_json",
    "print_rule",
    "print_panel",
]

__version__ = "1.0.0"
