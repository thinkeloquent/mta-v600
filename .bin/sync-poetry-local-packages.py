#!/usr/bin/env python3
"""
python .bin/sync-poetry-local-packages.py

Scans packages_py/ directory and updates pyproject.toml to include all
local Python packages as editable dependencies.

Usage:
    python .bin/sync-poetry-local-packages.py [--dry-run]

Options:
    --dry-run    Show what would be changed without modifying files
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def get_script_root() -> Path:
    """Get the monorepo root directory."""
    script_path = Path(__file__).resolve()
    # .bin is directly under root
    return script_path.parent.parent


def find_python_packages(packages_dir: Path) -> list[str]:
    """
    Find all valid Python packages in packages_py/.

    A valid package has a pyproject.toml file.
    """
    packages = []

    if not packages_dir.exists():
        return packages

    for item in sorted(packages_dir.iterdir()):
        if item.is_dir() and not item.name.startswith(('.', '_')):
            # Check for pyproject.toml (Poetry/PEP 517 package)
            if (item / 'pyproject.toml').exists():
                packages.append(item.name)
            # Also check for setup.py (legacy)
            elif (item / 'setup.py').exists():
                packages.append(item.name)

    return packages


def parse_existing_local_packages(content: str) -> dict[str, str]:
    """
    Parse existing local package entries from pyproject.toml.

    Returns dict of package_name -> full line
    """
    packages = {}

    # Match lines like: package-name = {path = "packages_py/package_name", develop = true}
    pattern = r'^([\w-]+)\s*=\s*\{path\s*=\s*"packages_py/[^"]+",\s*develop\s*=\s*true\}'

    for line in content.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            pkg_name = match.group(1)
            packages[pkg_name] = line.strip()

    return packages


def folder_to_package_name(folder_name: str) -> str:
    """Convert folder name (with underscores) to package name (with hyphens)."""
    return folder_name.replace('_', '-')


def generate_package_entry(folder_name: str) -> str:
    """Generate a pyproject.toml entry for a local package."""
    pkg_name = folder_to_package_name(folder_name)
    return f'{pkg_name} = {{path = "packages_py/{folder_name}", develop = true}}'


def update_pyproject_toml(
    pyproject_path: Path,
    packages: list[str],
    dry_run: bool = False
) -> tuple[bool, list[str], list[str]]:
    """
    Update pyproject.toml with local packages.

    Returns:
        (changed, added, removed) - whether file changed, packages added, packages removed
    """
    content = pyproject_path.read_text()

    # Find existing local packages
    existing = parse_existing_local_packages(content)
    existing_names = set(existing.keys())
    desired_names = set(folder_to_package_name(p) for p in packages)

    # Calculate diff
    to_add = sorted(desired_names - existing_names)
    to_remove = sorted(existing_names - desired_names)

    if not to_add and not to_remove:
        return False, [], []

    # Find the local packages section
    # Look for the comment marker
    marker = "# Local packages"

    if marker not in content:
        print(f"ERROR: Could not find marker '{marker}' in pyproject.toml")
        print("Please add this comment before the local packages section.")
        sys.exit(1)

    # Split content at marker
    before_marker, after_marker = content.split(marker, 1)

    # Find where the local packages section ends (next section or empty lines)
    lines_after = after_marker.split('\n')

    # Skip the marker line itself (empty after split)
    section_end_idx = 1
    for i, line in enumerate(lines_after[1:], start=1):
        stripped = line.strip()
        # End of section: empty line followed by [section] or end of file
        if stripped == '':
            # Check if next non-empty line is a section header
            for j in range(i + 1, len(lines_after)):
                next_stripped = lines_after[j].strip()
                if next_stripped:
                    if next_stripped.startswith('['):
                        section_end_idx = i
                    break
            if section_end_idx != 1:
                break
        elif stripped.startswith('['):
            section_end_idx = i
            break

    # Build new local packages section
    new_entries = []
    for pkg in sorted(packages):
        new_entries.append(generate_package_entry(pkg))

    # Reconstruct content
    new_content = (
        before_marker +
        marker + '\n' +
        '\n'.join(new_entries) + '\n' +
        '\n'.join(lines_after[section_end_idx:])
    )

    # Clean up multiple blank lines
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    if not dry_run:
        pyproject_path.write_text(new_content)

    return True, to_add, to_remove


def main():
    parser = argparse.ArgumentParser(
        description='Sync packages_py/ with pyproject.toml local dependencies'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    args = parser.parse_args()

    root = get_script_root()
    packages_dir = root / 'packages_py'
    pyproject_path = root / 'pyproject.toml'

    print(f"Scanning: {packages_dir}")
    print(f"Target:   {pyproject_path}")
    print()

    if not packages_dir.exists():
        print(f"ERROR: packages_py directory not found at {packages_dir}")
        sys.exit(1)

    if not pyproject_path.exists():
        print(f"ERROR: pyproject.toml not found at {pyproject_path}")
        sys.exit(1)

    # Find all packages
    packages = find_python_packages(packages_dir)

    print(f"Found {len(packages)} Python packages:")
    for pkg in packages:
        print(f"  - {pkg}")
    print()

    # Update pyproject.toml
    changed, added, removed = update_pyproject_toml(
        pyproject_path,
        packages,
        dry_run=args.dry_run
    )

    if not changed:
        print("pyproject.toml is already up to date.")
        return

    if added:
        print(f"Added {len(added)} package(s):")
        for pkg in added:
            print(f"  + {pkg}")

    if removed:
        print(f"Removed {len(removed)} package(s):")
        for pkg in removed:
            print(f"  - {pkg}")

    print()

    if args.dry_run:
        print("DRY RUN: No changes made. Run without --dry-run to apply.")
    else:
        print("pyproject.toml updated successfully.")
        print()
        print("Next steps:")
        print("  1. Run 'poetry lock' to update the lock file")
        print("  2. Run 'poetry install' to install the packages")


if __name__ == '__main__':
    main()
