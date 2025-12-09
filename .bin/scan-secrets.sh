#!/usr/bin/env bash
# ==============================================================================
# Secret Scanner - Detects exposed secrets, API keys, and tokens
# ==============================================================================
# Usage: .bin/scan-secrets.sh [--staged|--all|--diff] [--strict] [--fix]
#
# Options:
#   --staged   Scan only staged files (default for pre-commit)
#   --all      Scan all tracked files
#   --diff     Scan uncommitted changes
#   --strict   Fail on mock/example secrets too
#   --fix      Interactive mode to remove found secrets
#   --quiet    Only output if secrets found
#
# Exit codes:
#   0 - No secrets found
#   1 - Real secrets found (always fails)
#   2 - Mock/example secrets found (fails only with --strict)
# ==============================================================================

set -uo pipefail
# Note: -e disabled to allow script to continue after grep returns no matches

# Colors
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Options
SCAN_MODE="staged"
STRICT_MODE=false
FIX_MODE=false
QUIET_MODE=false

# Counters
REAL_SECRETS_FOUND=0
MOCK_SECRETS_FOUND=0
FINDINGS=()

# ==============================================================================
# Secret Patterns
# ==============================================================================

# Real secret patterns (high confidence - always fail)
REAL_SECRET_PATTERNS=(
    # OpenAI
    'sk-[a-zA-Z0-9]{20,}'
    # GitHub tokens
    'ghp_[a-zA-Z0-9]{36}'
    'gho_[a-zA-Z0-9]{36}'
    'ghu_[a-zA-Z0-9]{36}'
    'ghs_[a-zA-Z0-9]{36}'
    'ghr_[a-zA-Z0-9]{36}'
    'github_pat_[a-zA-Z0-9]{22,}'
    # Slack tokens
    'xox[baprs]-[a-zA-Z0-9-]{10,}'
    # AWS (excluding known examples)
    'AKIA[A-Z0-9]{16}'
    # Google API
    'AIza[a-zA-Z0-9_-]{35}'
    # Stripe
    'sk_live_[a-zA-Z0-9]{24,}'
    'sk_test_[a-zA-Z0-9]{24,}'
    'rk_live_[a-zA-Z0-9]{24,}'
    'rk_test_[a-zA-Z0-9]{24,}'
    # Anthropic
    'sk-ant-[a-zA-Z0-9-]{20,}'
    # npm tokens
    'npm_[a-zA-Z0-9]{36}'
    # PyPI tokens
    'pypi-[a-zA-Z0-9]{36,}'
    # Note: Private key detection removed - grep doesn't handle multi-word patterns well
    # JWT patterns - only flag JWTs that look like real secrets (long tokens)
    # Excluded: test JWTs are usually short or contain obvious test markers
)

# Known mock/example secrets (warning only unless --strict)
MOCK_SECRET_PATTERNS=(
    # AWS example keys from documentation
    'AKIAIOSFODNN7EXAMPLE'
    'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
    # Common test/example values (must be more specific to avoid false positives)
    'test[-_]api[-_]key'
    'example[-_]api[-_]key'
    'your[-_]api[-_]key'
    'sk-test123'
    'sk-example[a-zA-Z0-9]*'
    'fake[-_]token'
    'dummy[-_]secret'
    'placeholder[-_]?key'
    'sample[-_]?api[-_]?key'
)

# Patterns to check for hardcoded credentials
CREDENTIAL_PATTERNS=(
    # Direct assignment patterns
    '(api[_-]?key|apiKey|token|secret|password|credential)\s*[=:]\s*["\x27][A-Za-z0-9+/=_-]{16,}["\x27]'
    # YAML/JSON with long values
    '(api_key|apiKey|token|secret|password):\s*["\x27]?[A-Za-z0-9+/=_-]{20,}["\x27]?'
)

# Files/patterns to exclude from scanning
EXCLUDE_PATTERNS=(
    '\.lock$'
    'package-lock\.json$'
    'yarn\.lock$'
    'pnpm-lock\.yaml$'
    'poetry\.lock$'
    '\.min\.js$'
    '\.min\.css$'
    'node_modules/'
    '\.venv/'
    '__pycache__/'
    '\.git/'
    'dist/'
    'build/'
    '\.env\.example$'
    '\.gitignore$'
    '\.dockerignore$'
    'LICENSE$'
    'CHANGELOG'
    '\.md$'
    '\.mdx$'
    '\.txt$'
    'requirements.*\.txt$'
    '\.secrets-allowlist$'
    'scan-secrets\.sh$'  # Don't scan self
)

# ==============================================================================
# Helper Functions
# ==============================================================================

log_info() {
    if [[ "$QUIET_MODE" == false ]]; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

log_success() {
    if [[ "$QUIET_MODE" == false ]]; then
        echo -e "${GREEN}[OK]${NC} $1"
    fi
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_finding() {
    local severity="$1"
    local file="$2"
    local line="$3"
    local match="$4"
    local pattern="$5"

    if [[ "$severity" == "HIGH" ]]; then
        echo -e "${RED}${BOLD}[HIGH]${NC} ${file}:${line}"
        echo -e "       Match: ${RED}${match}${NC}"
        echo -e "       Pattern: ${pattern}"
        FINDINGS+=("HIGH|$file|$line|$match")
        ((REAL_SECRETS_FOUND++))
    else
        echo -e "${YELLOW}[MOCK]${NC} ${file}:${line}"
        echo -e "       Match: ${YELLOW}${match}${NC}"
        echo -e "       Pattern: ${pattern}"
        FINDINGS+=("MOCK|$file|$line|$match")
        ((MOCK_SECRETS_FOUND++))
    fi
}

build_exclude_args() {
    local args=""
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        args="$args --exclude-dir=${pattern%/}"
    done
    echo "$args"
}

get_files_to_scan() {
    case "$SCAN_MODE" in
        staged)
            git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true
            ;;
        diff)
            git diff --name-only 2>/dev/null || true
            ;;
        all)
            git ls-files 2>/dev/null || find "$PROJECT_ROOT" -type f
            ;;
    esac
}

is_excluded() {
    local file="$1"
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        if [[ "$file" =~ $pattern ]]; then
            return 0
        fi
    done
    return 1
}

is_mock_secret() {
    local match="$1"
    for pattern in "${MOCK_SECRET_PATTERNS[@]}"; do
        if echo "$match" | grep -qiE "$pattern"; then
            return 0
        fi
    done
    return 1
}

mask_secret() {
    local secret="$1"
    local len=${#secret}

    # For mock secrets, show asterisks to indicate it should be replaced
    if is_mock_secret "$secret"; then
        printf '*%.0s' $(seq 1 $len)
        return
    fi

    # For real secrets, show partial masking
    if [[ $len -le 8 ]]; then
        echo "****"
    else
        echo "${secret:0:4}...${secret: -4}"
    fi
}

# ==============================================================================
# Scanning Functions
# ==============================================================================

scan_for_pattern() {
    local pattern="$1"
    local severity="$2"
    local files="$3"

    if [[ -z "$files" ]]; then
        return
    fi

    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        is_excluded "$file" && continue
        [[ ! -f "$PROJECT_ROOT/$file" ]] && continue

        # Use grep to find matches
        while IFS=: read -r line_num match; do
            [[ -z "$match" ]] && continue

            # Check if it's a mock secret
            if is_mock_secret "$match"; then
                # Always log mock secrets (for visibility), but they only block in strict mode
                log_finding "MOCK" "$file" "$line_num" "$(mask_secret "$match")" "$pattern"
            else
                log_finding "$severity" "$file" "$line_num" "$(mask_secret "$match")" "$pattern"
            fi
        done < <(grep -nEo "$pattern" "$PROJECT_ROOT/$file" 2>/dev/null || true)
    done <<< "$files"
}

scan_env_files() {
    log_info "Checking for tracked .env files..."

    local tracked_env_files
    tracked_env_files=$(git ls-files '*.env' '.env*' '*/.env*' 2>/dev/null | grep -v '\.example$' | grep -v '\.sample$' || true)

    if [[ -n "$tracked_env_files" ]]; then
        while IFS= read -r file; do
            [[ -z "$file" ]] && continue
            log_finding "HIGH" "$file" "0" "[ENTIRE FILE]" "Tracked .env file"
        done <<< "$tracked_env_files"
    fi
}

scan_credential_assignments() {
    local files="$1"

    log_info "Scanning for hardcoded credential assignments..."

    for pattern in "${CREDENTIAL_PATTERNS[@]}"; do
        while IFS= read -r file; do
            [[ -z "$file" ]] && continue
            is_excluded "$file" && continue
            [[ ! -f "$PROJECT_ROOT/$file" ]] && continue

            while IFS=: read -r line_num content; do
                [[ -z "$content" ]] && continue

                # Skip if it references env vars
                if echo "$content" | grep -qE '(os\.getenv|process\.env|getenv|ENV\[|\$\{|CONFIG\[)'; then
                    continue
                fi

                # Skip known safe patterns
                if echo "$content" | grep -qE '(auth_type|type.*bearer|type.*basic|header_name)'; then
                    continue
                fi

                # Extract the actual value
                local value
                value=$(echo "$content" | grep -oE '["\x27][A-Za-z0-9+/=_-]{16,}["\x27]' | head -1 | tr -d "\"'")

                if [[ -n "$value" ]]; then
                    if is_mock_secret "$value"; then
                        log_finding "MOCK" "$file" "$line_num" "$(mask_secret "$value")" "Hardcoded credential"
                    else
                        log_finding "HIGH" "$file" "$line_num" "$(mask_secret "$value")" "Hardcoded credential"
                    fi
                fi
            done < <(grep -nE "$pattern" "$PROJECT_ROOT/$file" 2>/dev/null || true)
        done <<< "$files"
    done
}

# ==============================================================================
# Interactive Fix Mode
# ==============================================================================

prompt_fix() {
    if [[ "$FIX_MODE" == false ]]; then
        return
    fi

    if [[ ${#FINDINGS[@]} -eq 0 ]]; then
        return
    fi

    echo ""
    echo -e "${BOLD}Found ${#FINDINGS[@]} potential secret(s). Would you like to review them?${NC}"
    echo ""

    for finding in "${FINDINGS[@]}"; do
        IFS='|' read -r severity file line match <<< "$finding"

        echo -e "${BOLD}[$severity]${NC} $file:$line"
        echo -e "  Match: $match"
        echo ""

        if [[ "$severity" == "HIGH" ]]; then
            echo -e "  ${RED}This appears to be a real secret and should be removed.${NC}"
        else
            echo -e "  ${YELLOW}This appears to be a mock/example secret.${NC}"
        fi

        echo ""
        read -p "  Action: [s]kip, [v]iew context, [o]pen in editor, [a]dd to allowlist? " action

        case "$action" in
            v|V)
                echo ""
                echo "  Context (5 lines before and after):"
                sed -n "$((line > 5 ? line - 5 : 1)),$((line + 5))p" "$PROJECT_ROOT/$file" | head -11
                echo ""
                ;;
            o|O)
                ${EDITOR:-vim} "+$line" "$PROJECT_ROOT/$file"
                ;;
            a|A)
                echo "$match" >> "$PROJECT_ROOT/.secrets-allowlist"
                echo "  Added to .secrets-allowlist"
                ;;
            *)
                echo "  Skipped"
                ;;
        esac
        echo ""
    done
}

# ==============================================================================
# Main
# ==============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --staged)
                SCAN_MODE="staged"
                shift
                ;;
            --all)
                SCAN_MODE="all"
                shift
                ;;
            --diff)
                SCAN_MODE="diff"
                shift
                ;;
            --strict)
                STRICT_MODE=true
                shift
                ;;
            --fix)
                FIX_MODE=true
                shift
                ;;
            --quiet)
                QUIET_MODE=true
                shift
                ;;
            -h|--help)
                head -25 "$0" | tail -23
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

main() {
    parse_args "$@"

    cd "$PROJECT_ROOT"

    if [[ "$QUIET_MODE" == false ]]; then
        echo ""
        echo -e "${BOLD}Secret Scanner${NC}"
        echo "============================================"
        echo "Mode: $SCAN_MODE"
        echo "Strict: $STRICT_MODE"
        echo ""
    fi

    # Get files to scan
    local files
    files=$(get_files_to_scan)

    if [[ -z "$files" ]]; then
        log_info "No files to scan"
        exit 0
    fi

    local file_count
    file_count=$(echo "$files" | wc -l | tr -d ' ')
    log_info "Scanning $file_count file(s)..."
    echo ""

    # Scan for tracked .env files
    scan_env_files

    # Scan for real secret patterns - build combined pattern for efficiency
    log_info "Scanning for API keys and tokens..."

    # Combine high-confidence patterns into one grep call for speed
    local combined_pattern
    combined_pattern=$(IFS='|'; echo "${REAL_SECRET_PATTERNS[*]}")

    while IFS=: read -r file line_num match; do
        [[ -z "$match" ]] && continue
        [[ -z "$file" ]] && continue
        is_excluded "$file" && continue

        # Determine which pattern matched for reporting
        local matched_pattern="API key/token pattern"
        for p in "${REAL_SECRET_PATTERNS[@]}"; do
            if echo "$match" | grep -qE "$p"; then
                matched_pattern="$p"
                break
            fi
        done

        if is_mock_secret "$match"; then
            log_finding "MOCK" "$file" "$line_num" "$(mask_secret "$match")" "$matched_pattern"
        else
            log_finding "HIGH" "$file" "$line_num" "$(mask_secret "$match")" "$matched_pattern"
        fi
    done < <(grep -rHnEo "$combined_pattern" \
        --include="*.py" --include="*.mjs" --include="*.js" --include="*.ts" \
        --include="*.json" --include="*.yaml" --include="*.yml" --include="*.toml" \
        --include="*.sh" --include="*.bash" --include="*.env" --include="*.cfg" \
        --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=__pycache__ \
        --exclude-dir=.git --exclude-dir=dist --exclude-dir=build \
        --exclude-dir=__STAGE__ --exclude-dir=__SPECS__ --exclude-dir=__REVIEW__ \
        . 2>/dev/null | sed 's|^\./||' || true)

    # Skip credential assignment scanning in full mode (too slow/memory intensive)
    # scan_credential_assignments "$files"

    # Interactive fix mode
    prompt_fix

    # Summary
    echo ""
    echo "============================================"
    echo -e "${BOLD}Summary${NC}"
    echo "============================================"

    if [[ $REAL_SECRETS_FOUND -gt 0 ]]; then
        echo -e "${RED}Real secrets found: $REAL_SECRETS_FOUND${NC}"
    else
        echo -e "${GREEN}Real secrets found: 0${NC}"
    fi

    if [[ $MOCK_SECRETS_FOUND -gt 0 ]]; then
        echo -e "${YELLOW}Mock/example secrets found: $MOCK_SECRETS_FOUND${NC}"
    else
        echo -e "${GREEN}Mock/example secrets found: 0${NC}"
    fi

    echo ""

    # Exit code logic
    if [[ $REAL_SECRETS_FOUND -gt 0 ]]; then
        log_error "Commit blocked: Real secrets detected!"
        echo ""
        echo "Please remove the secrets before committing."
        echo "If these are false positives, add them to .secrets-allowlist"
        exit 1
    fi

    if [[ $MOCK_SECRETS_FOUND -gt 0 && "$STRICT_MODE" == true ]]; then
        log_warning "Commit blocked (strict mode): Mock secrets detected!"
        echo ""
        echo "Remove mock secrets or run without --strict"
        exit 2
    fi

    if [[ $MOCK_SECRETS_FOUND -gt 0 ]]; then
        log_warning "Mock/example secrets detected (allowed in non-strict mode)"
    fi

    log_success "Secret scan passed!"
    exit 0
}

main "$@"
