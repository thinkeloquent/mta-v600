#!/usr/bin/env python3
"""
Parse pytest build and test error logs and convert to JSONL format.

Usage:
    # Parse build errors (from poetry run pytest --collect-only)
    python3 .bin/parse_pytest_build_errors.py build_log

    # Parse test errors (from poetry run pytest)
    python3 .bin/parse_pytest_build_errors.py test_log

Input:
    build_log: logs/pytest-build-error.log -> logs/pytest-build-error.jsonl
    test_log:  logs/pytest-test-error.log  -> logs/pytest-test-error.jsonl

Each output line contains a JSON object with:
    - package: The Python package name
    - file: Source file path
    - line: Line number of the error (if available)
    - error_type: Error type (ImportError, SyntaxError, AssertionError, etc.)
    - message: Full error message
    - traceback: Traceback lines (for detailed errors)
"""
import re
import json
import os
import sys
from datetime import datetime

# Configuration
CONFIG = {
    "build_log": {
        "input": "logs/pytest-build-error.log",
        "output": "logs/pytest-build-error.jsonl",
    },
    "test_log": {
        "input": "logs/pytest-test-error.log",
        "output": "logs/pytest-test-error.jsonl",
    },
}


def parse_collection_error(content):
    """
    Parse pytest collection errors (--collect-only failures).
    These occur during import/load phase before tests run.
    """
    errors = []
    timestamp = datetime.now().isoformat()

    # First, try to parse from "short test summary info" section
    # This is the most reliable source at the end of pytest output
    summary_errors = parse_short_summary_errors(content, timestamp)
    if summary_errors:
        errors.extend(summary_errors)

    # Also parse detailed error sections for additional context
    detailed_errors = parse_detailed_collection_errors(content, timestamp)

    # Merge detailed info into summary errors if we have both
    if summary_errors and detailed_errors:
        errors = merge_error_details(summary_errors, detailed_errors)
    elif detailed_errors and not summary_errors:
        errors = detailed_errors

    return errors


def parse_short_summary_errors(content, timestamp):
    """
    Parse errors from pytest's 'short test summary info' section.
    Format: ERROR path/to/test.py - ModuleNotFoundError: message
    """
    errors = []

    # Find the short test summary info section
    summary_match = re.search(
        r"={10,}\s*short test summary info\s*={10,}\s*\n(.*?)(?:={10,}|$)",
        content,
        re.DOTALL,
    )

    if not summary_match:
        return errors

    summary_section = summary_match.group(1)

    # Pattern for ERROR lines in summary
    # Examples:
    #   ERROR packages_py/cache_dsn/tests/test_config.py
    #   ERROR __STAGE__/mta-v400/app/hello/tests/test_hello.py
    #   ERROR packages_py/cache_request/tests - ModuleNotFoundError: No module named 'tests.conftest'
    error_pattern = re.compile(
        r"^ERROR\s+(\S+)\s*(?:-\s*(.+))?$",
        re.MULTILINE,
    )

    for match in error_pattern.finditer(summary_section):
        test_file = match.group(1).strip()
        error_message = match.group(2) or ""

        # Extract package name
        package = extract_package_name(test_file)

        # Parse error type from message
        error_type = "CollectionError"
        message = error_message

        if error_message:
            type_match = re.match(
                r"(ModuleNotFoundError|ImportError|SyntaxError|"
                r"AttributeError|TypeError|_pytest\.pathlib\.ImportPathMismatchError):\s*(.+)",
                error_message,
            )
            if type_match:
                error_type = type_match.group(1)
                message = type_match.group(2)

        errors.append(
            {
                "package": package,
                "test_file": test_file,
                "file": test_file,
                "line": None,
                "error_type": error_type,
                "message": message.strip() if message else "Collection failed",
                "traceback": [],
                "phase": "collection",
                "timestamp": timestamp,
            }
        )

    return errors


def parse_detailed_collection_errors(content, timestamp):
    """
    Parse detailed collection errors from ERROR collecting sections.
    """
    errors = []

    # Pattern for import errors in traceback
    import_error_pattern = re.compile(
        r"^E\s+(ImportError|ModuleNotFoundError|SyntaxError|AttributeError|NameError|TypeError):\s*(.+)$",
        re.MULTILINE,
    )

    # Pattern for file:line in traceback
    file_line_pattern = re.compile(r'File "([^"]+)", line (\d+)')

    # Split content by collection error markers
    sections = re.split(r"_{20,}\s*ERROR\s+collecting", content)

    for section in sections[1:]:  # Skip first empty section
        # Extract the file being collected - path ends at whitespace or underscore sequence
        # Format: " path/to/file ___" or " path/to/file.py ___"
        file_match = re.match(r"\s*(\S+?)(?:\s+_{3,}|\s*$)", section)
        if not file_match:
            continue

        test_file = file_match.group(1).strip()
        package = extract_package_name(test_file)

        # Find import/syntax errors (lines starting with E)
        error_matches = import_error_pattern.findall(section)

        # Find file:line references in traceback
        file_line_matches = file_line_pattern.findall(section)
        source_file = None
        line_num = None

        if file_line_matches:
            source_file, line_num = file_line_matches[-1]
            line_num = int(line_num)

        traceback_lines = extract_traceback(section)

        if error_matches:
            for error_type, message in error_matches:
                errors.append(
                    {
                        "package": package,
                        "test_file": test_file,
                        "file": source_file or test_file,
                        "line": line_num,
                        "error_type": error_type,
                        "message": message.strip(),
                        "traceback": traceback_lines,
                        "phase": "collection",
                        "timestamp": timestamp,
                    }
                )
        else:
            # Try alternate error pattern without E prefix
            alt_error_pattern = re.compile(
                r"^(ImportError|ModuleNotFoundError|SyntaxError):\s*(.+)$",
                re.MULTILINE,
            )
            alt_matches = alt_error_pattern.findall(section)

            if alt_matches:
                for error_type, message in alt_matches:
                    errors.append(
                        {
                            "package": package,
                            "test_file": test_file,
                            "file": source_file or test_file,
                            "line": line_num,
                            "error_type": error_type,
                            "message": message.strip(),
                            "traceback": traceback_lines,
                            "phase": "collection",
                            "timestamp": timestamp,
                        }
                    )
            else:
                errors.append(
                    {
                        "package": package,
                        "test_file": test_file,
                        "file": source_file or test_file,
                        "line": line_num,
                        "error_type": "CollectionError",
                        "message": section.strip()[:500],
                        "traceback": traceback_lines,
                        "phase": "collection",
                        "timestamp": timestamp,
                    }
                )

    return errors


def merge_error_details(summary_errors, detailed_errors):
    """
    Merge detailed error information into summary errors.
    """
    # Create lookup by test_file
    detailed_by_file = {}
    for err in detailed_errors:
        key = err.get("test_file", "")
        if key not in detailed_by_file:
            detailed_by_file[key] = err

    # Enrich summary errors with details
    for err in summary_errors:
        key = err.get("test_file", "")
        if key in detailed_by_file:
            detail = detailed_by_file[key]
            if detail.get("line"):
                err["line"] = detail["line"]
            if detail.get("file") and detail["file"] != detail.get("test_file"):
                err["source_file"] = detail["file"]
            if detail.get("traceback"):
                err["traceback"] = detail["traceback"]
            # If summary has generic message, use detailed message
            if err.get("message") == "Collection failed" and detail.get("message"):
                err["message"] = detail["message"]
                err["error_type"] = detail.get("error_type", err["error_type"])

    return summary_errors


def parse_test_failures(content):
    """
    Parse pytest test failures from actual test runs.
    """
    errors = []
    timestamp = datetime.now().isoformat()

    # Pattern for failed tests in short test summary
    # Format: FAILED path/to/test.py::TestClass::test_name
    # or:     FAILED path/to/test.py::TestClass::test_name - ErrorType: message
    failed_pattern = re.compile(
        r"^FAILED\s+([^\s:]+)::(\S+?)(?:\s+-\s+(.+))?$", re.MULTILINE
    )

    # Pattern for error tests in short test summary
    # Format: ERROR path/to/test.py::TestClass::test_name - Exception: message
    error_pattern = re.compile(
        r"^ERROR\s+([^\s:]+)::(\S+?)(?:\s+-\s+(.+))?$", re.MULTILINE
    )

    # Find all FAILED lines
    for match in failed_pattern.finditer(content):
        test_file = match.group(1)
        test_name = match.group(2)
        short_message = match.group(3) or ""

        package = extract_package_name(test_file)

        # Parse error type and message from short message
        error_type, message = parse_error_message(short_message)

        errors.append(
            {
                "package": package,
                "test_file": test_file,
                "test_name": test_name,
                "file": test_file,
                "line": None,
                "error_type": error_type or "TestFailure",
                "message": message or "",
                "traceback": [],
                "phase": "test",
                "result": "FAILED",
                "timestamp": timestamp,
            }
        )

    # Find all ERROR lines (test errors, not collection errors)
    for match in error_pattern.finditer(content):
        test_file = match.group(1)
        test_name = match.group(2)
        short_message = match.group(3) or ""

        package = extract_package_name(test_file)
        error_type, message = parse_error_message(short_message)

        errors.append(
            {
                "package": package,
                "test_file": test_file,
                "test_name": test_name,
                "file": test_file,
                "line": None,
                "error_type": error_type or "Error",
                "message": message or "",
                "traceback": [],
                "phase": "test",
                "result": "ERROR",
                "timestamp": timestamp,
            }
        )

    # Parse detailed failure sections for more info
    errors = enrich_with_detailed_sections(content, errors)

    return errors


def parse_error_message(message):
    """
    Parse error type and message from a pytest error line.
    Example: "AssertionError: assert 1 == 2" -> ("AssertionError", "assert 1 == 2")
    """
    if not message:
        return None, None

    # Common error patterns
    error_pattern = re.compile(
        r"^(AssertionError|TypeError|ValueError|KeyError|AttributeError|"
        r"ImportError|ModuleNotFoundError|RuntimeError|Exception|"
        r"IndexError|ZeroDivisionError|FileNotFoundError|PermissionError|"
        r"ConnectionError|TimeoutError|OSError):\s*(.*)$"
    )

    match = error_pattern.match(message.strip())
    if match:
        return match.group(1), match.group(2)

    return None, message


def extract_package_name(file_path):
    """
    Extract package name from file path.
    Examples:
        packages_py/cache_dsn/tests/test_dsn.py -> cache_dsn
        packages-py/figma_api/tests -> figma_api
        fastapi_apps/app_hello/tests/test_hello.py -> app_hello
        fastapi-apps/app_hello/tests -> app_hello
        __STAGE__/mta-v400/app/hello/tests -> hello
        __SPECS__/mta-v500/packages-py/figma_api/tests -> figma_api
        tests/test_main.py -> root
    """
    parts = file_path.replace("\\", "/").split("/")

    # Check for packages_py or packages-py pattern
    for pkg_dir in ["packages_py", "packages-py"]:
        if pkg_dir in parts:
            idx = parts.index(pkg_dir)
            if idx + 1 < len(parts):
                return parts[idx + 1]

    # Check for fastapi_apps or fastapi-apps pattern
    for app_dir in ["fastapi_apps", "fastapi-apps"]:
        if app_dir in parts:
            idx = parts.index(app_dir)
            if idx + 1 < len(parts):
                return parts[idx + 1]

    # Check for __STAGE__ or __SPECS__ patterns with nested structures
    # e.g., __STAGE__/mta-v400/app/hello/tests -> hello
    # e.g., __STAGE__/mta-v400/packages/figma-api/tests -> figma-api
    if "__STAGE__" in parts or "__SPECS__" in parts:
        # Look for 'app', 'packages', 'py' directories
        for marker in ["app", "packages", "py"]:
            if marker in parts:
                idx = parts.index(marker)
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        # Fallback: use the path after __STAGE__ or __SPECS__
        for marker in ["__STAGE__", "__SPECS__"]:
            if marker in parts:
                idx = parts.index(marker)
                if idx + 1 < len(parts):
                    return parts[idx + 1]

    # Check for packages_mjs pattern
    if "packages_mjs" in parts:
        idx = parts.index("packages_mjs")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    # Check for src/ingestion type patterns
    if "src" in parts:
        idx = parts.index("src")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    # Default to root
    return "root"


def extract_traceback(section):
    """
    Extract traceback lines from an error section.
    """
    lines = []
    in_traceback = False

    for line in section.split("\n"):
        stripped = line.strip()

        # Start of traceback
        if stripped.startswith("Traceback (most recent call last):"):
            in_traceback = True
            lines.append(stripped)
            continue

        # Lines within traceback
        if in_traceback:
            if stripped.startswith('File "') or stripped.startswith(
                "    "
            ):
                lines.append(stripped)
            elif stripped and not stripped.startswith("_"):
                # Error line (e.g., "ImportError: ...")
                lines.append(stripped)
                break

    return lines[:20]  # Limit to 20 lines


def enrich_with_detailed_sections(content, errors):
    """
    Enrich error records with information from detailed failure sections.
    """
    # Pattern for individual test failure/error sections
    # Matches: _____________ TestClass.test_name _____________
    section_pattern = re.compile(
        r"_{10,}\s+([^\n]+?)\s+_{10,}\s*\n(.*?)(?=_{10,}|$)",
        re.DOTALL,
    )

    # Pattern for error lines (E   ErrorType: message)
    error_line_pattern = re.compile(
        r"^E\s+(AttributeError|AssertionError|TypeError|ValueError|KeyError|"
        r"ImportError|ModuleNotFoundError|RuntimeError|Exception|"
        r"IndexError|ZeroDivisionError|FileNotFoundError|PermissionError|"
        r"ConnectionError|TimeoutError|OSError|NameError):\s*(.+)$",
        re.MULTILINE,
    )

    for match in section_pattern.finditer(content):
        test_identifier = match.group(1).strip()
        section_content = match.group(2)

        # Skip FAILURES/ERRORS section headers
        if test_identifier in ("FAILURES", "ERRORS"):
            continue

        # Find matching error and enrich it
        for error in errors:
            test_name = error.get("test_name", "")
            # Match by test name (handle TestClass::test_name or TestClass.test_name)
            normalized_identifier = test_identifier.replace(".", "::")
            if test_name and (
                normalized_identifier.endswith(test_name) or
                test_identifier.endswith(test_name.replace("::", "."))
            ):
                # Extract file:line from section (last occurrence before error)
                file_line_pattern = re.compile(r'([^\s:]+\.py):(\d+):')
                file_line_matches = file_line_pattern.findall(section_content)
                if file_line_matches:
                    # Use the last file:line reference (closest to error)
                    error["file"] = file_line_matches[-1][0]
                    error["line"] = int(file_line_matches[-1][1])

                # Extract error type and message from E lines
                error_match = error_line_pattern.search(section_content)
                if error_match:
                    error["error_type"] = error_match.group(1)
                    error["message"] = error_match.group(2).strip()

                # Extract traceback
                error["traceback"] = extract_traceback(section_content)
                break

    return errors


def process_log(mode):
    """
    Process log file based on mode (build_log or test_log).
    """
    if mode not in CONFIG:
        print(f"Error: Unknown mode '{mode}'. Use 'build_log' or 'test_log'.")
        sys.exit(1)

    config = CONFIG[mode]
    log_file_path = config["input"]
    output_file_path = config["output"]

    try:
        with open(log_file_path, "r") as f:
            log_content = f.read()
    except FileNotFoundError:
        print(f"Error: Log file not found at {log_file_path}")
        sys.exit(1)

    # Parse based on mode
    if mode == "build_log":
        errors = parse_collection_error(log_content)
    else:  # test_log
        errors = parse_test_failures(log_content)

    if not errors:
        print(f"No errors found in {log_file_path}")
        return

    # Calculate statistics
    total_errors = len(errors)
    unique_errors = set()
    for error in errors:
        unique_key = (
            error.get("file", ""),
            error.get("line", ""),
            error.get("error_type", ""),
        )
        unique_errors.add(unique_key)
    dedup_count = len(unique_errors)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Write JSONL output
    with open(output_file_path, "w") as f:
        for error in errors:
            f.write(json.dumps(error) + "\n")

    print(f"Errors consolidated into {output_file_path}")
    print(f"Errors found: {total_errors} total / {dedup_count} unique")

    # Print summary by package
    by_package = {}
    for error in errors:
        pkg = error.get("package", "unknown")
        by_package[pkg] = by_package.get(pkg, 0) + 1

    if by_package:
        print("\nBy package:")
        for pkg, count in sorted(by_package.items(), key=lambda x: -x[1]):
            print(f"  {pkg}: {count}")


def show_help():
    """Show usage help."""
    print(__doc__)
    print("\nCommands:")
    print("  build_log  - Parse pytest collection/build errors")
    print("               Input:  logs/pytest-build-error.log")
    print("               Output: logs/pytest-build-error.jsonl")
    print("")
    print("  test_log   - Parse pytest test failures")
    print("               Input:  logs/pytest-test-error.log")
    print("               Output: logs/pytest-test-error.jsonl")


def main():
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)

    command = sys.argv[1]

    if command in ["--help", "-h", "help"]:
        show_help()
        sys.exit(0)

    if command in ["build_log", "test_log"]:
        process_log(command)
    else:
        print(f"Error: Unknown command '{command}'")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
