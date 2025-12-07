#!/bin/bash
# dev-parallel.sh - Run FastAPI, Fastify, and Vite servers in parallel
# Handles clean shutdown on Ctrl+C
#
# Usage:
#   ./dev-parallel.sh                    # FastAPI + Fastify + Vite build:watch

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Ports
FASTIFY_PORT=${FASTIFY_PORT:-51000}
FASTAPI_PORT=${FASTAPI_PORT:-52000}

# Build parameters
BUILD_ID=${BUILD_ID:-local}
BUILD_VERSION=${BUILD_VERSION:-0.0.0-dev}
GIT_COMMIT=${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")}

# Python/venv paths
VENV_DIR="$PROJECT_ROOT/.venv"
if [ -f "$VENV_DIR/bin/uvicorn" ]; then
    UVICORN="$VENV_DIR/bin/uvicorn"
else
    UVICORN="uvicorn"
fi

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting development servers...${NC}"
echo -e "  ${CYAN}Frontend:${NC} watch mode (rebuilds on changes)"
echo -e "  ${CYAN}Fastify:${NC}  http://localhost:${FASTIFY_PORT}"
echo -e "  ${CYAN}FastAPI:${NC}  http://localhost:${FASTAPI_PORT}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Track all background PIDs
PIDS=()

# Cleanup function - kill all child processes
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping all servers...${NC}"

    # Kill all tracked PIDs
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping process $pid..."
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    # Wait briefly for graceful shutdown
    sleep 1

    # Force kill any remaining processes on the ports
    echo "Cleaning up ports..."
    bash "$SCRIPT_DIR/clean-port-51000.sh" 2>/dev/null || true
    bash "$SCRIPT_DIR/clean-port-52000.sh" 2>/dev/null || true

    # Kill any remaining child processes of this script
    pkill -P $$ 2>/dev/null || true

    echo -e "${GREEN}All servers stopped${NC}"
    exit 0
}

# Set up trap - catch INT (Ctrl+C), TERM, and EXIT
trap cleanup INT TERM

# Clean ports before starting
echo -e "${YELLOW}Cleaning up ports before starting...${NC}"
bash "$SCRIPT_DIR/clean-port-51000.sh" 2>/dev/null || true
bash "$SCRIPT_DIR/clean-port-52000.sh" 2>/dev/null || true
echo ""

# Start Frontend (Vite build:watch) in background
echo -e "${GREEN}Starting Frontend (Vite watch)...${NC}"
(cd "$PROJECT_ROOT/frontend_apps/main_entry" && pnpm dev 2>&1 | awk '{print "[Frontend] " $0; fflush()}') &
PIDS+=($!)

# Small delay to let frontend start first
sleep 1

# Start Fastify in background with prefixed output
echo -e "${GREEN}Starting Fastify (port $FASTIFY_PORT)...${NC}"
(cd "$PROJECT_ROOT/fastify_apps/main_entry" && \
    PORT=$FASTIFY_PORT \
    BUILD_ID=$BUILD_ID \
    BUILD_VERSION=$BUILD_VERSION \
    GIT_COMMIT=$GIT_COMMIT \
    node src/main.mjs 2>&1 | awk '{print "[Fastify] " $0; fflush()}') &
PIDS+=($!)

# Small delay
sleep 1

# Start FastAPI in background with prefixed output
echo -e "${GREEN}Starting FastAPI (port $FASTAPI_PORT)...${NC}"
(cd "$PROJECT_ROOT/fastapi_apps/main_entry" && \
    BUILD_ID=$BUILD_ID \
    BUILD_VERSION=$BUILD_VERSION \
    GIT_COMMIT=$GIT_COMMIT \
    $UVICORN app.main:app --reload --host 0.0.0.0 --port $FASTAPI_PORT 2>&1 | awk '{print "[FastAPI] " $0; fflush()}') &
PIDS+=($!)

echo ""
echo -e "${GREEN}All servers started. Waiting...${NC}"
echo ""

# Wait for all processes - this will be interrupted by the trap
wait
