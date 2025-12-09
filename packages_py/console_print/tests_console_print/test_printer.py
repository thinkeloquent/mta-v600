"""Tests for console_print module."""

import pytest
from console_print import (
    HAS_RICH,
    Console,
    console,
    get_console,
    print_info,
    print_success,
    print_warning,
    print_error,
    print_debug,
    print_table,
    print_json,
    print_rule,
    print_panel,
)


def test_has_rich_is_bool():
    """HAS_RICH should be a boolean."""
    assert isinstance(HAS_RICH, bool)


def test_console_exists():
    """Global console should exist."""
    assert console is not None


def test_console_is_rich_property():
    """Console should have is_rich property."""
    assert hasattr(console, "is_rich")
    assert console.is_rich == HAS_RICH


def test_get_console_returns_console():
    """get_console should return Console instance."""
    c = get_console()
    assert isinstance(c, Console)


def test_get_console_quiet():
    """get_console with quiet=True should work."""
    c = get_console(quiet=True)
    assert isinstance(c, Console)


def test_print_functions_exist():
    """All print functions should exist and be callable."""
    assert callable(print_info)
    assert callable(print_success)
    assert callable(print_warning)
    assert callable(print_error)
    assert callable(print_debug)
    assert callable(print_table)
    assert callable(print_json)
    assert callable(print_rule)
    assert callable(print_panel)


def test_print_info(capsys):
    """print_info should output to stdout."""
    print_info("test message")
    captured = capsys.readouterr()
    assert "INFO" in captured.out
    assert "test message" in captured.out


def test_print_success(capsys):
    """print_success should output to stdout."""
    print_success("test message")
    captured = capsys.readouterr()
    assert "OK" in captured.out
    assert "test message" in captured.out


def test_print_error(capsys):
    """print_error should output to stdout."""
    print_error("test message")
    captured = capsys.readouterr()
    assert "ERROR" in captured.out
    assert "test message" in captured.out


def test_print_warning(capsys):
    """print_warning should output to stdout."""
    print_warning("test message")
    captured = capsys.readouterr()
    assert "WARN" in captured.out
    assert "test message" in captured.out


def test_print_json_dict(capsys):
    """print_json should handle dict."""
    print_json({"key": "value"})
    captured = capsys.readouterr()
    assert "key" in captured.out
    assert "value" in captured.out


def test_print_json_list(capsys):
    """print_json should handle list."""
    print_json([1, 2, 3])
    captured = capsys.readouterr()
    assert "1" in captured.out


def test_print_table_empty(capsys):
    """print_table should handle empty data."""
    print_table([])
    captured = capsys.readouterr()
    assert "empty" in captured.out.lower()


def test_print_table_with_data(capsys):
    """print_table should display data."""
    data = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
    print_table(data)
    captured = capsys.readouterr()
    assert "Alice" in captured.out
    assert "Bob" in captured.out


def test_print_rule(capsys):
    """print_rule should output a rule."""
    print_rule("Title")
    captured = capsys.readouterr()
    assert "Title" in captured.out or "-" in captured.out


def test_console_print(capsys):
    """Console.print should output."""
    console.print("hello world")
    captured = capsys.readouterr()
    assert "hello world" in captured.out


def test_console_log(capsys):
    """Console.log should output with timestamp."""
    console.log("log message")
    captured = capsys.readouterr()
    assert "log message" in captured.out
