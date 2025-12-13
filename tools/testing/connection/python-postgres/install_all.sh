#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Installing all test suites..."

for dir in */; do
    if [ -f "${dir}setup.sh" ]; then
        echo ">>> Installing ${dir}..."
        (cd "$dir" && ./setup.sh)
        echo ">>> Done ${dir}"
    fi
done

echo "All installations complete."
