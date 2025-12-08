#!/usr/bin/env python3
"""
Fix pytest test namespaces by renaming tests/ directories to tests_<package>/.

This script solves the pytest namespace collision issue where multiple packages
have tests/ directories that all get imported as the same 'tests' module.

Usage:
    # Dry run (preview changes)
    python3 .bin/fix_pytest_test_namespaces.py --dry-run

    # Apply changes
    python3 .bin/fix_pytest_test_namespaces.py

    # Revert changes (restore original tests/ names)
    python3 .bin/fix_pytest_test_namespaces.py --revert

What it does:
    1. Cleans __pycache__ and .pytest_cache directories
    2. Updates root pyproject.toml with asyncio_mode and --import-mode=importlib
    3. Renames tests/ -> tests_<package_name>/ for each package
    4. Updates imports to use relative imports (from .conftest import ...)
    5. Adds __init__.py to test dirs for relative imports to work
"""
import os
import re
import sys
import shutil
from pathlib import Path


# Directories to process
PACKAGE_DIRS = [
    "packages_py",
    "fastapi_apps",
]

# Root directory (relative to script location)
ROOT_DIR = Path(__file__).parent.parent


def get_package_name(package_path: Path) -> str:
    """Extract package name from path."""
    return package_path.name


def find_packages_with_tests(base_dir: Path) -> list[tuple[Path, Path]]:
    """Find all packages that have a tests/ directory."""
    packages = []
    if not base_dir.exists():
        return packages

    for item in base_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            tests_dir = item / "tests"
            if tests_dir.exists() and tests_dir.is_dir():
                packages.append((item, tests_dir))

    return packages


def get_new_tests_dir_name(package_name: str) -> str:
    """Generate new tests directory name."""
    return f"tests_{package_name}"


def update_imports_in_file(file_path: Path, dry_run: bool = False) -> bool:
    """Update imports in a Python file to use relative imports for conftest."""
    try:
        content = file_path.read_text()

        # Pattern to match imports from tests.conftest or conftest
        # Convert to relative import (.conftest)
        patterns = [
            # from tests.conftest import X -> from .conftest import X
            (r'from\s+tests\.conftest\s+import', 'from .conftest import'),
            # from tests.conftest.X import -> from .conftest.X import
            (r'from\s+tests\.conftest\.', 'from .conftest.'),
            # from conftest import X -> from .conftest import X (for standalone conftest imports)
            (r'from\s+conftest\s+import', 'from .conftest import'),
        ]

        new_content = content
        changed = False

        for pattern, replacement in patterns:
            new_content, count = re.subn(pattern, replacement, new_content, flags=re.MULTILINE)
            if count > 0:
                changed = True

        if changed and not dry_run:
            file_path.write_text(new_content)

        return changed
    except Exception as e:
        print(f"  Warning: Could not process {file_path}: {e}")
        return False


def remove_init_py(tests_dir: Path, dry_run: bool = False) -> bool:
    """Remove __init__.py from tests directory (modern pytest pattern)."""
    init_file = tests_dir / "__init__.py"
    if init_file.exists():
        if not dry_run:
            init_file.unlink()
        return True
    return False


def add_init_py(tests_dir: Path, dry_run: bool = False) -> bool:
    """Add __init__.py to tests directory for relative imports to work."""
    init_file = tests_dir / "__init__.py"
    if not init_file.exists():
        if not dry_run:
            init_file.write_text("# Test package\n")
        return True
    return False


def rename_tests_directory(package_path: Path, tests_dir: Path, dry_run: bool = False) -> dict:
    """Rename tests/ to tests_<package>/ and update imports."""
    package_name = get_package_name(package_path)
    new_name = get_new_tests_dir_name(package_name)
    new_tests_dir = package_path / new_name

    result = {
        "package": package_name,
        "old_path": str(tests_dir),
        "new_path": str(new_tests_dir),
        "files_updated": [],
        "init_added": False,
        "renamed": False,
    }

    # Skip if already renamed
    if new_tests_dir.exists():
        print(f"  Skipping {package_name}: {new_name}/ already exists")
        return result

    # Update imports in test files to use relative imports
    for py_file in tests_dir.glob("**/*.py"):
        if py_file.name != "conftest.py" and py_file.name != "__init__.py":
            if update_imports_in_file(py_file, dry_run):
                result["files_updated"].append(str(py_file.relative_to(ROOT_DIR)))

    # Add __init__.py for relative imports to work
    if add_init_py(tests_dir, dry_run):
        result["init_added"] = True

    # Rename the directory
    if not dry_run:
        shutil.move(str(tests_dir), str(new_tests_dir))
    result["renamed"] = True

    return result


def revert_tests_directory(package_path: Path, dry_run: bool = False) -> dict:
    """Revert tests_<package>/ back to tests/."""
    package_name = get_package_name(package_path)
    new_name = get_new_tests_dir_name(package_name)
    new_tests_dir = package_path / new_name
    original_tests_dir = package_path / "tests"

    result = {
        "package": package_name,
        "old_path": str(new_tests_dir),
        "new_path": str(original_tests_dir),
        "reverted": False,
    }

    if not new_tests_dir.exists():
        return result

    if original_tests_dir.exists():
        print(f"  Skipping {package_name}: tests/ already exists")
        return result

    if not dry_run:
        shutil.move(str(new_tests_dir), str(original_tests_dir))
    result["reverted"] = True

    return result


def clean_cache_directories(base_dir: Path, dry_run: bool = False) -> dict:
    """Clean __pycache__ and .pytest_cache directories."""
    result = {"pycache_removed": 0, "pytest_cache_removed": 0}

    # Clean __pycache__
    for cache_dir in base_dir.rglob("__pycache__"):
        if cache_dir.is_dir():
            if not dry_run:
                shutil.rmtree(cache_dir, ignore_errors=True)
            result["pycache_removed"] += 1

    # Clean .pytest_cache
    for cache_dir in base_dir.rglob(".pytest_cache"):
        if cache_dir.is_dir():
            if not dry_run:
                shutil.rmtree(cache_dir, ignore_errors=True)
            result["pytest_cache_removed"] += 1

    return result


def update_root_pyproject_toml(root_dir: Path, dry_run: bool = False) -> dict:
    """Update root pyproject.toml with pytest settings for running tests from root."""
    result = {"updated": False, "changes": []}
    pyproject_path = root_dir / "pyproject.toml"

    if not pyproject_path.exists():
        return result

    content = pyproject_path.read_text()

    # Check if asyncio_mode is already set
    if "asyncio_mode" not in content:
        # Find [tool.pytest.ini_options] section and add asyncio_mode
        if "[tool.pytest.ini_options]" in content:
            # Add asyncio_mode after the section header
            new_content = content.replace(
                "[tool.pytest.ini_options]",
                "[tool.pytest.ini_options]\nasyncio_mode = \"auto\""
            )
            if new_content != content:
                result["changes"].append("Added asyncio_mode = \"auto\"")
                if not dry_run:
                    pyproject_path.write_text(new_content)
                result["updated"] = True
                content = new_content

    # Check if --import-mode=importlib is already set
    if "--import-mode=importlib" not in content:
        # Find addopts line and append --import-mode=importlib
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if line.strip().startswith("addopts") and "--import-mode=importlib" not in line:
                # Append to existing addopts
                if line.rstrip().endswith('"'):
                    line = line.rstrip()[:-1] + ' --import-mode=importlib"'
                    result["changes"].append("Added --import-mode=importlib to addopts")
                    result["updated"] = True
            new_lines.append(line)

        if result["updated"] and not dry_run:
            pyproject_path.write_text("\n".join(new_lines))

    return result


def main():
    dry_run = "--dry-run" in sys.argv
    revert = "--revert" in sys.argv

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    mode = "REVERT" if revert else ("DRY RUN" if dry_run else "APPLY")
    print(f"\n{'='*60}")
    print(f"Fix Pytest Test Namespaces - {mode}")
    print(f"{'='*60}\n")

    # Clean cache directories first
    print("Cleaning cache directories...")
    cache_result = clean_cache_directories(ROOT_DIR, dry_run)
    print(f"  Removed {cache_result['pycache_removed']} __pycache__ directories")
    print(f"  Removed {cache_result['pytest_cache_removed']} .pytest_cache directories")
    print()

    # Update root pyproject.toml (only when not reverting)
    pyproject_result = {"updated": False, "changes": []}
    if not revert:
        print("Updating pyproject.toml...")
        pyproject_result = update_root_pyproject_toml(ROOT_DIR, dry_run)
        if pyproject_result["changes"]:
            for change in pyproject_result["changes"]:
                print(f"  {change}")
        else:
            print("  No changes needed (settings already present)")
        print()

    all_results = []

    for pkg_dir_name in PACKAGE_DIRS:
        pkg_dir = ROOT_DIR / pkg_dir_name
        print(f"Processing {pkg_dir_name}/...")

        if revert:
            # Find renamed test directories
            if not pkg_dir.exists():
                continue
            for item in pkg_dir.iterdir():
                if item.is_dir():
                    result = revert_tests_directory(item, dry_run)
                    if result["reverted"]:
                        all_results.append(result)
                        print(f"  {result['package']}: {result['old_path']} -> {result['new_path']}")
        else:
            packages = find_packages_with_tests(pkg_dir)

            for package_path, tests_dir in packages:
                result = rename_tests_directory(package_path, tests_dir, dry_run)
                all_results.append(result)

                if result["renamed"]:
                    print(f"  {result['package']}:")
                    print(f"    Renamed: tests/ -> tests_{result['package']}/")
                    if result["init_added"]:
                        print(f"    Added: __init__.py")
                    if result["files_updated"]:
                        print(f"    Updated imports in {len(result['files_updated'])} file(s)")

    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")

    print(f"Cache cleanup:")
    print(f"  __pycache__ removed: {cache_result['pycache_removed']}")
    print(f"  .pytest_cache removed: {cache_result['pytest_cache_removed']}")

    if not revert:
        print(f"pyproject.toml updates: {len(pyproject_result['changes'])}")

    if revert:
        reverted = sum(1 for r in all_results if r.get("reverted"))
        print(f"Directories reverted: {reverted}")
    else:
        renamed = sum(1 for r in all_results if r.get("renamed"))
        files_updated = sum(len(r.get("files_updated", [])) for r in all_results)
        init_added = sum(1 for r in all_results if r.get("init_added"))

        print(f"Test directories renamed: {renamed}")
        print(f"Files with updated imports: {files_updated}")
        print(f"__init__.py files added: {init_added}")

    if dry_run:
        print(f"\nThis was a dry run. No changes were made.")
        print(f"Run without --dry-run to apply changes.")

    # Update pyproject.toml suggestion
    if not revert and not dry_run and any(r.get("renamed") for r in all_results):
        print(f"\n{'='*60}")
        print("Next Steps")
        print(f"{'='*60}")
        print("""
After running this script, you can now run pytest from root:

    poetry run pytest

Each package's tests are now in a unique namespace (tests_<package>/).
This prevents conftest.py and test module collisions.
""")


if __name__ == "__main__":
    main()
