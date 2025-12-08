#!/bin/bash
# =============================================================================
# sync-internal.sh - Copy internal files to their respective locations
#
# Usage:
#   .bin/sync-internal.sh [INTERNAL_PATH] [OPTIONS]
#   .bin/sync-internal.sh                    # Use default ./internal/
#   .bin/sync-internal.sh ./my-internal      # Use custom internal path
#   .bin/sync-internal.sh --dry-run          # Preview with default path
#   .bin/sync-internal.sh ./my-internal -n   # Custom path + dry-run
#
# This script copies files from INTERNAL_PATH/** to ../ (parent of INTERNAL_PATH)
# without overwriting folders.
#
# Example (with default ./internal/):
#   ./internal/static/index.html       => ./static/index.html
#   ./internal/common/config/redis.yaml => ./common/config/redis.yaml
#   ./internal/db_init/db.sql          => ./db_init/db.sql
#
# =============================================================================

set -e

# =============================================================================
# Configuration (default, can be overridden by argument)
# =============================================================================
INTERNAL_DIR="./internal"

# =============================================================================
# Script setup
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
DRY_RUN=false

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_action() {
    echo -e "${BLUE}[COPY]${NC} $1"
}

# =============================================================================
# Parse arguments
# =============================================================================
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [INTERNAL_PATH] [OPTIONS]"
            echo ""
            echo "Copy files from INTERNAL_PATH/ to ../ (parent directory)."
            echo ""
            echo "Arguments:"
            echo "  INTERNAL_PATH  Path to internal directory (default: ./internal)"
            echo ""
            echo "Options:"
            echo "  --dry-run, -n  Show what would be copied without copying"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                       # Copy from ./internal/ to ./"
            echo "  $0 ./my-internal         # Copy from ./my-internal/ to ./"
            echo "  $0 --dry-run             # Preview changes"
            echo "  $0 ./my-internal --dry-run # Custom path + preview"
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
        *)
            # Positional argument: INTERNAL_PATH
            INTERNAL_DIR="$1"
            shift
            ;;
    esac
done

# =============================================================================
# Main logic
# =============================================================================

# Resolve INTERNAL_DIR to absolute path
if [[ "$INTERNAL_DIR" = /* ]]; then
    # Already absolute
    INTERNAL_DIR_ABS="$INTERNAL_DIR"
else
    # Make relative to ROOT_DIR
    INTERNAL_DIR_ABS="$ROOT_DIR/$INTERNAL_DIR"
fi

# Target directory is parent of INTERNAL_DIR (../ from the internal folder)
TARGET_DIR="$(dirname "$INTERNAL_DIR_ABS")"

# Check if internal directory exists
if [[ ! -d "$INTERNAL_DIR_ABS" ]]; then
    log_error "Internal directory not found: $INTERNAL_DIR_ABS"
    exit 1
fi

log_info "Source: $INTERNAL_DIR_ABS"
log_info "Target: $TARGET_DIR"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    log_info "DRY RUN MODE - No files will be copied"
    echo ""
fi

# Count files
FILE_COUNT=0
COPIED_COUNT=0
SKIPPED_COUNT=0

# Find all files in internal directory (excluding hidden files)
while IFS= read -r -d '' internal_file; do
    # Get relative path from internal directory
    # e.g., /path/to/internal/static/index.html => static/index.html
    relative_path="${internal_file#${INTERNAL_DIR_ABS}/}"

    # Target path is ../ from INTERNAL_DIR (parent directory)
    target_path="${TARGET_DIR}/${relative_path}"
    target_dir="$(dirname "$target_path")"

    ((FILE_COUNT++))

    # Check if target is a directory (we don't want to overwrite directories)
    if [[ -d "$target_path" ]]; then
        log_warn "Skipping: $relative_path (target is a directory)"
        ((SKIPPED_COUNT++))
        continue
    fi

    # Create target directory if it doesn't exist
    if [[ ! -d "$target_dir" ]]; then
        if [[ "$DRY_RUN" == "true" ]]; then
            log_action "Would create directory: $target_dir"
        else
            mkdir -p "$target_dir"
        fi
    fi

    # Copy the file
    if [[ "$DRY_RUN" == "true" ]]; then
        if [[ -f "$target_path" ]]; then
            log_action "Would overwrite: $relative_path"
        else
            log_action "Would copy: $relative_path"
        fi
    else
        cp "$internal_file" "$target_path"
        if [[ -f "$target_path" ]]; then
            log_action "Copied: $relative_path"
        fi
    fi

    ((COPIED_COUNT++))

done < <(find "$INTERNAL_DIR_ABS" -type f -print0)

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=========================================="
if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY RUN SUMMARY"
else
    echo "COPY SUMMARY"
fi
echo "=========================================="
echo "Total files found:  $FILE_COUNT"
echo "Files copied:       $COPIED_COUNT"
echo "Files skipped:      $SKIPPED_COUNT"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    log_info "Run without --dry-run to apply changes"
fi
