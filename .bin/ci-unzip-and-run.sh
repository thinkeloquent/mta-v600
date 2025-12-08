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

# Extract to temp directory, then move contents to target (avoids nested folder)
TEMP_DIR=$(mktemp -d)
unzip -o "${ZIP_PATH}" -d "${TEMP_DIR}"

# Move contents (handles single root folder in zip)
shopt -s dotglob
EXTRACTED_ITEMS=("${TEMP_DIR}"/*)
if [ ${#EXTRACTED_ITEMS[@]} -eq 1 ] && [ -d "${EXTRACTED_ITEMS[0]}" ]; then
    # Single folder in zip - move its contents
    mv "${EXTRACTED_ITEMS[0]}"/* "${UNZIP_PATH}/"
else
    # Multiple items or files - move all
    mv "${TEMP_DIR}"/* "${UNZIP_PATH}/"
fi
shopt -u dotglob
rm -rf "${TEMP_DIR}"

echo "Deleting ${ZIP_PATH}..."
rm -f "${ZIP_PATH}"

echo "Running CI-1.sh..."
bash CI-1.sh

echo "Sourcing CI-2.sh..."
source CI-2.sh

echo "Done."
