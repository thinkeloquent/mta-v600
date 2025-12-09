#!/usr/bin/env python3
"""
Build standalone wheel by converting path dependencies to PyPI dependencies.

This script:
1. Backs up the original pyproject.toml
2. Converts path-based dependencies to versioned PyPI dependencies
3. The caller then builds the wheel
4. The caller restores the original pyproject.toml

Usage:
    python .bin/build-standalone-wheel.py packages_py/provider_api_getters

The script reads the package's pyproject.toml and rewrites path dependencies
as version-pinned PyPI dependencies, making the wheel installable standalone.
"""

import re
import shutil
import sys
from pathlib import Path

# Mapping of local package names to their PyPI equivalents
# Local packages use underscores, PyPI uses hyphens
# Version is set to ">=1.0.0" for flexibility, adjust as needed
LOCAL_TO_PYPI = {
    # Core infrastructure
    "app_static_config_yaml": ("app-static-config-yaml", ">=1.0.0"),
    "cache_dsn": ("cache-dsn", ">=1.0.0"),
    "cache_request": ("cache-request", ">=1.0.0"),
    "cache_response": ("cache-response", ">=1.0.0"),
    "connection_pool": ("connection-pool", ">=1.0.0"),
    "fetch_client": ("fetch-client", ">=1.0.0"),
    "fetch_proxy_dispatcher": ("fetch-proxy-dispatcher", ">=1.0.0"),
    "fetch_rate_limiter": ("fetch-rate-limiter", ">=1.0.0"),
    "fetch_retry": ("fetch-retry", ">=1.0.0"),
    "vault_file": ("vault-file", ">=1.0.0"),
    # Composition packages
    "fetch_compose_cache_dsn": ("fetch-compose-cache-dsn", ">=1.0.0"),
    "fetch_compose_cache_request": ("fetch-compose-cache-request", ">=1.0.0"),
    "fetch_compose_cache_response": ("fetch-compose-cache-response", ">=1.0.0"),
    "fetch_compose_connection_pool": ("fetch-compose-connection-pool", ">=1.0.0"),
    "fetch_compose_rate_limiter": ("fetch-compose-rate-limiter", ">=1.0.0"),
    "fetch_compose_retry": ("fetch-compose-retry", ">=1.0.0"),
    # High-level packages
    "provider_api_getters": ("provider-api-getters", ">=1.0.0"),
}

# Alternative: Skip local dependencies entirely (comment out to use PyPI mapping)
SKIP_LOCAL_DEPS = False


def convert_pyproject(package_dir: Path) -> None:
    """Convert path dependencies to PyPI dependencies in pyproject.toml."""
    pyproject_path = package_dir / "pyproject.toml"

    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found")
        sys.exit(1)

    # Backup original
    backup_path = package_dir / "pyproject.toml.bak"
    shutil.copy(pyproject_path, backup_path)
    print(f"  Backed up to {backup_path}")

    # Read content
    content = pyproject_path.read_text()

    # Pattern to match path-based dependencies
    # Matches: package_name = {path = "../package_name", develop = true}
    path_dep_pattern = re.compile(
        r'^(\s*)([a-z_][a-z0-9_]*)\s*=\s*\{path\s*=\s*"[^"]+"\s*,?\s*develop\s*=\s*true\s*\}',
        re.MULTILINE | re.IGNORECASE
    )

    def replace_dep(match):
        indent = match.group(1)
        pkg_name = match.group(2)

        if SKIP_LOCAL_DEPS:
            # Remove the dependency entirely
            print(f"  Removed local dependency: {pkg_name}")
            return ""

        if pkg_name in LOCAL_TO_PYPI:
            pypi_name, version = LOCAL_TO_PYPI[pkg_name]
            new_line = f'{indent}{pkg_name} = "{version}"'
            print(f"  Converted: {pkg_name} -> {pypi_name} {version}")
            return new_line
        else:
            # Unknown local package - comment it out
            print(f"  Warning: Unknown local package '{pkg_name}' - commenting out")
            return f"{indent}# {pkg_name} = {{path = ...}}  # Commented out for standalone build"

    # Replace path dependencies
    new_content = path_dep_pattern.sub(replace_dep, content)

    # Remove empty lines that might result from removed deps
    new_content = re.sub(r'\n\n\n+', '\n\n', new_content)

    # Write modified content
    pyproject_path.write_text(new_content)
    print(f"  Updated {pyproject_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python build-standalone-wheel.py <package_dir>")
        print("Example: python build-standalone-wheel.py packages_py/provider_api_getters")
        sys.exit(1)

    package_dir = Path(sys.argv[1])

    if not package_dir.is_dir():
        print(f"Error: {package_dir} is not a directory")
        sys.exit(1)

    print(f"Converting {package_dir} for standalone build...")
    convert_pyproject(package_dir)
    print("Done! Ready for wheel build.")


if __name__ == "__main__":
    main()
