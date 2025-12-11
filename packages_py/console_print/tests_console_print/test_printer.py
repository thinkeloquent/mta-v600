"""Tests for console_print module."""

import pytest
from console_print import (
    HAS_RICH,
    has_colors,
    Console,
    console,
    get_console,
    print_section,
    print_rule,
    print_json,
    mask_sensitive,
    mask_url,
    print_info,
    print_success,
    print_warning,
    print_error,
    print_debug,
    print_table,
    print_panel,
    print_key_value,
    print_key_values,
)


class TestHasColors:
    """Tests for has_colors function."""

    def test_returns_bool(self):
        """has_colors should return a boolean."""
        assert isinstance(has_colors(), bool)

    def test_matches_has_rich(self):
        """has_colors should match HAS_RICH."""
        assert has_colors() == HAS_RICH


class TestMaskSensitive:
    """Tests for mask_sensitive function."""

    def test_returns_placeholder_for_none(self):
        """Should return placeholder for None."""
        assert mask_sensitive(None) == "<none>"

    def test_returns_placeholder_for_empty(self):
        """Should return placeholder for empty string."""
        assert mask_sensitive("") == "<none>"

    def test_masks_short_values_completely(self):
        """Should mask short values completely."""
        assert mask_sensitive("abc") == "***"
        assert mask_sensitive("abcd") == "****"

    def test_shows_first_n_characters(self):
        """Should show first N characters for longer values."""
        assert mask_sensitive("password123") == "pass***"
        assert mask_sensitive("secrettoken") == "secr***"

    def test_respects_show_chars_option_as_int(self):
        """Should respect show_chars as int shorthand."""
        assert mask_sensitive("password123", 2) == "pa***"
        assert mask_sensitive("password123", 6) == "passwo***"

    def test_respects_show_chars_option_in_dict(self):
        """Should respect show_chars in options dict."""
        assert mask_sensitive("password123", {"show_chars": 2}) == "pa***"

    def test_respects_placeholder_option(self):
        """Should respect custom placeholder."""
        assert mask_sensitive(None, {"placeholder": "N/A"}) == "N/A"


class TestMaskUrl:
    """Tests for mask_url function."""

    def test_returns_placeholder_for_none(self):
        """Should return placeholder for None."""
        assert mask_url(None) == "<none>"

    def test_returns_placeholder_for_empty(self):
        """Should return placeholder for empty string."""
        assert mask_url("") == "<none>"

    def test_masks_password_in_url(self):
        """Should mask password in URL."""
        url = "redis://user:secretpassword@localhost:6379/0"
        masked = mask_url(url)
        assert "****" in masked
        assert "secretpassword" not in masked

    def test_masks_sensitive_query_params(self):
        """Should mask sensitive query parameters."""
        url = "https://api.example.com?key=myapikey&other=value"
        masked = mask_url(url)
        assert "myapikey" not in masked
        assert "other=value" in masked


class TestPrintSection:
    """Tests for print_section function."""

    def test_prints_section_header(self, capsys):
        """Should print section header."""
        print_section("Test Section")
        captured = capsys.readouterr()
        assert "=" in captured.out
        assert "Test Section" in captured.out


class TestPrintRule:
    """Tests for print_rule function."""

    def test_prints_horizontal_rule(self, capsys):
        """Should print horizontal rule."""
        print_rule()
        captured = capsys.readouterr()
        assert "-" in captured.out

    def test_prints_rule_with_title(self, capsys):
        """Should print rule with title."""
        print_rule("Title")
        captured = capsys.readouterr()
        assert "Title" in captured.out


class TestPrintJson:
    """Tests for print_json function."""

    def test_prints_dict(self, capsys):
        """Should print dict as JSON."""
        print_json({"key": "value"})
        captured = capsys.readouterr()
        assert "key" in captured.out
        assert "value" in captured.out

    def test_prints_list(self, capsys):
        """Should print list as JSON."""
        print_json([1, 2, 3])
        captured = capsys.readouterr()
        assert "1" in captured.out

    def test_prints_string(self, capsys):
        """Should print JSON string."""
        print_json('{"key": "value"}')
        captured = capsys.readouterr()
        assert "key" in captured.out

    def test_prints_title_as_string(self, capsys):
        """Should print title when provided as string."""
        print_json({"key": "value"}, "My Title")
        captured = capsys.readouterr()
        assert "My Title" in captured.out

    def test_prints_title_from_options(self, capsys):
        """Should print title from options dict."""
        print_json({"key": "value"}, {"title": "Config Data"})
        captured = capsys.readouterr()
        assert "Config Data" in captured.out


class TestStatusMessages:
    """Tests for status message functions."""

    def test_print_info(self, capsys):
        """Should print info message."""
        print_info("Info message")
        captured = capsys.readouterr()
        assert "INFO" in captured.out
        assert "Info message" in captured.out

    def test_print_info_with_title_string(self, capsys):
        """Should print info with title as string."""
        print_info("Info message", "Redis")
        captured = capsys.readouterr()
        assert "INFO:Redis" in captured.out

    def test_print_info_with_title_in_options(self, capsys):
        """Should print info with title in options."""
        print_info("Info message", {"title": "Config"})
        captured = capsys.readouterr()
        assert "INFO:Config" in captured.out

    def test_print_success(self, capsys):
        """Should print success message."""
        print_success("Success message")
        captured = capsys.readouterr()
        assert "OK" in captured.out
        assert "Success message" in captured.out

    def test_print_success_with_title(self, capsys):
        """Should print success with title."""
        print_success("Connected", "Redis")
        captured = capsys.readouterr()
        assert "OK:Redis" in captured.out

    def test_print_warning(self, capsys):
        """Should print warning message."""
        print_warning("Warning message")
        captured = capsys.readouterr()
        assert "WARN" in captured.out
        assert "Warning message" in captured.out

    def test_print_warning_with_title(self, capsys):
        """Should print warning with title."""
        print_warning("Slow response", "API")
        captured = capsys.readouterr()
        assert "WARN:API" in captured.out

    def test_print_error(self, capsys):
        """Should print error message."""
        print_error("Error message")
        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Error message" in captured.out

    def test_print_error_with_title(self, capsys):
        """Should print error with title."""
        print_error("Connection failed", "Database")
        captured = capsys.readouterr()
        assert "ERROR:Database" in captured.out

    def test_print_debug(self, capsys):
        """Should print debug message."""
        print_debug("Debug message")
        captured = capsys.readouterr()
        assert "DEBUG" in captured.out
        assert "Debug message" in captured.out

    def test_print_debug_with_title(self, capsys):
        """Should print debug with title."""
        print_debug("Inspecting config", "Auth")
        captured = capsys.readouterr()
        assert "DEBUG:Auth" in captured.out


class TestPrintTable:
    """Tests for print_table function."""

    def test_handles_empty_data(self, capsys):
        """Should handle empty data."""
        print_table([])
        captured = capsys.readouterr()
        assert "empty" in captured.out.lower()

    def test_prints_table_with_data(self, capsys):
        """Should print table with data."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        print_table(data)
        captured = capsys.readouterr()
        assert "Alice" in captured.out
        assert "Bob" in captured.out

    def test_prints_table_with_title_string(self, capsys):
        """Should print table with title as string."""
        print_table([{"a": 1}], "My Table")
        captured = capsys.readouterr()
        # Rich may split the title across lines, so check for both words
        assert "My" in captured.out and "Table" in captured.out


class TestPrintPanel:
    """Tests for print_panel function."""

    def test_prints_content_in_panel(self, capsys):
        """Should print content in panel."""
        print_panel("Content here")
        captured = capsys.readouterr()
        assert "Content here" in captured.out
        assert "+" in captured.out or "─" in captured.out  # Border chars

    def test_prints_panel_with_title_string(self, capsys):
        """Should print panel with title as string."""
        print_panel("Content", "Panel Title")
        captured = capsys.readouterr()
        assert "Panel Title" in captured.out


class TestPrintKeyValue:
    """Tests for print_key_value function."""

    def test_prints_key_value_pair(self, capsys):
        """Should print key-value pair."""
        print_key_value("Host", "localhost")
        captured = capsys.readouterr()
        assert "Host" in captured.out
        assert "localhost" in captured.out

    def test_respects_indent_as_int(self, capsys):
        """Should respect indent as int shorthand."""
        print_key_value("Key", "value", 4)
        captured = capsys.readouterr()
        assert "    " in captured.out  # 4 spaces


class TestPrintKeyValues:
    """Tests for print_key_values function."""

    def test_prints_multiple_pairs(self, capsys):
        """Should print multiple key-value pairs."""
        print_key_values({"host": "localhost", "port": 6379})
        captured = capsys.readouterr()
        assert "host" in captured.out
        assert "localhost" in captured.out
        assert "port" in captured.out
        assert "6379" in captured.out


class TestConsole:
    """Tests for Console class."""

    def test_console_exists(self):
        """Global console should exist."""
        assert console is not None

    def test_console_is_rich_property(self):
        """Console should have is_rich property."""
        assert hasattr(console, "is_rich")
        assert console.is_rich == HAS_RICH

    def test_get_console_returns_console(self):
        """get_console should return Console instance."""
        c = get_console()
        assert isinstance(c, Console)

    def test_get_console_quiet(self):
        """get_console with quiet=True should work."""
        c = get_console(quiet=True)
        assert isinstance(c, Console)

    def test_console_print(self, capsys):
        """Console.print should output."""
        console.print("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.out
