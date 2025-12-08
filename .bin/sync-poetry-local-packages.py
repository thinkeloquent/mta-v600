#!/usr/bin/env python3
"""
python .bin/sync-poetry-local-packages.py

Scans packages_py/ and fastapi_apps/ directories and updates pyproject.toml
to include all local Python packages as editable dependencies.

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
    Find all valid Python packages in a directory.

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


# Type alias for package info: (folder_name, base_dir)
PackageInfo = tuple[str, str]


def find_all_packages(root: Path) -> list[PackageInfo]:
    """
    Find all Python packages in packages_py/ and fastapi_apps/.

    Returns list of (folder_name, base_dir) tuples.
    """
    packages: list[PackageInfo] = []

    # Scan packages_py/
    packages_py_dir = root / 'packages_py'
    for pkg in find_python_packages(packages_py_dir):
        packages.append((pkg, 'packages_py'))

    # Scan fastapi_apps/
    fastapi_apps_dir = root / 'fastapi_apps'
    for pkg in find_python_packages(fastapi_apps_dir):
        packages.append((pkg, 'fastapi_apps'))

    return packages


def parse_existing_local_packages(content: str) -> dict[str, str]:
    """
    Parse existing local package entries from pyproject.toml.

    Returns dict of package_name -> full line
    """
    packages = {}

    # Match lines like: package-name = {path = "packages_py/package_name", develop = true}
    # or: package-name = {path = "fastapi_apps/package_name", develop = true}
    pattern = r'^([\w-]+)\s*=\s*\{path\s*=\s*"(?:packages_py|fastapi_apps)/[^"]+",\s*develop\s*=\s*true\}'

    for line in content.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            pkg_name = match.group(1)
            packages[pkg_name] = line.strip()

    return packages


def folder_to_package_name(folder_name: str) -> str:
    """Convert folder name (with underscores) to package name (with hyphens)."""
    return folder_name.replace('_', '-')


def read_package_name_from_pyproject(package_dir: Path) -> str | None:
    """Read the package name from a package's pyproject.toml.

    Normalizes underscores to hyphens (pip/poetry convention).
    """
    pyproject_file = package_dir / 'pyproject.toml'
    if not pyproject_file.exists():
        return None

    content = pyproject_file.read_text()
    # Match: name = "package-name" or name = 'package-name'
    match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if match:
        # Normalize underscores to hyphens (pip/poetry convention)
        return match.group(1).replace('_', '-')
    return None


def generate_package_entry(folder_name: str, base_dir: str, root: Path) -> str:
    """Generate a pyproject.toml entry for a local package."""
    # Try to read the actual package name from the package's pyproject.toml
    package_dir = root / base_dir / folder_name
    pkg_name = read_package_name_from_pyproject(package_dir)

    # Fallback to folder name conversion if we can't read it
    if not pkg_name:
        pkg_name = folder_to_package_name(folder_name)

    return f'{pkg_name} = {{path = "{base_dir}/{folder_name}", develop = true}}'


def update_pyproject_toml(
    pyproject_path: Path,
    packages: list[PackageInfo],
    root: Path,
    dry_run: bool = False
) -> tuple[bool, list[str], list[str]]:
    """
    Update pyproject.toml with local packages.

    Args:
        packages: List of (folder_name, base_dir) tuples
        root: Monorepo root path

    Returns:
        (changed, added, removed) - whether file changed, packages added, packages removed
    """
    content = pyproject_path.read_text()

    # Find existing local packages
    existing = parse_existing_local_packages(content)
    existing_names = set(existing.keys())

    # Get actual package names from their pyproject.toml files
    def get_pkg_name(folder_name: str, base_dir: str) -> str:
        pkg_name = read_package_name_from_pyproject(root / base_dir / folder_name)
        return pkg_name if pkg_name else folder_to_package_name(folder_name)

    desired_names = set(get_pkg_name(f, b) for f, b in packages)

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
    # Group by base_dir for organized output
    packages_py_entries = []
    fastapi_apps_entries = []

    for folder_name, base_dir in sorted(packages, key=lambda x: (x[1], x[0])):
        entry = generate_package_entry(folder_name, base_dir, root)
        if base_dir == 'packages_py':
            packages_py_entries.append(entry)
        else:
            fastapi_apps_entries.append(entry)

    new_entries = packages_py_entries
    if fastapi_apps_entries:
        new_entries.append('')
        new_entries.append('# FastAPI apps')
        new_entries.extend(fastapi_apps_entries)

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
        description='Sync packages_py/ and fastapi_apps/ with pyproject.toml local dependencies'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    args = parser.parse_args()

    root = get_script_root()
    pyproject_path = root / 'pyproject.toml'

    print(f"Scanning: {root / 'packages_py'}")
    print(f"Scanning: {root / 'fastapi_apps'}")
    print(f"Target:   {pyproject_path}")
    print()

    if not pyproject_path.exists():
        print(f"ERROR: pyproject.toml not found at {pyproject_path}")
        sys.exit(1)

    # Find all packages from both directories
    packages = find_all_packages(root)

    # Group for display
    packages_py = [(f, b) for f, b in packages if b == 'packages_py']
    fastapi_apps = [(f, b) for f, b in packages if b == 'fastapi_apps']

    print(f"Found {len(packages_py)} packages in packages_py/:")
    for pkg, _ in packages_py:
        print(f"  - {pkg}")

    if fastapi_apps:
        print(f"\nFound {len(fastapi_apps)} apps in fastapi_apps/:")
        for pkg, _ in fastapi_apps:
            print(f"  - {pkg}")
    print()

    # Update pyproject.toml
    changed, added, removed = update_pyproject_toml(
        pyproject_path,
        packages,
        root,
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
