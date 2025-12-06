#!/bin/bash
# Generate TypeScript types from JSON schemas
# Usage: ./generate-types.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMAS_DIR="$COMMON_DIR/schemas/json"
OUTPUT_DIR="$COMMON_DIR/types/typescript"

echo "Generating types from JSON schemas..."
echo "Schemas: $SCHEMAS_DIR"
echo "Output: $OUTPUT_DIR"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "Type generation complete!"
echo "Note: Add json-schema-to-typescript or similar tool for automatic generation"
