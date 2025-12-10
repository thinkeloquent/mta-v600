#!/usr/bin/env python3
"""
Scanner to find hardcoded sensitive test data across the codebase.

Usage:
    python .bin/find-sensitive-test-data.py [--format json|text|md] [--output FILE]
    python .bin/find-sensitive-test-data.py --scan-dirs packages_mjs packages_py

Detects:
    - Email addresses
    - Password assignments
    - API keys and tokens
    - Base64 encoded credentials
    - Bearer/Basic auth tokens
    - AWS access keys
    - Connection strings
    - Credit card numbers
    - Phone numbers
    - SSN patterns
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional


class Match(NamedTuple):
    """A single match of sensitive data."""
    file: str
    line_number: int
    line_content: str
    category: str
    pattern_name: str
    matched_value: str


# Regex patterns for detecting sensitive data
PATTERNS = {
    "credentials": {
        "email": r"['\"]([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})['\"]",
        "password_assignment": r"(?:password|passwd|pwd)\s*[:=]\s*['\"]([^'\"]{4,})['\"]",
        "username_assignment": r"(?:username|user)\s*[:=]\s*['\"]([^'\"]{2,})['\"]",
    },
    "tokens": {
        "api_key": r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
        "api_token": r"(?:api[_-]?token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
        "bearer_token": r"['\"]Bearer\s+([A-Za-z0-9._-]+)['\"]",
        "bearer_header": r"Bearer\s+([A-Za-z0-9._-]{10,})",
        "basic_auth": r"['\"]Basic\s+([A-Za-z0-9+/=]{10,})['\"]",
        "basic_header": r"Basic\s+([A-Za-z0-9+/=]{10,})",
        "jwt_token": r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
        "oauth_token": r"(?:oauth[_-]?token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
        "x_api_key": r"['\"]?[xX]-[aA][pP][iI]-[kK][eE][yY]['\"]?\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
    },
    "aws": {
        "access_key_id": r"AKIA[0-9A-Z]{16}",
        "secret_access_key": r"(?:aws[_-]?secret|secret[_-]?access[_-]?key)\s*[:=]\s*['\"]([A-Za-z0-9/+=]{40})['\"]",
    },
    "pii": {
        "credit_card": r"\b(4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
        "ssn": r"\b(\d{3}-\d{2}-\d{4})\b",
        "phone_us": r"['\"](\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})['\"]",
    },
    "urls": {
        "connection_string": r"(postgres|mysql|redis|mongodb)://[^\s'\"]+",
        "base_url": r"(?:base[_-]?url)\s*[:=]\s*['\"]([^'\"]+)['\"]",
        "proxy_url": r"(?:proxy[_-]?url|http[s]?_proxy)\s*[:=]\s*['\"]([^'\"]+)['\"]",
    },
    "base64": {
        "base64_credential": r"['\"]([A-Za-z0-9+/]{20,}={0,2})['\"]",  # Long base64 strings
    }
}

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".mjs", ".ts", ".mts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml"
}

# Directories to exclude
EXCLUDE_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv",
    "dist", "build", ".next", ".cache", "coverage",
    "__STAGE__", "__SPECS__", "__REVIEW__", "__BACKUP__"
}

# Files to exclude
EXCLUDE_FILES = {
    "package-lock.json", "pnpm-lock.yaml", "poetry.lock",
    "sensitive-data.yaml"  # Exclude the target file itself
}


def should_scan_file(path: Path) -> bool:
    """Check if a file should be scanned."""
    # Check extension
    if path.suffix.lower() not in SCANNABLE_EXTENSIONS:
        return False

    # Check excluded directories
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return False

    # Check excluded files
    if path.name in EXCLUDE_FILES:
        return False

    return True


def is_test_file(path: Path) -> bool:
    """Check if a file is a test file."""
    name = path.name.lower()
    parts = [p.lower() for p in path.parts]

    # Check filename patterns
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name.endswith(".test.mjs") or name.endswith(".test.ts"):
        return True
    if name.endswith(".spec.mjs") or name.endswith(".spec.ts"):
        return True
    if name == "conftest.py":
        return True

    # Check directory patterns
    if "tests" in parts or "test" in parts:
        return True
    if any(p.startswith("tests_") for p in parts):
        return True

    return False


def scan_file(file_path: Path, test_files_only: bool = True) -> List[Match]:
    """Scan a single file for sensitive data patterns."""
    if test_files_only and not is_test_file(file_path):
        return []

    matches = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            for category, patterns in PATTERNS.items():
                for pattern_name, pattern in patterns.items():
                    for match in re.finditer(pattern, line, re.IGNORECASE):
                        matched_value = match.group(1) if match.lastindex else match.group(0)

                        # Filter out false positives
                        if is_false_positive(matched_value, pattern_name):
                            continue

                        matches.append(Match(
                            file=str(file_path),
                            line_number=line_num,
                            line_content=line.strip()[:200],  # Truncate long lines
                            category=category,
                            pattern_name=pattern_name,
                            matched_value=matched_value[:50] + "..." if len(matched_value) > 50 else matched_value
                        ))

    except Exception as e:
        print(f"Error scanning {file_path}: {e}", file=sys.stderr)

    return matches


def is_false_positive(value: str, pattern_name: str) -> bool:
    """Filter out common false positives."""
    # Skip very short values
    if len(value) < 4:
        return True

    # Skip common test placeholders
    false_positives = {
        "example.com", "test.com", "localhost",
        "xxx", "yyy", "zzz", "abc", "123",
        "password", "secret", "token", "key",
        "your-", "my-", "sample-", "example-",
        "placeholder", "changeme", "fixme"
    }

    value_lower = value.lower()
    for fp in false_positives:
        if value_lower == fp or value_lower.startswith(fp):
            return True

    # Skip import statements
    if "@" in value and "/" in value:  # npm package patterns
        return True

    return False


def scan_directory(
    directory: Path,
    test_files_only: bool = True,
    include_patterns: Optional[List[str]] = None
) -> List[Match]:
    """Scan a directory recursively for sensitive data."""
    all_matches = []

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue

        if not should_scan_file(file_path):
            continue

        # Apply include patterns if specified
        if include_patterns:
            match = False
            for pattern in include_patterns:
                if file_path.match(pattern):
                    match = True
                    break
            if not match:
                continue

        matches = scan_file(file_path, test_files_only=test_files_only)
        all_matches.extend(matches)

    return all_matches


def format_text(matches: List[Match]) -> str:
    """Format matches as plain text."""
    if not matches:
        return "No sensitive data found."

    lines = [
        f"Found {len(matches)} potential sensitive data occurrences:",
        "=" * 60,
        ""
    ]

    # Group by category
    by_category: Dict[str, List[Match]] = {}
    for match in matches:
        if match.category not in by_category:
            by_category[match.category] = []
        by_category[match.category].append(match)

    for category, cat_matches in sorted(by_category.items()):
        lines.append(f"\n[{category.upper()}] ({len(cat_matches)} matches)")
        lines.append("-" * 40)

        for m in cat_matches:
            lines.append(f"  {m.file}:{m.line_number}")
            lines.append(f"    Pattern: {m.pattern_name}")
            lines.append(f"    Value: {m.matched_value}")
            lines.append(f"    Line: {m.line_content}")
            lines.append("")

    return "\n".join(lines)


def format_markdown(matches: List[Match]) -> str:
    """Format matches as markdown."""
    if not matches:
        return "# Sensitive Data Scan Results\n\nNo sensitive data found."

    lines = [
        "# Sensitive Data Scan Results",
        "",
        f"Found **{len(matches)}** potential sensitive data occurrences.",
        "",
    ]

    # Group by category
    by_category: Dict[str, List[Match]] = {}
    for match in matches:
        if match.category not in by_category:
            by_category[match.category] = []
        by_category[match.category].append(match)

    for category, cat_matches in sorted(by_category.items()):
        lines.append(f"## {category.title()} ({len(cat_matches)} matches)")
        lines.append("")
        lines.append("| File | Line | Pattern | Value |")
        lines.append("|------|------|---------|-------|")

        for m in cat_matches:
            file_short = m.file.replace("/Users/Shared/autoload/mta-v600/", "")
            lines.append(f"| `{file_short}` | {m.line_number} | {m.pattern_name} | `{m.matched_value}` |")

        lines.append("")

    return "\n".join(lines)


def format_json(matches: List[Match]) -> str:
    """Format matches as JSON."""
    return json.dumps(
        {
            "total": len(matches),
            "matches": [m._asdict() for m in matches]
        },
        indent=2
    )


def main():
    parser = argparse.ArgumentParser(
        description="Scan for hardcoded sensitive test data in the codebase"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json", "md"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--scan-dirs",
        nargs="+",
        default=["packages_mjs", "packages_py"],
        help="Directories to scan (default: packages_mjs packages_py)"
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Scan all files, not just test files"
    )
    parser.add_argument(
        "--include",
        nargs="+",
        help="Only include files matching these glob patterns"
    )

    args = parser.parse_args()

    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    # Scan directories
    all_matches = []
    for dir_name in args.scan_dirs:
        scan_path = project_root / dir_name
        if not scan_path.exists():
            print(f"Warning: Directory not found: {scan_path}", file=sys.stderr)
            continue

        print(f"Scanning {scan_path}...", file=sys.stderr)
        matches = scan_directory(
            scan_path,
            test_files_only=not args.all_files,
            include_patterns=args.include
        )
        all_matches.extend(matches)

    # Format output
    if args.format == "json":
        output = format_json(all_matches)
    elif args.format == "md":
        output = format_markdown(all_matches)
    else:
        output = format_text(all_matches)

    # Write output
    if args.output:
        Path(args.output).write_text(output)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Return non-zero if matches found (for CI usage)
    return 1 if all_matches else 0


if __name__ == "__main__":
    sys.exit(main())
