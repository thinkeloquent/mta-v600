#!/usr/bin/env python3
"""
Parse pnpm build/test error logs and convert to JSONL format.

Usage:
    # Auto-detect mode based on which log file exists (most recent)
    python3 .bin/parse_pnpm_build_errors.py

    # Explicitly specify mode
    python3 .bin/parse_pnpm_build_errors.py build_log
    python3 .bin/parse_pnpm_build_errors.py test_log

Input/Output:
    build_log: logs/pnpm-build-error.log -> logs/pnpm-build-error.jsonl
    test_log:  logs/pnpm-test-error.log  -> logs/pnpm-test-error.jsonl

Each output line contains a JSON object with:
    - project: The internal package name (e.g., @internal/my-package)
    - file: Source file path
    - line: Line number of the error
    - error_code: TypeScript error code (e.g., TS2345) or test error type
    - message: Full error message (including multi-line continuations)
    - phase: "build" or "test"
"""
import re
import json
import os
import sys
from datetime import datetime

# Configuration
CONFIG = {
    "build_log": {
        "input": "logs/pnpm-build-error.log",
        "output": "logs/pnpm-build-error.jsonl",
    },
    "test_log": {
        "input": "logs/pnpm-test-error.log",
        "output": "logs/pnpm-test-error.jsonl",
    },
}


def detect_log_type(content):
    """
    Auto-detect whether content is from build or test based on patterns.

    Returns: "build_log" or "test_log"
    """
    # TypeScript build error pattern
    ts_error_pattern = re.compile(r"@internal\/[a-zA-Z0-9_-]+:.*error TS\d+:")

    # Jest/test patterns
    test_patterns = [
        r"FAIL\s+\S+",  # Jest FAIL line
        r"●\s+.+",  # Jest test marker
        r"PASS\s+\S+",  # Jest PASS line
        r"Test Suites:",  # Jest summary
        r"Tests:\s+\d+",  # Jest test count
        r"Running target test for",  # Nx test target
    ]

    # Count matches for each type
    build_matches = len(ts_error_pattern.findall(content))
    test_matches = sum(
        len(re.findall(pattern, content)) for pattern in test_patterns
    )

    if build_matches > test_matches:
        return "build_log"
    elif test_matches > 0:
        return "test_log"
    else:
        # Default to build if no clear signal
        return "build_log"


def auto_detect_mode():
    """
    Auto-detect which mode to use based on which log file exists and is most recent.

    Returns: ("build_log" or "test_log", log_content) or (None, None) if no logs found
    """
    build_log = CONFIG["build_log"]["input"]
    test_log = CONFIG["test_log"]["input"]

    build_exists = os.path.exists(build_log)
    test_exists = os.path.exists(test_log)

    if not build_exists and not test_exists:
        return None, None

    # If only one exists, use that
    if build_exists and not test_exists:
        with open(build_log, "r") as f:
            content = f.read()
        # Still verify content matches expected type
        detected = detect_log_type(content)
        return detected, content

    if test_exists and not build_exists:
        with open(test_log, "r") as f:
            content = f.read()
        detected = detect_log_type(content)
        return detected, content

    # Both exist - use the most recently modified one
    build_mtime = os.path.getmtime(build_log)
    test_mtime = os.path.getmtime(test_log)

    if test_mtime >= build_mtime:
        with open(test_log, "r") as f:
            content = f.read()
        detected = detect_log_type(content)
        return detected, content
    else:
        with open(build_log, "r") as f:
            content = f.read()
        detected = detect_log_type(content)
        return detected, content


def parse_typescript_build_errors(content):
    """
    Parse TypeScript build errors from pnpm build output.

    Format: @internal/package: path/file.ts(line,col): error TS####: message
    """
    errors = []
    timestamp = datetime.now().isoformat()

    current_error = None

    for line in content.splitlines():
        match = re.match(
            r"^(@internal\/[a-zA-Z0-9_-]+): ([^:]+)\((\d+),(\d+)\): error (TS\d+): (.*)$",
            line,
        )

        if match:
            if current_error:
                errors.append(current_error)

            project = match.group(1).strip()
            file_path = match.group(2).strip()
            line_num = int(match.group(3))
            error_code = match.group(5).strip()
            message = match.group(6).strip()

            current_error = {
                "project": project,
                "file": file_path,
                "line": line_num,
                "error_code": error_code,
                "message": message,
                "phase": "build",
                "timestamp": timestamp,
            }
        elif current_error and is_continuation_line(line):
            current_error["message"] += " " + line.strip()
        elif current_error and not line.strip():
            current_error["message"] += " " + line.strip()
        elif current_error:
            errors.append(current_error)
            current_error = None

    if current_error:
        errors.append(current_error)

    return errors


def is_continuation_line(line):
    """Check if a line is a continuation of a TypeScript error message."""
    stripped = line.strip()
    continuations = [
        "Type '",
        "Argument of type",
        "Overload",
        "Types of parameters",
        "Target signature provides too few arguments",
        "Non-abstract class",
        "Object literal may only specify known properties",
        "Property",
        "Module",
        "Expected",
        "Implicitly",
        "Object is possibly 'undefined'",
        "Missing the following properties",
        "Conversion of type",
        "Index signature for type",
        "must have a '[Symbol.asyncIterator]()' method",
    ]
    return any(stripped.startswith(c) for c in continuations)


def parse_jest_test_errors(content):
    """
    Parse Jest test errors from pnpm test output.

    Handles:
    - FAIL package/path/to/test.mjs
    - ● TestSuite › test name
    - expect(...).toBe(...) failures
    - Error: messages
    """
    errors = []
    timestamp = datetime.now().isoformat()

    current_package = None
    current_test_file = None

    # Pattern for FAIL lines from Jest
    fail_pattern = re.compile(r"^\s*FAIL\s+(\S+)\s*$")

    # Pattern for test name (● TestSuite › test name)
    test_name_pattern = re.compile(r"^\s*●\s+(.+)$")

    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for FAIL line
        fail_match = fail_pattern.match(line)
        if fail_match:
            current_test_file = fail_match.group(1)
            current_package = extract_package_from_path(current_test_file)
            i += 1
            continue

        # Check for test name (● marker)
        test_match = test_name_pattern.match(line)
        if test_match and current_test_file:
            test_name = test_match.group(1).strip()

            # Look ahead for error details
            error_info = extract_jest_error_details(lines, i + 1)

            errors.append(
                {
                    "project": current_package or "unknown",
                    "test_file": current_test_file,
                    "test_name": test_name,
                    "file": error_info.get("file", current_test_file),
                    "line": error_info.get("line"),
                    "error_code": error_info.get("error_type", "TestFailure"),
                    "message": error_info.get("message", ""),
                    "phase": "test",
                    "result": "FAILED",
                    "timestamp": timestamp,
                }
            )

        i += 1

    return errors


def extract_jest_error_details(lines, start_idx):
    """
    Extract error details from Jest output starting at given index.
    """
    result = {
        "error_type": "TestFailure",
        "message": "",
        "file": None,
        "line": None,
    }

    message_lines = []
    file_line_pattern = re.compile(r"at\s+(?:\S+\s+)?\(([^:]+):(\d+):\d+\)")

    for i in range(start_idx, min(start_idx + 30, len(lines))):
        line = lines[i]
        stripped = line.strip()

        # Stop at next test or empty section
        if (
            stripped.startswith("●")
            or stripped.startswith("PASS")
            or stripped.startswith("FAIL")
        ):
            break

        # Check for error type
        if stripped.startswith("Error:") or stripped.startswith("TypeError:"):
            parts = stripped.split(":", 1)
            result["error_type"] = parts[0]
            if len(parts) > 1:
                message_lines.append(parts[1].strip())
            continue

        # Check for expect() assertion failures
        if "expect(" in stripped and "received" in stripped.lower():
            result["error_type"] = "AssertionError"
            message_lines.append(stripped)
            continue

        # Check for Expected/Received pattern
        if stripped.startswith("Expected:") or stripped.startswith("Received:"):
            message_lines.append(stripped)
            continue

        # Check for file:line in stack trace
        file_match = file_line_pattern.search(line)
        if file_match and not result["file"]:
            result["file"] = file_match.group(1)
            result["line"] = int(file_match.group(2))

        # Collect message lines (skip stack traces)
        if (
            stripped
            and not stripped.startswith("at ")
            and not stripped.startswith("│")
        ):
            message_lines.append(stripped)

    result["message"] = " ".join(message_lines[:5])
    return result


def extract_package_from_path(file_path):
    """
    Extract package name from file path.
    """
    parts = file_path.replace("\\", "/").split("/")

    for pkg_dir in ["packages_mjs", "packages-mjs"]:
        if pkg_dir in parts:
            idx = parts.index(pkg_dir)
            if idx + 1 < len(parts):
                return f"@internal/{parts[idx + 1]}"

    for app_dir in ["fastify_apps", "fastify-apps"]:
        if app_dir in parts:
            idx = parts.index(app_dir)
            if idx + 1 < len(parts):
                return f"@internal/{parts[idx + 1]}"

    return "unknown"


def process_log(mode, content=None):
    """
    Process log file based on mode (build_log or test_log).
    """
    if mode not in CONFIG:
        print(f"Error: Unknown mode '{mode}'. Use 'build_log' or 'test_log'.")
        sys.exit(1)

    config = CONFIG[mode]
    log_file_path = config["input"]
    output_file_path = config["output"]

    # Use provided content or read from file
    if content is None:
        try:
            with open(log_file_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: Log file not found at {log_file_path}")
            sys.exit(1)

    print(f"Detected mode: {mode}")
    print(f"Processing: {log_file_path}")

    # Parse based on mode
    if mode == "build_log":
        errors = parse_typescript_build_errors(content)
    else:  # test_log
        errors = parse_jest_test_errors(content)

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
            error.get("error_code", ""),
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

    # Print summary by project
    by_project = {}
    for error in errors:
        pkg = error.get("project", "unknown")
        by_project[pkg] = by_project.get(pkg, 0) + 1

    if by_project:
        print("\nBy project:")
        for pkg, count in sorted(by_project.items(), key=lambda x: -x[1]):
            print(f"  {pkg}: {count}")


def show_help():
    """Show usage help."""
    print(__doc__)
    print("\nCommands:")
    print("  (no args)  - Auto-detect based on most recent log file")
    print("  build_log  - Parse pnpm/TypeScript build errors")
    print("               Input:  logs/pnpm-build-error.log")
    print("               Output: logs/pnpm-build-error.jsonl")
    print("")
    print("  test_log   - Parse pnpm/Jest test failures")
    print("               Input:  logs/pnpm-test-error.log")
    print("               Output: logs/pnpm-test-error.jsonl")


def main():
    # Handle explicit mode argument
    if len(sys.argv) >= 2:
        command = sys.argv[1]

        if command in ["--help", "-h", "help"]:
            show_help()
            sys.exit(0)

        if command in ["build_log", "test_log"]:
            process_log(command)
            return
        else:
            print(f"Error: Unknown command '{command}'")
            show_help()
            sys.exit(1)

    # No arguments - auto-detect mode
    mode, content = auto_detect_mode()

    if mode is None:
        print("Error: No log files found.")
        print("Expected one of:")
        print(f"  - {CONFIG['build_log']['input']}")
        print(f"  - {CONFIG['test_log']['input']}")
        print("\nRun 'pnpm build:log' or 'pnpm test:log' first to generate logs.")
        sys.exit(1)

    process_log(mode, content)


if __name__ == "__main__":
    main()
