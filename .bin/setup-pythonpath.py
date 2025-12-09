#!/usr/bin/env python3
"""
Sets up PYTHONPATH with all Python modules for local development.

Usage:
    eval $(python .bin/setup-pythonpath.py)           # Set PYTHONPATH in current shell
    python .bin/setup-pythonpath.py --print           # Just print paths (no export)
    source <(python .bin/setup-pythonpath.py --bash)  # Bash-sourceable output
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def get_script_root() -> Path:
    """Get the monorepo root directory."""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent


def find_python_packages(packages_dir: Path) -> list[Path]:
    """Find all valid Python packages with pyproject.toml."""
    packages = []
    if not packages_dir.exists():
        return packages

    for item in sorted(packages_dir.iterdir()):
        if item.is_dir() and not item.name.startswith(('.', '_')):
            if (item / 'pyproject.toml').exists():
                packages.append(item)
    return packages


def get_pythonpath_entries(root: Path) -> list[Path]:
    """Get all PYTHONPATH entries for packages_py/*/src and fastapi_apps/*."""
    entries = []

    # packages_py/*/src
    for pkg in find_python_packages(root / 'packages_py'):
        src_dir = pkg / 'src'
        if src_dir.exists():
            entries.append(src_dir)

    # fastapi_apps/* (direct, not /src)
    for app in find_python_packages(root / 'fastapi_apps'):
        entries.append(app)

    return entries


def main():
    parser = argparse.ArgumentParser(description='Setup PYTHONPATH for local development')
    parser.add_argument('--print', dest='print_only', action='store_true',
                        help='Print paths only (no export statement)')
    parser.add_argument('--bash', action='store_true',
                        help='Output bash-sourceable export statement')
    args = parser.parse_args()

    root = get_script_root()
    entries = get_pythonpath_entries(root)

    # Build PYTHONPATH string
    existing = os.environ.get('PYTHONPATH', '')
    paths = [str(p) for p in entries]
    if existing:
        paths.append(existing)
    pythonpath = ':'.join(paths)

    if args.print_only:
        print("PYTHONPATH entries:")
        for entry in entries:
            print(f"  - {entry}")
        print(f"\nTotal: {len(entries)} paths")
    elif args.bash:
        print(f'export PYTHONPATH="{pythonpath}"')
        print(f'echo "PYTHONPATH configured with {len(entries)} paths"', file=sys.stderr)
    else:
        # Default: output for eval
        print(f'export PYTHONPATH="{pythonpath}"')
        print(f"\n# PYTHONPATH configured:", file=sys.stderr)
        for entry in entries:
            print(f"#   - {entry}", file=sys.stderr)
        print(f"# Total: {len(entries)} paths", file=sys.stderr)


if __name__ == '__main__':
    main()
