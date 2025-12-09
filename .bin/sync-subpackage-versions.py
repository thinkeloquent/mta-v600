#!/usr/bin/env python3
"""
Sync sub-package dependencies to use flexible versions.

This script updates sub-packages (packages_py/*, fastapi_apps/*) to use
flexible version specifiers ("*" or ">=0") for dependencies that are
defined in the root pyproject.toml.

The root pyproject.toml remains the source of truth for pinned versions.
Sub-packages defer to constraints.txt at install time.

Usage:
    # Update all sub-packages to use flexible versions
    python .bin/sync-subpackage-versions.py

    # Update specific sub-package
    python .bin/sync-subpackage-versions.py --package packages_py/fetch_client

    # Preview changes without writing
    python .bin/sync-subpackage-versions.py --dry-run

    # Use >=0 instead of * (more compatible with some tools)
    python .bin/sync-subpackage-versions.py --version-style floor
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Literal

# Try tomllib (Python 3.11+) or fall back to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("Error: tomllib (Python 3.11+) or tomli package required.")
        print("Install with: pip install tomli")
        sys.exit(1)

# For writing TOML, we need tomlkit to preserve formatting
try:
    import tomlkit
except ImportError:
    tomlkit = None


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_root_dependencies(root: Path) -> set[str]:
    """
    Get the set of dependency names defined in root pyproject.toml.

    Returns:
        Set of normalized package names (lowercase, hyphens).
    """
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"Root pyproject.toml not found at {pyproject_path}")

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps = set()
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})

    for name, spec in poetry_deps.items():
        if name.lower() == "python":
            continue
        # Skip local path dependencies
        if isinstance(spec, dict) and "path" in spec:
            continue
        # Normalize name
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        deps.add(normalized)

    # Also check dev dependencies
    dev_deps = (
        data.get("tool", {})
        .get("poetry", {})
        .get("group", {})
        .get("dev", {})
        .get("dependencies", {})
    )
    for name, spec in dev_deps.items():
        if isinstance(spec, dict) and "path" in spec:
            continue
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        deps.add(normalized)

    return deps


def find_sub_packages(root: Path) -> list[Path]:
    """Find all sub-package directories with pyproject.toml."""
    packages = []

    # Directories to ignore
    ignore_dirs = {
        "__STAGE__",
        "__SPECS__",
        "__REVIEW__",
        "__BACKUP__",
        "__pycache__",
        ".git",
        "node_modules",
        ".venv",
        "dist",
        "build",
    }

    def should_ignore(path: Path) -> bool:
        """Check if path or any parent should be ignored."""
        for part in path.parts:
            if part in ignore_dirs or part.startswith("."):
                return True
        return False

    # Check packages_py directory
    packages_py = root / "packages_py"
    if packages_py.exists():
        for pkg_dir in packages_py.iterdir():
            if pkg_dir.is_dir() and not should_ignore(pkg_dir) and (pkg_dir / "pyproject.toml").exists():
                packages.append(pkg_dir)

    # Check fastapi_apps directory
    fastapi_apps = root / "fastapi_apps"
    if fastapi_apps.exists():
        for app_dir in fastapi_apps.iterdir():
            if app_dir.is_dir() and not should_ignore(app_dir) and (app_dir / "pyproject.toml").exists():
                packages.append(app_dir)

    return sorted(packages)


def update_pyproject_toml(
    pkg_path: Path,
    root_deps: set[str],
    version_style: Literal["star", "floor"],
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """
    Update a sub-package's pyproject.toml to use flexible versions.

    Args:
        pkg_path: Path to the package directory.
        root_deps: Set of dependency names defined in root.
        version_style: "star" for "*", "floor" for ">=0".
        dry_run: If True, don't write changes.

    Returns:
        Tuple of (number of changes, list of change descriptions).
    """
    pyproject_path = pkg_path / "pyproject.toml"

    if tomlkit is None:
        print("Warning: tomlkit not installed. Using simple replacement.")
        return update_pyproject_toml_simple(
            pyproject_path, root_deps, version_style, dry_run
        )

    with open(pyproject_path, "r") as f:
        content = f.read()

    doc = tomlkit.parse(content)
    changes = []
    change_count = 0

    flexible_version = "*" if version_style == "star" else ">=0"

    # Update dependencies
    deps = doc.get("tool", {}).get("poetry", {}).get("dependencies", {})
    if deps:
        for name in list(deps.keys()):
            if name.lower() == "python":
                continue

            normalized = re.sub(r"[-_.]+", "-", name).lower()

            # If this dep is in root, make it flexible
            if normalized in root_deps:
                current = deps[name]
                # Skip if already flexible
                if current in ("*", ">=0"):
                    continue
                # Skip path dependencies
                if isinstance(current, dict) and "path" in current:
                    continue

                deps[name] = flexible_version
                changes.append(f"  {name}: {current} -> {flexible_version}")
                change_count += 1

    if changes and not dry_run:
        with open(pyproject_path, "w") as f:
            f.write(tomlkit.dumps(doc))

    return change_count, changes


def update_pyproject_toml_simple(
    pyproject_path: Path,
    root_deps: set[str],
    version_style: Literal["star", "floor"],
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """
    Simple regex-based update for pyproject.toml (fallback if tomlkit not available).
    """
    with open(pyproject_path, "r") as f:
        content = f.read()

    changes = []
    change_count = 0
    flexible_version = "*" if version_style == "star" else ">=0"

    lines = content.split("\n")
    new_lines = []

    for line in lines:
        # Match dependency lines like: httpx = "^0.28.0"
        match = re.match(r'^(\s*)([a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"(.*)$', line)
        if match:
            indent, name, version, rest = match.groups()
            normalized = re.sub(r"[-_.]+", "-", name).lower()

            if normalized in root_deps and version not in ("*", ">=0"):
                changes.append(f"  {name}: {version} -> {flexible_version}")
                change_count += 1
                new_lines.append(f'{indent}{name} = "{flexible_version}"{rest}')
                continue

        new_lines.append(line)

    if changes and not dry_run:
        with open(pyproject_path, "w") as f:
            f.write("\n".join(new_lines))

    return change_count, changes


def update_requirements_txt(
    pkg_path: Path,
    root_deps: set[str],
    root: Path,
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """
    Update a sub-package's requirements.txt to reference constraints.txt.

    Args:
        pkg_path: Path to the package directory.
        root_deps: Set of dependency names defined in root.
        root: Project root path.
        dry_run: If True, don't write changes.

    Returns:
        Tuple of (number of changes, list of change descriptions).
    """
    req_path = pkg_path / "requirements.txt"

    if not req_path.exists():
        return 0, []

    with open(req_path, "r") as f:
        content = f.read()

    lines = content.split("\n")
    changes = []
    change_count = 0

    # Calculate relative path to constraints.txt
    rel_path = Path("..") / ".." / "constraints.txt"
    try:
        rel_path = pkg_path.relative_to(root)
        depth = len(rel_path.parts)
        rel_path = Path("/".join([".."] * depth)) / "constraints.txt"
    except ValueError:
        pass

    # Check if constraints reference already exists
    has_constraints = any(
        line.strip().startswith("-c") and "constraints.txt" in line for line in lines
    )

    new_lines = []

    # Add constraints reference at the top if not present
    if not has_constraints:
        new_lines.append(f"# Use root constraints for version pinning")
        new_lines.append(f"-c {rel_path}")
        new_lines.append("")
        changes.append(f"  Added: -c {rel_path}")
        change_count += 1

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and comments at the start
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Skip existing constraint references
        if stripped.startswith("-c"):
            new_lines.append(line)
            continue

        # Parse requirement line
        # Match: package==1.0.0, package>=1.0.0, package~=1.0.0, package
        match = re.match(r"^([a-zA-Z0-9_-]+)([<>=!~]+.+)?$", stripped)
        if match:
            name, version = match.groups()
            normalized = re.sub(r"[-_.]+", "-", name).lower()

            # If this dep is in root, remove version specifier
            if normalized in root_deps and version:
                changes.append(f"  {name}{version} -> {name}")
                change_count += 1
                new_lines.append(name)
                continue

        new_lines.append(line)

    if changes and not dry_run:
        with open(req_path, "w") as f:
            f.write("\n".join(new_lines))

    return change_count, changes


def main():
    parser = argparse.ArgumentParser(
        description="Sync sub-package dependencies to use flexible versions"
    )
    parser.add_argument(
        "--package",
        "-p",
        type=Path,
        help="Update specific package only",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview changes without writing",
    )
    parser.add_argument(
        "--version-style",
        choices=["star", "floor"],
        default="star",
        help='Use "*" (star) or ">=0" (floor) for flexible versions (default: star)',
    )
    parser.add_argument(
        "--skip-requirements",
        action="store_true",
        help="Skip updating requirements.txt files",
    )

    args = parser.parse_args()

    root = get_project_root()

    try:
        root_deps = get_root_dependencies(root)
        print(f"Found {len(root_deps)} dependencies in root pyproject.toml")

        if args.package:
            packages = [args.package]
        else:
            packages = find_sub_packages(root)

        print(f"Found {len(packages)} sub-packages to check")
        print()

        total_changes = 0

        for pkg_path in packages:
            pkg_name = pkg_path.relative_to(root)
            pyproject_changes, pyproject_msgs = update_pyproject_toml(
                pkg_path, root_deps, args.version_style, args.dry_run
            )

            req_changes, req_msgs = (0, [])
            if not args.skip_requirements:
                req_changes, req_msgs = update_requirements_txt(
                    pkg_path, root_deps, root, args.dry_run
                )

            if pyproject_changes or req_changes:
                print(f"{pkg_name}:")
                if pyproject_changes:
                    print(f"  pyproject.toml ({pyproject_changes} changes):")
                    for msg in pyproject_msgs:
                        print(f"  {msg}")
                if req_changes:
                    print(f"  requirements.txt ({req_changes} changes):")
                    for msg in req_msgs:
                        print(f"  {msg}")
                print()
                total_changes += pyproject_changes + req_changes

        if args.dry_run:
            print(f"Dry run: {total_changes} changes would be made")
        else:
            print(f"Updated {total_changes} dependency versions")

        if total_changes > 0:
            print()
            print("Next steps:")
            print("  1. Run 'make -f Makefile.poetry lock' to update poetry.lock")
            print("  2. Run 'make -f Makefile.poetry constraints' to generate constraints.txt")
            print("  3. Commit the changes")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
