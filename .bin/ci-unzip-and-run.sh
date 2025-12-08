#!/bin/bash
#
# Unzip a file, delete the zip, and run CI scripts.
#
# Usage:
#   ./.bin/ci-unzip-and-run.sh
#

set -e

# =============================================================================
# Configuration
# =============================================================================
ZIP_PATH="./hello.zip"
UNZIP_PATH="/hello/world"

# =============================================================================
# Main
# =============================================================================

echo "Unzipping ${ZIP_PATH} to ${UNZIP_PATH}..."
mkdir -p "${UNZIP_PATH}"
unzip -o "${ZIP_PATH}" -d "${UNZIP_PATH}"

echo "Deleting ${ZIP_PATH}..."
rm -f "${ZIP_PATH}"

echo "Running CI-1.sh..."
bash CI-1.sh

echo "Sourcing CI-2.sh..."
source CI-2.sh

echo "Done."
