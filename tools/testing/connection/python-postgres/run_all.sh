#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Running all test suites..."

for dir in */; do
    if [ -f "${dir}run.sh" ]; then
        echo ">>> Running test suite: ${dir}"
        (cd "$dir" && ./run.sh)
        echo "---------------------------------------------------"
    fi
done

echo "All tests complete."
