#!/usr/bin/env bash
# ci-install.sh
# CI/CD installation script for cloud providers (GitHub Actions, GitLab CI, etc.)
#
# Usage:
#   .bin/ci-install.sh                    # Auto-detect Python
#   .bin/ci-install.sh python3.11         # Use specific Python
#   PYTHON=python3.11 .bin/ci-install.sh  # Via environment variable
#
# Environment Variables:
#   PYTHON          - Python interpreter to use (default: auto-detect)
#   SSL_VERIFY      - Set to "false" to disable SSL verification
#   CA_BUNDLE       - Path to custom CA bundle
#   CERT            - Path to client certificate
#   HTTP_PROXY      - HTTP proxy URL
#   HTTPS_PROXY     - HTTPS proxy URL
#   PIP_INDEX_URL   - Custom PyPI registry URL
#   CI              - Set to "true" for quieter output (auto-set by most CI systems)

set -euo pipefail

# Colors (disabled in CI or non-interactive shells)
if [[ -t 1 ]] && [[ -z "${CI:-}" ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Get script directory (project root is parent of .bin)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Determine Python interpreter
detect_python() {
    local python_cmd=""

    # Priority order for Python detection:
    # 1. Command line argument
    # 2. PYTHON environment variable
    # 3. pyenv python 3.11.x
    # 4. python3.11 in PATH
    # 5. python3 in PATH

    if [[ -n "${1:-}" ]]; then
        python_cmd="$1"
    elif [[ -n "${PYTHON:-}" ]]; then
        python_cmd="$PYTHON"
    elif [[ -f "$HOME/.pyenv/versions/3.11.4/bin/python" ]]; then
        python_cmd="$HOME/.pyenv/versions/3.11.4/bin/python"
    elif command -v python3.11 &> /dev/null; then
        python_cmd="python3.11"
    elif command -v python3 &> /dev/null; then
        python_cmd="python3"
    else
        log_error "No Python interpreter found"
        exit 1
    fi

    # Verify Python exists and get version
    if ! command -v "$python_cmd" &> /dev/null && [[ ! -f "$python_cmd" ]]; then
        log_error "Python interpreter not found: $python_cmd"
        exit 1
    fi

    echo "$python_cmd"
}

# Main installation
main() {
    log_info "Starting CI installation..."
    log_info "Project root: $PROJECT_ROOT"

    # Detect Python
    PYTHON_CMD=$(detect_python "${1:-}")
    PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1)
    PYTHON_PATH=$(command -v "$PYTHON_CMD" 2>/dev/null || echo "$PYTHON_CMD")

    log_info "Python: $PYTHON_VERSION ($PYTHON_PATH)"

    # Check Python version is 3.9+
    PYTHON_MAJOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.major)")
    PYTHON_MINOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.minor)")

    if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 9 ]]; then
        log_error "Python 3.9+ required, found $PYTHON_VERSION"
        exit 1
    fi

    # Upgrade pip first
    log_info "Upgrading pip..."
    "$PYTHON_CMD" -m pip install --upgrade pip setuptools wheel --quiet

    # Build make arguments
    MAKE_ARGS="PYTHON=$PYTHON_CMD"

    [[ -n "${SSL_VERIFY:-}" ]] && MAKE_ARGS="$MAKE_ARGS SSL_VERIFY=$SSL_VERIFY"
    [[ -n "${CA_BUNDLE:-}" ]] && MAKE_ARGS="$MAKE_ARGS CA_BUNDLE=$CA_BUNDLE"
    [[ -n "${CERT:-}" ]] && MAKE_ARGS="$MAKE_ARGS CERT=$CERT"
    [[ -n "${HTTP_PROXY:-}" ]] && MAKE_ARGS="$MAKE_ARGS HTTP_PROXY=$HTTP_PROXY"
    [[ -n "${HTTPS_PROXY:-}" ]] && MAKE_ARGS="$MAKE_ARGS HTTPS_PROXY=$HTTPS_PROXY"
    [[ -n "${PIP_INDEX_URL:-}" ]] && MAKE_ARGS="$MAKE_ARGS PIP_INDEX_URL=$PIP_INDEX_URL"
    [[ -n "${CI:-}" ]] && MAKE_ARGS="$MAKE_ARGS CI=$CI"

    # Run installation
    log_info "Running: make -f Makefile.pip $MAKE_ARGS install-all"
    make -f Makefile.pip $MAKE_ARGS install-all

    log_success "Installation complete!"

    # Show installed packages summary
    log_info "Installed packages:"
    "$PYTHON_CMD" -m pip list --format=columns | head -20

    TOTAL_PACKAGES=$("$PYTHON_CMD" -m pip list --format=freeze | wc -l | tr -d ' ')
    log_info "Total packages installed: $TOTAL_PACKAGES"
}

main "$@"
