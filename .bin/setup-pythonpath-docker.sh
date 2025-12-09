#!/bin/bash
# setup-pythonpath-docker.sh
# Docker entrypoint wrapper that dynamically sets PYTHONPATH
#
# Usage: Used as ENTRYPOINT in Dockerfile to ensure PYTHONPATH is set at runtime
#        ENTRYPOINT ["/usr/local/bin/setup-pythonpath.sh"]
#        CMD ["uvicorn", "app:app"]

PYTHON_PATHS=""

# Add packages_py/*/src
for pkg in /applications/packages_py/*/; do
    if [[ -d "${pkg}src" ]]; then
        PYTHON_PATHS="${PYTHON_PATHS}:${pkg}src"
    fi
done

# Add fastapi_apps/*
for app in /applications/fastapi_apps/*/; do
    if [[ -d "$app" ]]; then
        PYTHON_PATHS="${PYTHON_PATHS}:${app}"
    fi
done

# Remove leading colon and export (preserve existing PYTHONPATH)
export PYTHONPATH="${PYTHON_PATHS#:}:${PYTHONPATH:-}"

# Execute the command passed to the entrypoint
exec "$@"
