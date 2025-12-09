#!/usr/bin/env bash
# setup-pythonpath.sh
# Sets up PYTHONPATH with all Python modules for local development
#
# Usage:
#   source .bin/setup-pythonpath.sh     # Source to set in current shell
#   eval $(.bin/setup-pythonpath.sh)    # Alternative

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Build PYTHONPATH
PYTHON_PATHS=""

# Add packages_py/*/src
for pkg in "$PROJECT_ROOT"/packages_py/*/; do
    if [[ -d "${pkg}src" ]]; then
        PYTHON_PATHS="${PYTHON_PATHS}:${pkg}src"
    fi
done

# Add fastapi_apps/*
for app in "$PROJECT_ROOT"/fastapi_apps/*/; do
    if [[ -d "$app" ]]; then
        PYTHON_PATHS="${PYTHON_PATHS}:${app}"
    fi
done

# Remove leading colon and export
PYTHON_PATHS="${PYTHON_PATHS#:}"
export PYTHONPATH="${PYTHON_PATHS}:${PYTHONPATH:-}"

# Print confirmation
echo "PYTHONPATH configured:"
echo "$PYTHONPATH" | tr ':' '\n' | grep -v '^$' | while read -r p; do
    echo "  - $p"
done
echo ""
echo "Total: $(echo "$PYTHONPATH" | tr ':' '\n' | grep -v '^$' | wc -l | tr -d ' ') paths"
