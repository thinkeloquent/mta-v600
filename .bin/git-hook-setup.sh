#!/bin/bash
#
# git-hook-setup.sh - Install git hooks for the monorepo
#
# Usage:
#   .bin/git-hook-setup.sh          # Install all hooks
#   .bin/git-hook-setup.sh --remove # Remove all hooks
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$ROOT_DIR/.git/hooks"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

install_hooks() {
    log_info "Installing git hooks..."

    # Ensure hooks directory exists
    mkdir -p "$HOOKS_DIR"

    # Create pre-commit hook
    cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
#
# Pre-commit hook: Multiple checks
#
# 1. Update COMMIT file with parent (HEAD) commit hash
# 2. Ensure packages_py/ changes are reflected in pyproject.toml
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# =============================================================================
# STEP 1: Update COMMIT file with parent hash
# =============================================================================
# This updates the COMMIT file with the current HEAD hash (which becomes the
# parent of the new commit). The COMMIT file is auto-staged.

COMMIT_FILE="${ROOT_DIR}/COMMIT"

# Get current HEAD hash (this will be the parent of the new commit)
PARENT_HASH="$(git rev-parse HEAD 2>/dev/null || echo 'initial')"

# Check if COMMIT file exists and has the current hash
UPDATE_COMMIT=true
if [ -f "${COMMIT_FILE}" ]; then
    EXISTING_HASH="$(cat "${COMMIT_FILE}" | tr -d '[:space:]')"
    if [ "${EXISTING_HASH}" = "${PARENT_HASH}" ]; then
        UPDATE_COMMIT=false
    fi
fi

if [ "$UPDATE_COMMIT" = true ]; then
    echo "${PARENT_HASH}" > "${COMMIT_FILE}"
    git add "${COMMIT_FILE}"
    echo "[pre-commit] Updated COMMIT file with parent hash: ${PARENT_HASH:0:8}"
fi

# =============================================================================
# STEP 2: Check packages_py/ sync with pyproject.toml
# =============================================================================

SYNC_SCRIPT="$ROOT_DIR/.bin/sync-poetry-local-packages.py"
if [[ ! -f "$SYNC_SCRIPT" ]]; then
    echo "[pre-commit] Warning: sync-poetry-local-packages.py not found, skipping package sync"
    exit 0
fi

# Check if any packages_py files are staged
if git diff --cached --name-only | grep -q "^packages_py/"; then
    echo "[pre-commit] Detected changes in packages_py/, checking pyproject.toml sync..."

    # Run sync in dry-run mode to check
    OUTPUT=$(python3 "$SYNC_SCRIPT" --dry-run 2>&1)

    if echo "$OUTPUT" | grep -q "DRY RUN:"; then
        echo ""
        echo "=========================================="
        echo "pyproject.toml needs to be updated!"
        echo "=========================================="
        echo ""
        echo "Run the following command to sync:"
        echo "  python .bin/sync-poetry-local-packages.py"
        echo ""
        echo "Then add the changes:"
        echo "  git add pyproject.toml"
        echo ""
        exit 1
    fi
fi

exit 0
EOF

    chmod +x "$HOOKS_DIR/pre-commit"
    log_info "Installed pre-commit hook"

    # Remove old hooks if they exist (from previous versions)
    for old_hook in pre-push post-commit; do
        if [ -f "$HOOKS_DIR/$old_hook" ]; then
            rm "$HOOKS_DIR/$old_hook"
            log_info "Removed old $old_hook hook"
        fi
    done

    log_info "Git hooks installed successfully!"
    echo ""
    echo "Installed hooks:"
    echo "  - pre-commit:"
    echo "      1. Updates COMMIT file with parent hash (auto-staged)"
    echo "      2. Checks packages_py/ sync with pyproject.toml"
}

remove_hooks() {
    log_info "Removing git hooks..."

    if [[ -f "$HOOKS_DIR/pre-commit" ]]; then
        rm "$HOOKS_DIR/pre-commit"
        log_info "Removed pre-commit hook"
    else
        log_warn "pre-commit hook not found"
    fi

    log_info "Git hooks removed successfully!"
}

# Parse arguments
case "${1:-}" in
    --remove|-r)
        remove_hooks
        ;;
    --help|-h)
        echo "Usage: $0 [--remove]"
        echo ""
        echo "Options:"
        echo "  --remove, -r  Remove installed hooks"
        echo "  --help, -h    Show this help message"
        ;;
    *)
        install_hooks
        ;;
esac
