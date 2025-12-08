#!/usr/bin/env bash
# ts-apply-noImplicitAny.sh - Ensure all tsconfig.json files have noImplicitAny: false
# Scans project directories (excluding node_modules) and updates tsconfig files

set -e

SEARCH_DIR="${1:-.}"

echo "═══════════════════════════════════════════════════════════════"
echo "  Scanning for tsconfig.json files in: $SEARCH_DIR"
echo "═══════════════════════════════════════════════════════════════"

# Find all tsconfig.json files excluding node_modules and dist
TSCONFIG_FILES=$(find "$SEARCH_DIR" -name "tsconfig.json" \
    -not -path "*/node_modules/*" \
    -not -path "*/dist/*" \
    -not -path "*/.nx/*" \
    2>/dev/null | sort)

if [ -z "$TSCONFIG_FILES" ]; then
    echo "No tsconfig.json files found."
    exit 0
fi

UPDATED=0
SKIPPED=0
ALREADY_SET=0

echo ""
echo "Found tsconfig.json files:"
echo "$TSCONFIG_FILES"
echo ""

for file in $TSCONFIG_FILES; do
    echo "Processing: $file"

    # Check if file contains noImplicitAny
    if grep -q '"noImplicitAny"' "$file"; then
        # Check if already set to false
        if grep -q '"noImplicitAny"[[:space:]]*:[[:space:]]*false' "$file"; then
            echo "  -> Already has noImplicitAny: false"
            ((ALREADY_SET++))
        else
            # Update noImplicitAny to false
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS sed requires empty string for -i
                sed -i '' 's/"noImplicitAny"[[:space:]]*:[[:space:]]*true/"noImplicitAny": false/g' "$file"
            else
                # Linux sed
                sed -i 's/"noImplicitAny"[[:space:]]*:[[:space:]]*true/"noImplicitAny": false/g' "$file"
            fi
            echo "  -> Updated noImplicitAny to false"
            ((UPDATED++))
        fi
    else
        # Check if file has strict: true (noImplicitAny implied)
        if grep -q '"strict"[[:space:]]*:[[:space:]]*true' "$file"; then
            # Add noImplicitAny: false after strict: true
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' 's/"strict"[[:space:]]*:[[:space:]]*true/"strict": true,\n    "noImplicitAny": false/g' "$file"
            else
                sed -i 's/"strict"[[:space:]]*:[[:space:]]*true/"strict": true,\n    "noImplicitAny": false/g' "$file"
            fi
            echo "  -> Added noImplicitAny: false (strict mode detected)"
            ((UPDATED++))
        else
            echo "  -> Skipped (no strict mode, noImplicitAny not needed)"
            ((SKIPPED++))
        fi
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Summary"
echo "═══════════════════════════════════════════════════════════════"
echo "  Updated:     $UPDATED"
echo "  Already set: $ALREADY_SET"
echo "  Skipped:     $SKIPPED"
echo ""

if [ $UPDATED -gt 0 ]; then
    echo "Run 'git status' to see modified files."
fi
